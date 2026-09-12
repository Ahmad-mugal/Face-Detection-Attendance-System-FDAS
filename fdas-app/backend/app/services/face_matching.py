import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import (
    FACE_MATCH_AGGREGATION,
    FACE_MATCH_THRESHOLD,
    IDENTITY_MATCHING_SAFETY_HOLD,
    MIN_IDENTITY_MARGIN,
)
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.models.user import User
from app.services.departments import ensure_department_access
from app.services.face_enrollment import ALLOWED_FACE_IMAGE_SUFFIXES, FACE_ENROLLMENT_SAMPLE_COUNT, MAX_FACE_IMAGE_BYTES
from app.services.face_processing import ENCODING_VERSION, PROCESSING_PROVIDER, descriptor_similarity, process_image_bytes
from app.services.students import ensure_student_access, get_student_or_404


@dataclass
class MatchCandidate:
    template: FaceTemplate
    descriptor: list[float]


@dataclass
class StudentMatchScore:
    candidate: MatchCandidate
    score: float
    templatesEvaluated: int
    maximumScore: float
    meanTop3Score: float
    meanTop5Score: float
    medianTop5Score: float


MATCH_AGGREGATION_METHODS = ("maximum", "mean_top_3", "mean_top_5", "median_top_5")


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
    return descriptor_similarity(queryVector, storedVector)


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
            FaceTemplate.encodingVersion == ENCODING_VERSION,
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
            FaceTemplate.encodingVersion == ENCODING_VERSION,
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
    ranked_students = rank_student_matches(queryVector, candidates, FACE_MATCH_AGGREGATION)
    if not ranked_students:
        return None, None
    best = ranked_students[0]
    return best.candidate, best.score


def calculate_student_aggregate_scores(scores: list[float]) -> dict[str, float]:
    ordered = sorted(scores, reverse=True)
    if not ordered:
        raise ValueError("At least one template score is required")

    top_three = ordered[:3]
    top_five = ordered[:5]
    median_index = len(top_five) // 2
    if len(top_five) % 2:
        median_top_five = top_five[median_index]
    else:
        median_top_five = (top_five[median_index - 1] + top_five[median_index]) / 2

    return {
        "maximum": round(ordered[0], 6),
        "mean_top_3": round(sum(top_three) / len(top_three), 6),
        "mean_top_5": round(sum(top_five) / len(top_five), 6),
        "median_top_5": round(median_top_five, 6),
    }


def rank_student_matches(
    queryVector: list[float],
    candidates: list[MatchCandidate],
    aggregation_method: str = FACE_MATCH_AGGREGATION,
) -> list[StudentMatchScore]:
    if aggregation_method not in MATCH_AGGREGATION_METHODS:
        raise ValueError(f"Unsupported face-match aggregation method: {aggregation_method}")

    candidates_by_student: dict[int, list[tuple[MatchCandidate, float]]] = {}

    for candidate in candidates:
        score = compare_descriptors(queryVector, candidate.descriptor)
        student_id = candidate.template.studentId
        candidates_by_student.setdefault(student_id, []).append((candidate, score))

    ranked: list[StudentMatchScore] = []
    for student_candidates in candidates_by_student.values():
        ordered = sorted(
            student_candidates,
            key=lambda item: (-item[1], item[0].template.templateId),
        )
        aggregate_scores = calculate_student_aggregate_scores([score for _, score in ordered])
        ranked.append(
            StudentMatchScore(
                candidate=ordered[0][0],
                score=aggregate_scores[aggregation_method],
                templatesEvaluated=len(ordered),
                maximumScore=aggregate_scores["maximum"],
                meanTop3Score=aggregate_scores["mean_top_3"],
                meanTop5Score=aggregate_scores["mean_top_5"],
                medianTop5Score=aggregate_scores["median_top_5"],
            )
        )

    ranked.sort(key=lambda item: (-item.score, item.candidate.template.studentId))
    return ranked


def diagnostic_candidate_result(item: StudentMatchScore) -> dict:
    student = item.candidate.template.student
    return {
        "studentId": student.studentId,
        "studentName": student.fullName,
        "rollNo": student.rollNo,
        "bestTemplateId": item.candidate.template.templateId,
        "bestScore": item.score,
        "maximumScore": item.maximumScore,
        "meanTop3Score": item.meanTop3Score,
        "meanTop5Score": item.meanTop5Score,
        "medianTop5Score": item.medianTop5Score,
        "templatesEvaluated": item.templatesEvaluated,
    }


