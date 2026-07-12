import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import FACE_MATCH_THRESHOLD
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.models.user import User
from app.services.departments import ensure_department_access
from app.services.face_enrollment import ALLOWED_FACE_IMAGE_SUFFIXES, FACE_ENROLLMENT_SAMPLE_COUNT, MAX_FACE_IMAGE_BYTES
from app.services.face_processing import ENCODING_VERSION, PROCESSING_PROVIDER, process_image_bytes
from app.services.students import ensure_student_access, get_student_or_404


@dataclass
class MatchCandidate:
    template: FaceTemplate
    descriptor: list[float]


def validate_match_upload_file(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_FACE_IMAGE_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only .jpg, .jpeg, and .png image files are supported",
        )
    return suffix


async def read_match_upload(file: UploadFile) -> bytes:
    validate_match_upload_file(file)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")
    if len(content) > MAX_FACE_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded image is larger than the 5 MB limit",
        )
    return content


def parse_encoding_data(encodingData: str | None) -> list[float] | None:
    if not encodingData:
        return None
    try:
        values = json.loads(encodingData)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(values, list) or not values:
        return None
    descriptor: list[float] = []
    for value in values:
        if not isinstance(value, (int, float)):
            return None
        descriptor.append(float(value))
    return descriptor


def compare_descriptors(queryVector: list[float], storedVector: list[float]) -> float:
    if len(queryVector) != len(storedVector) or not queryVector:
        return -1.0
    query = np.array(queryVector, dtype=np.float32)
    stored = np.array(storedVector, dtype=np.float32)
    query_norm = float(np.linalg.norm(query))
    stored_norm = float(np.linalg.norm(stored))
    if query_norm == 0 or stored_norm == 0:
        return -1.0
    return round(float(np.dot(query, stored) / (query_norm * stored_norm)), 6)


def registered_student_subquery(db: Session):
    return (
        db.query(FaceTemplate.studentId)
        .filter(FaceTemplate.isActive.is_(True))
        .group_by(FaceTemplate.studentId)
        .having(func.count(FaceTemplate.templateId) >= FACE_ENROLLMENT_SAMPLE_COUNT)
        .subquery()
    )


def eligible_student_count(db: Session, departmentId: int) -> int:
    registered_students = registered_student_subquery(db)
    return (
        db.query(Student)
        .filter(
            Student.departmentId == departmentId,
            Student.status == "Active",
            Student.studentId.in_(registered_students),
        )
        .count()
    )


def load_candidate_templates(db: Session, departmentId: int) -> list[MatchCandidate]:
    registered_students = registered_student_subquery(db)
    templates = (
        db.query(FaceTemplate)
        .join(Student)
        .filter(
            Student.departmentId == departmentId,
            Student.status == "Active",
            Student.studentId.in_(registered_students),
            FaceTemplate.isActive.is_(True),
            FaceTemplate.status == "Encoded",
            FaceTemplate.encodingData.isnot(None),
        )
        .all()
    )

    candidates: list[MatchCandidate] = []
    for template in templates:
        descriptor = parse_encoding_data(template.encodingData)
        if descriptor is not None:
            candidates.append(MatchCandidate(template=template, descriptor=descriptor))
    return candidates


def load_student_candidate_templates(db: Session, student: Student) -> list[MatchCandidate]:
    templates = (
        db.query(FaceTemplate)
        .filter(
            FaceTemplate.studentId == student.studentId,
            FaceTemplate.isActive.is_(True),
            FaceTemplate.status == "Encoded",
            FaceTemplate.encodingData.isnot(None),
        )
        .all()
    )

    candidates: list[MatchCandidate] = []
    for template in templates:
        descriptor = parse_encoding_data(template.encodingData)
        if descriptor is not None:
            candidates.append(MatchCandidate(template=template, descriptor=descriptor))
    return candidates


def find_best_match(
    queryVector: list[float],
    candidates: list[MatchCandidate],
    threshold: float = FACE_MATCH_THRESHOLD,
) -> tuple[MatchCandidate | None, float | None]:
    best_candidate: MatchCandidate | None = None
    best_score: float | None = None
    best_by_student: dict[int, tuple[MatchCandidate, float]] = {}

    for candidate in candidates:
        score = compare_descriptors(queryVector, candidate.descriptor)
        if score < 0:
            continue
        student_id = candidate.template.studentId
        current = best_by_student.get(student_id)
        if current is None or score > current[1]:
            best_by_student[student_id] = (candidate, score)

    for candidate, score in best_by_student.values():
        if best_score is None or score > best_score:
            best_candidate = candidate
            best_score = score

    if best_candidate is None or best_score is None or best_score < threshold:
        return best_candidate, best_score
    return best_candidate, best_score


