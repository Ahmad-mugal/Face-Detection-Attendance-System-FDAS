from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import (
    DEEP_ENROLLMENT_MIN_EMBEDDINGS,
    DEEP_FACE_EMBEDDING_DIMENSION,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_MATCH_CALIBRATION_LABEL,
    DEEP_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_MATCH_SCORING_METHOD,
    DEEP_MATCH_THRESHOLD,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.models.user import User
from app.services.deep_face import get_deep_face_service
from app.services.departments import ensure_department_access
from app.services.students import ensure_student_access, get_student_or_404


DEEP_SCORING_METHODS = (
    "maximum",
    "mean_top_3",
    "mean_top_5",
    "median_top_5",
    "prototype",
)


@dataclass(frozen=True)
class DeepMatchCandidate:
    embedding: FaceTemplateEmbedding
    template: FaceTemplate
    student: Student
    vector: np.ndarray


@dataclass(frozen=True)
class DeepStudentScore:
    student: Student
    score: float
    bestTemplateId: int
    bestEmbeddingId: int
    templatesEvaluated: int


def parse_deep_embedding(embedding_data: str | None) -> np.ndarray | None:
    if not embedding_data:
        return None
    try:
        raw = json.loads(embedding_data)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, list) or len(raw) != DEEP_FACE_EMBEDDING_DIMENSION:
        return None
    try:
        vector = np.asarray(raw, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError):
        return None
    if vector.size != DEEP_FACE_EMBEDDING_DIMENSION or not np.all(np.isfinite(vector)):
        return None
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0 or not np.isfinite(norm):
        return None
    return vector / norm


def _eligible_student_ids(db: Session, department_id: int):
    return (
        db.query(FaceTemplateEmbedding.studentId.label("studentId"))
        .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
        .join(Student, Student.studentId == FaceTemplateEmbedding.studentId)
        .filter(
            Student.departmentId == department_id,
            Student.status == "Active",
            FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
            FaceTemplateEmbedding.isActive.is_(True),
            FaceTemplate.isActive.is_(True),
        )
        .group_by(FaceTemplateEmbedding.studentId)
        .having(func.count(FaceTemplateEmbedding.faceTemplateEmbeddingId) >= DEEP_ENROLLMENT_MIN_EMBEDDINGS)
        .subquery()
    )


def load_deep_match_candidates(
    db: Session,
    current_user: User,
    department_id: int,
) -> list[DeepMatchCandidate]:
    ensure_department_access(current_user, department_id)
    eligible_ids = _eligible_student_ids(db, department_id)
    rows = (
        db.query(FaceTemplateEmbedding, FaceTemplate, Student)
        .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
        .join(Student, Student.studentId == FaceTemplateEmbedding.studentId)
        .filter(
            Student.departmentId == department_id,
            Student.status == "Active",
            FaceTemplateEmbedding.studentId.in_(select(eligible_ids.c.studentId)),
            FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
            FaceTemplateEmbedding.isActive.is_(True),
            FaceTemplate.isActive.is_(True),
        )
        .order_by(
            FaceTemplateEmbedding.studentId,
            FaceTemplateEmbedding.faceTemplateEmbeddingId,
        )
        .all()
    )

    candidates: list[DeepMatchCandidate] = []
    for embedding, template, student in rows:
        vector = parse_deep_embedding(embedding.embeddingData)
        if vector is None:
            continue
        candidates.append(
            DeepMatchCandidate(
                embedding=embedding,
                template=template,
                student=student,
                vector=vector,
            )
        )
    return candidates


def exclude_query_leakage(
    candidates: list[DeepMatchCandidate],
    *,
    excluded_embedding_id: int | None = None,
    excluded_source_sha256: str | None = None,
) -> tuple[list[DeepMatchCandidate], int]:
    filtered: list[DeepMatchCandidate] = []
    excluded_count = 0
    for candidate in candidates:
        same_row = (
            excluded_embedding_id is not None
            and candidate.embedding.faceTemplateEmbeddingId == excluded_embedding_id
        )
        same_source = (
            bool(excluded_source_sha256)
            and candidate.embedding.sourceImageSha256 == excluded_source_sha256
        )
        if same_row or same_source:
            excluded_count += 1
            continue
        filtered.append(candidate)
    return filtered, excluded_count