def diagnostic_aggregation_result(
    method: str,
    queryVector: list[float],
    candidates: list[MatchCandidate],
    expectedStudentId: int | None,
) -> dict:
    ranked = rank_student_matches(queryVector, candidates, method)
    top = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    expected = next(
        (item for item in ranked if item.candidate.template.studentId == expectedStudentId),
        None,
    )
    margin = round(top.score - second.score, 6) if top is not None and second is not None else None
    return {
        "method": method,
        "expectedStudentScore": expected.score if expected is not None else None,
        "topStudentId": top.candidate.template.studentId if top is not None else None,
        "topScore": top.score if top is not None else None,
        "secondStudentId": second.candidate.template.studentId if second is not None else None,
        "secondScore": second.score if second is not None else None,
        "scoreMargin": margin,
        "passesThreshold": top is not None and top.score >= FACE_MATCH_THRESHOLD,
        "passesMargin": margin is None or margin >= MIN_IDENTITY_MARGIN,
    }


def build_diagnostic_response(
    departmentId: int,
    expectedStudentId: int | None,
    queryVector: list[float],
    candidates: list[MatchCandidate],
) -> dict:
    ranked = rank_student_matches(queryVector, candidates, FACE_MATCH_AGGREGATION)
    top = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    expected = next(
        (item for item in ranked if item.candidate.template.studentId == expectedStudentId),
        None,
    )
    score_margin = round(top.score - second.score, 6) if top is not None and second is not None else None
    return {
        "status": "DiagnosticComplete" if top is not None else "NoEncodedTemplates",
        "message": (
            "Identity scores calculated without creating attendance."
            if top is not None
            else "No active encoded face templates are available in this department."
        ),
        "attendanceCreated": False,
        "departmentId": departmentId,
        "expectedStudentId": expectedStudentId,
        "expectedStudentScore": expected.score if expected is not None else None,
        "thresholdUsed": FACE_MATCH_THRESHOLD,
        "aggregationMethod": FACE_MATCH_AGGREGATION,
        "requiredMargin": MIN_IDENTITY_MARGIN,
        "candidateStudentCount": len(ranked),
        "candidateTemplateCount": len(candidates),
        "topCandidate": diagnostic_candidate_result(top) if top is not None else None,
        "secondCandidate": diagnostic_candidate_result(second) if second is not None else None,
        "scoreMargin": score_margin,
        "topAboveThreshold": top is not None and top.score >= FACE_MATCH_THRESHOLD,
        "candidates": [diagnostic_candidate_result(item) for item in ranked],
        "aggregations": [
            diagnostic_aggregation_result(method, queryVector, candidates, expectedStudentId)
            for method in MATCH_AGGREGATION_METHODS
        ],
    }


def failure_result(status_value: str, message: str, threshold: float, candidate_count: int = 0) -> dict:
    return {
        "matched": False,
        "status": status_value,
        "message": message,
        "thresholdUsed": threshold,
        "aggregationMethod": FACE_MATCH_AGGREGATION,
        "requiredMargin": MIN_IDENTITY_MARGIN,
        "candidateCount": candidate_count,
    }


def success_result(
    candidate: MatchCandidate,
    score: float,
    threshold: float,
    candidate_count: int,
    second_score: float | None = None,
    score_margin: float | None = None,
) -> dict:
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
        "secondSimilarityScore": second_score,
        "scoreMargin": score_margin,
        "thresholdUsed": threshold,
        "aggregationMethod": FACE_MATCH_AGGREGATION,
        "requiredMargin": MIN_IDENTITY_MARGIN,
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

    ranked = rank_student_matches(queryVector, candidates, FACE_MATCH_AGGREGATION)
    best = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    best_candidate = best.candidate if best is not None else None
    best_score = best.score if best is not None else None
    if best_candidate is None or best_score is None or best_score < threshold:
        return {
            **failure_result("MatchBelowThreshold", "Best candidate is below the configured threshold.", threshold, len(candidates)),
            "similarityScore": best_score,
            "bestTemplateId": best_candidate.template.templateId if best_candidate else None,
        }

    second_score = second.score if second is not None else None
    score_margin = round(best_score - second_score, 6) if second_score is not None else None
    if score_margin is not None and score_margin < MIN_IDENTITY_MARGIN:
        return {
            **failure_result(
                "AmbiguousMatch",
                "Identity could not be determined confidently. Please try again.",
                threshold,
                len(candidates),
            ),
            "similarityScore": best_score,
            "secondSimilarityScore": second_score,
            "scoreMargin": score_margin,
        }

    return success_result(
        best_candidate,
        best_score,
        threshold,
        len(candidates),
        second_score=second_score,
        score_margin=score_margin,
    )