def failure_result(status_value: str, message: str, threshold: float, candidate_count: int = 0) -> dict:
    return {
        "matched": False,
        "status": status_value,
        "message": message,
        "thresholdUsed": threshold,
        "candidateCount": candidate_count,
    }


def success_result(candidate: MatchCandidate, score: float, threshold: float, candidate_count: int) -> dict:
    student = candidate.template.student
    return {
        "matched": True,
        "status": "Matched",
        "message": "Best matching enrolled student candidate found.",
        "studentId": student.studentId,
        "studentName": student.fullName,
        "rollNo": student.rollNo,
        "classId": student.classId,
        "className": student.classroom.className if student.classroom else None,
        "departmentId": student.departmentId,
        "departmentName": student.department.departmentName if student.department else None,
        "bestTemplateId": candidate.template.templateId,
        "similarityScore": score,
        "thresholdUsed": threshold,
        "candidateCount": candidate_count,
    }


def build_match_response(
    db: Session,
    departmentId: int,
    queryVector: list[float],
    candidates: list[MatchCandidate],
    threshold: float = FACE_MATCH_THRESHOLD,
) -> dict:
    if not candidates:
        if eligible_student_count(db, departmentId) == 0:
            return failure_result("NoEligibleStudents", "No active registered students are eligible in this department.", threshold)
        return failure_result("NoEncodedTemplates", "No active encoded face templates are available in this department.", threshold)

    best_candidate, best_score = find_best_match(queryVector, candidates, threshold)
    if best_candidate is None or best_score is None or best_score < threshold:
        return {
            **failure_result("MatchBelowThreshold", "Best candidate is below the configured threshold.", threshold, len(candidates)),
            "similarityScore": best_score,
            "bestTemplateId": best_candidate.template.templateId if best_candidate else None,
        }
    return success_result(best_candidate, best_score, threshold, len(candidates))


def match_face_bytes(db: Session, currentUser: User, departmentId: int, image_bytes: bytes) -> dict:
    ensure_department_access(currentUser, departmentId)
    processing_result = process_image_bytes(image_bytes)
    if processing_result.status == "NoFaceDetected" or not processing_result.encodingData:
        return failure_result("NoFaceDetected", "No face was detected in the uploaded image.", FACE_MATCH_THRESHOLD)

    query_vector = parse_encoding_data(processing_result.encodingData)
    if query_vector is None:
        return failure_result("InvalidImage", "The uploaded image could not produce a valid descriptor.", FACE_MATCH_THRESHOLD)

    candidates = load_candidate_templates(db, departmentId)
    return build_match_response(db, departmentId, query_vector, candidates, FACE_MATCH_THRESHOLD)


def test_student_face_bytes(db: Session, currentUser: User, studentId: int, image_bytes: bytes) -> dict:
    student = get_student_or_404(db, studentId)
    ensure_student_access(currentUser, student)
    processing_result = process_image_bytes(image_bytes)
    if processing_result.status == "NoFaceDetected" or not processing_result.encodingData:
        return failure_result("NoFaceDetected", "No face was detected in the uploaded image.", FACE_MATCH_THRESHOLD)

    query_vector = parse_encoding_data(processing_result.encodingData)
    if query_vector is None:
        return failure_result("InvalidImage", "The uploaded image could not produce a valid descriptor.", FACE_MATCH_THRESHOLD)

    candidates = load_student_candidate_templates(db, student)
    if not candidates:
        return failure_result("NoEncodedTemplates", "This student has no active encoded face templates.", FACE_MATCH_THRESHOLD)

    best_candidate, best_score = find_best_match(query_vector, candidates, FACE_MATCH_THRESHOLD)
    if best_candidate is None or best_score is None or best_score < FACE_MATCH_THRESHOLD:
        return {
            **failure_result("MatchBelowThreshold", "Best student-specific candidate is below the configured threshold.", FACE_MATCH_THRESHOLD, len(candidates)),
            "studentId": student.studentId,
            "studentName": student.fullName,
            "rollNo": student.rollNo,
            "classId": student.classId,
            "className": student.classroom.className if student.classroom else None,
            "departmentId": student.departmentId,
            "departmentName": student.department.departmentName if student.department else None,
            "similarityScore": best_score,
            "bestTemplateId": best_candidate.template.templateId if best_candidate else None,
        }
    return success_result(best_candidate, best_score, FACE_MATCH_THRESHOLD, len(candidates))


def matching_info() -> dict:
    return {
        "provider": PROCESSING_PROVIDER,
        "encodingVersion": ENCODING_VERSION,
        "matchingImplemented": True,
        "attendanceMarkingImplemented": False,
        "livenessImplemented": False,
        "threshold": FACE_MATCH_THRESHOLD,
        "notes": "Foundation-level OpenCV descriptor matching only; no attendance marking or liveness detection is implemented.",
    }