def cosine_similarity(query_vector: np.ndarray, candidate_vector: np.ndarray) -> float:
    return float(np.dot(query_vector, candidate_vector))


def calculate_deep_identity_score(
    query_vector: np.ndarray,
    candidates: list[DeepMatchCandidate],
    method: str,
) -> tuple[float, DeepMatchCandidate]:
    if method not in DEEP_SCORING_METHODS:
        raise ValueError(f"Unsupported deep scoring method: {method}")
    if not candidates:
        raise ValueError("At least one deep candidate is required")

    scored = sorted(
        ((cosine_similarity(query_vector, candidate.vector), candidate) for candidate in candidates),
        key=lambda item: (-item[0], item[1].embedding.faceTemplateEmbeddingId),
    )
    similarities = [score for score, _candidate in scored]
    if method == "maximum":
        score = similarities[0]
    elif method == "mean_top_3":
        score = statistics.fmean(similarities[:3])
    elif method == "mean_top_5":
        score = statistics.fmean(similarities[:5])
    elif method == "median_top_5":
        score = statistics.median(similarities[:5])
    else:
        prototype = np.mean([candidate.vector for candidate in candidates], axis=0)
        prototype_norm = float(np.linalg.norm(prototype))
        score = cosine_similarity(query_vector, prototype / prototype_norm) if prototype_norm > 0 else -1.0
    return round(float(score), 6), scored[0][1]


def rank_deep_candidates(
    query_vector: np.ndarray,
    candidates: list[DeepMatchCandidate],
    method: str = DEEP_MATCH_SCORING_METHOD,
) -> list[DeepStudentScore]:
    normalized_query = np.asarray(query_vector, dtype=np.float64).reshape(-1)
    if normalized_query.size != DEEP_FACE_EMBEDDING_DIMENSION or not np.all(np.isfinite(normalized_query)):
        raise ValueError("Query embedding is invalid")
    query_norm = float(np.linalg.norm(normalized_query))
    if query_norm <= 0.0 or not np.isfinite(query_norm):
        raise ValueError("Query embedding is invalid")
    normalized_query = normalized_query / query_norm

    by_student: dict[int, list[DeepMatchCandidate]] = {}
    for candidate in candidates:
        by_student.setdefault(candidate.student.studentId, []).append(candidate)

    ranked: list[DeepStudentScore] = []
    for student_candidates in by_student.values():
        score, best_candidate = calculate_deep_identity_score(
            normalized_query,
            student_candidates,
            method,
        )
        ranked.append(
            DeepStudentScore(
                student=best_candidate.student,
                score=score,
                bestTemplateId=best_candidate.template.templateId,
                bestEmbeddingId=best_candidate.embedding.faceTemplateEmbeddingId,
                templatesEvaluated=len(student_candidates),
            )
        )
    ranked.sort(key=lambda item: (-item.score, item.student.studentId))
    return ranked


def _candidate_result(candidate: DeepStudentScore | None) -> dict | None:
    if candidate is None:
        return None
    return {
        "studentId": candidate.student.studentId,
        "studentName": candidate.student.fullName,
        "rollNo": candidate.student.rollNo,
        "score": candidate.score,
        "bestTemplateId": candidate.bestTemplateId,
        "bestEmbeddingId": candidate.bestEmbeddingId,
        "templatesEvaluated": candidate.templatesEvaluated,
    }


def _base_diagnostic_result(*, status_value: str, message: str) -> dict:
    return {
        "matched": False,
        "status": status_value,
        "message": message,
        "attendanceCreated": False,
        "persistentWrite": False,
        "activeForAttendance": False,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "calibrationLabel": DEEP_MATCH_CALIBRATION_LABEL,
        "scoringMethod": DEEP_MATCH_SCORING_METHOD,
        "thresholdUsed": DEEP_MATCH_THRESHOLD,
        "requiredMargin": DEEP_MATCH_MIN_IDENTITY_MARGIN,
        "candidateStudentCount": 0,
        "candidateEmbeddingCount": 0,
        "excludedCandidateCount": 0,
        "expectedStudentId": None,
        "expectedStudentScore": None,
        "topCandidate": None,
        "secondCandidate": None,
        "scoreMargin": None,
        "topAboveThreshold": False,
        "marginPassed": False,
    }