def match_face_bytes(db: Session, currentUser: User, departmentId: int, image_bytes: bytes) -> dict:
    ensure_department_access(currentUser, departmentId)
    processing_result = process_image_bytes(image_bytes)
    if processing_result.status == "MultipleFacesDetected":
        return failure_result(
            "MultipleFacesDetected",
            "Multiple faces detected. Please allow only one student in front of the camera for attendance.",
            FACE_MATCH_THRESHOLD,
        )
    if processing_result.status == "NoFaceDetected" or not processing_result.encodingData:
        return failure_result("NoFaceDetected", "No face was detected in the uploaded image.", FACE_MATCH_THRESHOLD)

    query_vector = parse_encoding_data(processing_result.encodingData)
    if query_vector is None:
        return failure_result("InvalidImage", "The uploaded image could not produce a valid descriptor.", FACE_MATCH_THRESHOLD)

    candidates = load_candidate_templates(db, departmentId)
    return build_match_response(db, departmentId, query_vector, candidates, FACE_MATCH_THRESHOLD)


def diagnose_face_bytes(
    db: Session,
    currentUser: User,
    departmentId: int,
    expectedStudentId: int | None,
    image_bytes: bytes,
) -> dict:
    ensure_department_access(currentUser, departmentId)
    if expectedStudentId is not None:
        expected_student = get_student_or_404(db, expectedStudentId)
        ensure_student_access(currentUser, expected_student)
        if expected_student.departmentId != departmentId:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Expected student is not in the selected department",
            )

    processing_result = process_image_bytes(image_bytes)
    if processing_result.status == "MultipleFacesDetected":
        return {
            "status": "MultipleFacesDetected",
            "message": "Multiple faces detected. Only one person should be in front of the camera.",
            "attendanceCreated": False,
            "departmentId": departmentId,
            "expectedStudentId": expectedStudentId,
            "expectedStudentScore": None,
            "thresholdUsed": FACE_MATCH_THRESHOLD,
            "candidateStudentCount": 0,
            "candidateTemplateCount": 0,
            "topCandidate": None,
            "secondCandidate": None,
            "scoreMargin": None,
            "topAboveThreshold": False,
            "candidates": [],
        }
    if processing_result.status == "NoFaceDetected" or not processing_result.encodingData:
        return {
            "status": "NoFaceDetected",
            "message": "No face was detected in the diagnostic image.",
            "attendanceCreated": False,
            "departmentId": departmentId,
            "expectedStudentId": expectedStudentId,
            "expectedStudentScore": None,
            "thresholdUsed": FACE_MATCH_THRESHOLD,
            "candidateStudentCount": 0,
            "candidateTemplateCount": 0,
            "topCandidate": None,
            "secondCandidate": None,
            "scoreMargin": None,
            "topAboveThreshold": False,
            "candidates": [],
        }

    query_vector = parse_encoding_data(processing_result.encodingData)
    if query_vector is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The diagnostic image could not produce a valid descriptor",
        )

    candidates = load_candidate_templates(db, departmentId)
    return build_diagnostic_response(departmentId, expectedStudentId, query_vector, candidates)


def test_student_face_bytes(db: Session, currentUser: User, studentId: int, image_bytes: bytes) -> dict:
    student = get_student_or_404(db, studentId)
    ensure_student_access(currentUser, student)
    processing_result = process_image_bytes(image_bytes)
    if processing_result.status == "MultipleFacesDetected":
        return failure_result(
            "MultipleFacesDetected",
            "Multiple faces detected. Only one person should be in front of the camera.",
            FACE_MATCH_THRESHOLD,
        )
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
        "attendanceMarkingImplemented": True,
        "livenessImplemented": True,
        "threshold": FACE_MATCH_THRESHOLD,
        "aggregationMethod": FACE_MATCH_AGGREGATION,
        "requiredIdentityMargin": MIN_IDENTITY_MARGIN,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
        "notes": "OpenCV descriptor matching with threshold and top-two ambiguity rejection, active session attendance marking, duplicate prevention, and challenge-response liveness verification.",
    }