def classify_deep_embedding(
    query_vector: np.ndarray,
    candidates: list[DeepMatchCandidate],
    *,
    expected_student_id: int | None = None,
    excluded_embedding_id: int | None = None,
    excluded_source_sha256: str | None = None,
    method: str = DEEP_MATCH_SCORING_METHOD,
    threshold: float = DEEP_MATCH_THRESHOLD,
    required_margin: float = DEEP_MATCH_MIN_IDENTITY_MARGIN,
) -> dict:
    filtered, excluded_count = exclude_query_leakage(
        candidates,
        excluded_embedding_id=excluded_embedding_id,
        excluded_source_sha256=excluded_source_sha256,
    )
    ranked = rank_deep_candidates(query_vector, filtered, method)
    if not ranked:
        result = _base_diagnostic_result(
            status_value="NoEligibleDeepStudents",
            message="No calibration-ready deep enrollment galleries are available in this scope.",
        )
        result.update(
            {
                "scoringMethod": method,
                "thresholdUsed": threshold,
                "requiredMargin": required_margin,
                "excludedCandidateCount": excluded_count,
                "expectedStudentId": expected_student_id,
            }
        )
        return result

    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    margin = round(top.score - second.score, 6) if second is not None else None
    expected = next(
        (item for item in ranked if item.student.studentId == expected_student_id),
        None,
    )
    top_above_threshold = top.score >= threshold
    margin_passed = margin is None or margin >= required_margin
    if not top_above_threshold:
        status_value = "MatchBelowThreshold"
        message = "The best deep identity score is below the preliminary threshold."
        matched = False
    elif not margin_passed:
        status_value = "AmbiguousMatch"
        message = "The top two deep identity scores are too close for a safe diagnostic match."
        matched = False
    else:
        status_value = "DiagnosticMatched"
        message = "A preliminary deep identity candidate passed the diagnostic-only rule."
        matched = True

    return {
        "matched": matched,
        "status": status_value,
        "message": message,
        "attendanceCreated": False,
        "persistentWrite": False,
        "activeForAttendance": False,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "calibrationLabel": DEEP_MATCH_CALIBRATION_LABEL,
        "scoringMethod": method,
        "thresholdUsed": threshold,
        "requiredMargin": required_margin,
        "candidateStudentCount": len(ranked),
        "candidateEmbeddingCount": len(filtered),
        "excludedCandidateCount": excluded_count,
        "expectedStudentId": expected_student_id,
        "expectedStudentScore": expected.score if expected is not None else None,
        "topCandidate": _candidate_result(top),
        "secondCandidate": _candidate_result(second),
        "scoreMargin": margin,
        "topAboveThreshold": top_above_threshold,
        "marginPassed": margin_passed,
    }


def diagnose_deep_face_bytes(
    db: Session,
    current_user: User,
    department_id: int,
    expected_student_id: int | None,
    image_bytes: bytes,
) -> dict:
    ensure_department_access(current_user, department_id)
    if expected_student_id is not None:
        expected_student = get_student_or_404(db, expected_student_id)
        ensure_student_access(current_user, expected_student)
        if expected_student.departmentId != department_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Expected student is not in the selected department",
            )

    encoding = get_deep_face_service().encode_image_bytes(image_bytes)
    if not encoding.success or encoding.embedding is None:
        result = _base_diagnostic_result(
            status_value=encoding.status,
            message=encoding.message,
        )
        result["expectedStudentId"] = expected_student_id
        return result

    candidates = load_deep_match_candidates(db, current_user, department_id)
    return classify_deep_embedding(
        encoding.embedding,
        candidates,
        expected_student_id=expected_student_id,
        excluded_source_sha256=hashlib.sha256(image_bytes).hexdigest(),
    )


def deep_matching_policy() -> dict:
    return {
        "diagnosticMatchingImplemented": True,
        "scoringMethod": DEEP_MATCH_SCORING_METHOD,
        "threshold": DEEP_MATCH_THRESHOLD,
        "requiredIdentityMargin": DEEP_MATCH_MIN_IDENTITY_MARGIN,
        "calibrationLabel": DEEP_MATCH_CALIBRATION_LABEL,
        "eligibleEmbeddingMinimum": DEEP_ENROLLMENT_MIN_EMBEDDINGS,
        "activeForAttendance": False,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
    }
