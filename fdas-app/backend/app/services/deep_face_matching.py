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
    DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID,
    DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED,
    DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_CONTROLLED_MATCH_THRESHOLD,
    DEEP_FACE_EMBEDDING_DIMENSION,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_MATCH_CALIBRATION_LABEL,
    DEEP_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_MATCH_SCORING_METHOD,
    DEEP_MATCH_THRESHOLD,
    DEEP_QUERY_BURST_COUNT,
    DEEP_QUERY_CONSENSUS_MIN_COUNT,
    DEEP_QUERY_MAX_RETRIES,
    DEEP_QUERY_MAX_BRIGHTNESS,
    DEEP_QUERY_MIN_BLUR_VARIANCE,
    DEEP_QUERY_MIN_BRIGHTNESS,
    DEEP_QUERY_MIN_EDGE_CLEARANCE_RATIO,
    DEEP_QUERY_MIN_FACE_AREA_RATIO,
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    DEEP_RECOGNITION_INTEGRATED_FOR_ATTENDANCE,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.models.user import User
from app.services.deep_face import DEEP_FACE_PROVIDER, DeepFaceInitializationError, get_deep_face_service
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


def controlled_attendance_student_capability(db: Session) -> dict:
    """Return the persisted readiness state for the one Phase 10.8 identity."""
    student = (
        db.query(Student)
        .filter(Student.studentId == DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID)
        .one_or_none()
    )
    valid_embedding_count = 0
    if student is not None:
        embedding_rows = (
            db.query(FaceTemplateEmbedding.embeddingData)
            .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
            .filter(
                FaceTemplateEmbedding.studentId == student.studentId,
                FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
                FaceTemplateEmbedding.isActive.is_(True),
                FaceTemplate.isActive.is_(True),
            )
            .all()
        )
        valid_embedding_count = sum(
            1 for (embedding_data,) in embedding_rows if parse_deep_embedding(embedding_data) is not None
        )

    student_ready = bool(
        student is not None
        and student.status == "Active"
        and valid_embedding_count >= DEEP_ENROLLMENT_MIN_EMBEDDINGS
    )
    return {
        "controlledAttendanceStudentId": DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID,
        "controlledAttendanceStudentName": student.fullName if student is not None else None,
        "controlledAttendanceStudentRollNo": student.rollNo if student is not None else None,
        "controlledAttendanceDepartmentId": student.departmentId if student is not None else None,
        "controlledAttendanceValidEmbeddingCount": valid_embedding_count,
        "controlledAttendanceStudentReady": student_ready,
    }


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


def _attendance_failure(status_value: str, message: str, **details) -> dict:
    result = {
        "matched": False,
        "status": status_value,
        "message": message,
        "studentId": None,
        "studentName": None,
        "rollNo": None,
        "classId": None,
        "className": None,
        "departmentId": None,
        "departmentName": None,
        "similarityScore": None,
        "secondSimilarityScore": None,
        "scoreMargin": None,
        "thresholdUsed": DEEP_MATCH_THRESHOLD,
        "requiredMargin": DEEP_MATCH_MIN_IDENTITY_MARGIN,
        "aggregationMethod": DEEP_MATCH_SCORING_METHOD,
        "recognitionProvider": DEEP_FACE_PROVIDER,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "topStudentId": None,
        "topStudentName": None,
        "topRollNo": None,
        "topScore": None,
        "secondStudentId": None,
        "secondStudentName": None,
        "secondRollNo": None,
        "secondScore": None,
        "queryCount": 0,
        "validQueryCount": 0,
        "consensusStudentId": None,
        "consensusCount": 0,
        "queryTopStudentIds": [],
        "queryTopScores": [],
        "queryQuality": [],
        "retryable": status_value in {
            "NoFaceDetected",
            "FaceDetectionMismatch",
            "PoorFaceQuality",
            "MatchBelowThreshold",
            "AmbiguousMatch",
            "QueryConsensusFailed",
        },
    }
    result.update(details)
    return result


def match_deep_face_query_burst_for_attendance(
    db: Session,
    current_user: User,
    department_id: int,
    image_bytes_list: list[bytes],
    *,
    threshold: float = DEEP_MATCH_THRESHOLD,
    required_margin: float = DEEP_MATCH_MIN_IDENTITY_MARGIN,
) -> dict:
    """Classify three fresh centered queries and require a 2-of-3 identity consensus."""
    ensure_department_access(current_user, department_id)
    query_count = len(image_bytes_list)
    if query_count != DEEP_QUERY_BURST_COUNT:
        return _attendance_failure(
            "InvalidQueryBurst",
            f"Exactly {DEEP_QUERY_BURST_COUNT} fresh recognition query images are required.",
            thresholdUsed=threshold,
            requiredMargin=required_margin,
            queryCount=query_count,
        )

    encodings = []
    qualities: list[dict] = []
    try:
        for index, image_bytes in enumerate(image_bytes_list, start=1):
            encoding = get_deep_face_service().encode_attendance_query_bytes(image_bytes)
            quality = dict(encoding.quality or {})
            quality.update(
                {
                    "queryIndex": index,
                    "status": encoding.status,
                    "haarFaceCount": encoding.haarFaceCount,
                    "deepFaceCount": encoding.deepFaceCount,
                    "haarBackgroundFalsePositiveReconciled": encoding.haarBackgroundFalsePositiveReconciled,
                }
            )
            qualities.append(quality)
            if not encoding.success or encoding.embedding is None:
                safe_status = encoding.status if encoding.status in {
                    "NoFaceDetected",
                    "MultipleFacesDetected",
                    "FaceDetectionMismatch",
                    "PoorFaceQuality",
                    "InvalidEmbedding",
                } else "DeepRecognitionUnavailable"
                return _attendance_failure(
                    safe_status,
                    encoding.message,
                    thresholdUsed=threshold,
                    requiredMargin=required_margin,
                    queryCount=query_count,
                    validQueryCount=len(encodings),
                    queryQuality=qualities,
                )
            encodings.append(encoding)
    except DeepFaceInitializationError as exc:
        return _attendance_failure(
            "DeepRecognitionUnavailable",
            f"Deep recognition is unavailable: {exc}",
            thresholdUsed=threshold,
            requiredMargin=required_margin,
            queryCount=query_count,
            validQueryCount=len(encodings),
            queryQuality=qualities,
        )
    except Exception:
        return _attendance_failure(
            "DeepRecognitionUnavailable",
            "Deep recognition could not process the query burst safely.",
            thresholdUsed=threshold,
            requiredMargin=required_margin,
            queryCount=query_count,
            validQueryCount=len(encodings),
            queryQuality=qualities,
        )

    candidates = load_deep_match_candidates(db, current_user, department_id)
    if not candidates:
        return _attendance_failure(
            "DeepEnrollmentIncomplete",
            "Face registration is incomplete. Please contact the administrator.",
            thresholdUsed=threshold,
            requiredMargin=required_margin,
            queryCount=query_count,
            validQueryCount=len(encodings),
            queryQuality=qualities,
        )

    rankings = [
        rank_deep_candidates(encoding.embedding, candidates, DEEP_MATCH_SCORING_METHOD)
        for encoding in encodings
    ]
    query_tops = [ranking[0] for ranking in rankings if ranking]
    if len(query_tops) != DEEP_QUERY_BURST_COUNT:
        return _attendance_failure(
            "DeepEnrollmentIncomplete",
            "Face registration is incomplete. Please contact the administrator.",
            thresholdUsed=threshold,
            requiredMargin=required_margin,
            queryCount=query_count,
            validQueryCount=len(encodings),
            queryQuality=qualities,
        )

    top_ids = [candidate.student.studentId for candidate in query_tops]
    top_scores = [candidate.score for candidate in query_tops]
    consensus_student_id, consensus_count = sorted(
        ((student_id, top_ids.count(student_id)) for student_id in set(top_ids)),
        key=lambda item: (-item[1], item[0]),
    )[0]

    by_student: dict[int, list[DeepStudentScore]] = {}
    for ranking in rankings:
        for candidate in ranking:
            by_student.setdefault(candidate.student.studentId, []).append(candidate)
    aggregate_ranked: list[DeepStudentScore] = []
    for student_scores in by_student.values():
        representative = max(student_scores, key=lambda item: item.score)
        aggregate_ranked.append(
            DeepStudentScore(
                student=representative.student,
                score=round(float(statistics.median(item.score for item in student_scores)), 6),
                bestTemplateId=representative.bestTemplateId,
                bestEmbeddingId=representative.bestEmbeddingId,
                templatesEvaluated=representative.templatesEvaluated,
            )
        )
    aggregate_ranked.sort(key=lambda item: (-item.score, item.student.studentId))
    top = aggregate_ranked[0]
    second = aggregate_ranked[1] if len(aggregate_ranked) > 1 else None
    margin = round(top.score - second.score, 6) if second is not None else None
    top_above_threshold = top.score >= threshold
    margin_passed = margin is None or margin >= required_margin
    consensus_passed = (
        consensus_count >= DEEP_QUERY_CONSENSUS_MIN_COUNT
        and consensus_student_id == top.student.studentId
    )

    common = {
        "queryCount": query_count,
        "validQueryCount": len(encodings),
        "consensusStudentId": consensus_student_id,
        "consensusCount": consensus_count,
        "queryTopStudentIds": top_ids,
        "queryTopScores": top_scores,
        "queryQuality": qualities,
        "topStudentId": top.student.studentId,
        "topStudentName": top.student.fullName,
        "topRollNo": top.student.rollNo,
        "topScore": top.score,
        "secondStudentId": second.student.studentId if second else None,
        "secondStudentName": second.student.fullName if second else None,
        "secondRollNo": second.student.rollNo if second else None,
        "secondScore": second.score if second else None,
        "similarityScore": top.score,
        "secondSimilarityScore": second.score if second else None,
        "scoreMargin": margin,
        "candidateStudentCount": len(aggregate_ranked),
        "candidateEmbeddingCount": len(candidates),
    }
    if not consensus_passed:
        return _attendance_failure(
            "QueryConsensusFailed",
            "The fresh query images did not agree on one identity in at least two of three captures.",
            thresholdUsed=threshold,
            requiredMargin=required_margin,
            **common,
        )
    if not top_above_threshold:
        return _attendance_failure(
            "MatchBelowThreshold",
            "Face could not be verified under the production deep-recognition policy.",
            thresholdUsed=threshold,
            requiredMargin=required_margin,
            **common,
        )
    if not margin_passed:
        return _attendance_failure(
            "AmbiguousMatch",
            "The top two median identity scores are too close for a safe match.",
            thresholdUsed=threshold,
            requiredMargin=required_margin,
            **common,
        )

    student = top.student
    return {
        "matched": True,
        "status": "DeepMatched",
        "message": "ArcFace identity passed the three-query consensus attendance rule.",
        "studentId": student.studentId,
        "studentName": student.fullName,
        "rollNo": student.rollNo,
        "classId": student.classId,
        "className": student.classroom.className if student.classroom else None,
        "departmentId": student.departmentId,
        "departmentName": student.department.departmentName if student.department else None,
        "thresholdUsed": threshold,
        "requiredMargin": required_margin,
        "aggregationMethod": f"median_of_{DEEP_QUERY_BURST_COUNT}_{DEEP_MATCH_SCORING_METHOD}",
        "recognitionProvider": DEEP_FACE_PROVIDER,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "retryable": False,
        **common,
    }


def match_deep_face_bytes_for_attendance(
    db: Session,
    current_user: User,
    department_id: int,
    image_bytes: bytes,
) -> dict:
    """Run the fail-closed ArcFace-only identity decision after liveness succeeds."""
    ensure_department_access(current_user, department_id)
    try:
        encoding = get_deep_face_service().encode_image_bytes(image_bytes)
    except DeepFaceInitializationError as exc:
        return _attendance_failure(
            "DeepRecognitionUnavailable",
            f"Deep recognition is unavailable: {exc}",
        )
    except Exception:
        return _attendance_failure(
            "DeepRecognitionUnavailable",
            "Deep recognition could not be initialized safely.",
        )

    if not encoding.success or encoding.embedding is None:
        safe_status = encoding.status
        if safe_status not in {
            "NoFaceDetected",
            "MultipleFacesDetected",
            "FaceDetectionMismatch",
            "InvalidEmbedding",
        }:
            safe_status = "DeepRecognitionUnavailable"
        return _attendance_failure(safe_status, encoding.message)

    candidates = load_deep_match_candidates(db, current_user, department_id)
    if not candidates:
        return _attendance_failure(
            "DeepEnrollmentIncomplete",
            "Face registration is incomplete. Please contact the administrator.",
        )

    classified = classify_deep_embedding(encoding.embedding, candidates)
    top = classified.get("topCandidate") or {}
    second = classified.get("secondCandidate") or {}
    matched = classified.get("status") == "DiagnosticMatched" and classified.get("matched") is True
    status_value = "DeepMatched" if matched else str(classified.get("status") or "DeepRecognitionUnavailable")
    student = (
        db.query(Student).filter(Student.studentId == top.get("studentId")).one_or_none()
        if matched and isinstance(top.get("studentId"), int)
        else None
    )
    if matched and student is None:
        return _attendance_failure("DeepRecognitionUnavailable", "The matched deep identity record is unavailable.")

    return {
        "matched": matched,
        "status": status_value,
        "message": (
            "ArcFace identity passed the deep attendance rule."
            if matched
            else classified.get("message", "Deep recognition did not produce a safe match.")
        ),
        "studentId": student.studentId if student else None,
        "studentName": student.fullName if student else None,
        "rollNo": student.rollNo if student else None,
        "classId": student.classId if student else None,
        "className": student.classroom.className if student and student.classroom else None,
        "departmentId": student.departmentId if student else department_id,
        "departmentName": student.department.departmentName if student and student.department else None,
        "similarityScore": top.get("score"),
        "secondSimilarityScore": second.get("score"),
        "scoreMargin": classified.get("scoreMargin"),
        "thresholdUsed": classified.get("thresholdUsed", DEEP_MATCH_THRESHOLD),
        "requiredMargin": classified.get("requiredMargin", DEEP_MATCH_MIN_IDENTITY_MARGIN),
        "aggregationMethod": classified.get("scoringMethod", DEEP_MATCH_SCORING_METHOD),
        "recognitionProvider": DEEP_FACE_PROVIDER,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "topStudentId": top.get("studentId"),
        "topStudentName": top.get("studentName"),
        "topRollNo": top.get("rollNo"),
        "topScore": top.get("score"),
        "secondStudentId": second.get("studentId"),
        "secondStudentName": second.get("studentName"),
        "secondRollNo": second.get("rollNo"),
        "secondScore": second.get("score"),
        "candidateStudentCount": classified.get("candidateStudentCount", 0),
        "candidateEmbeddingCount": classified.get("candidateEmbeddingCount", 0),
    }


def deep_matching_policy() -> dict:
    return {
        "diagnosticMatchingImplemented": True,
        "scoringMethod": DEEP_MATCH_SCORING_METHOD,
        "threshold": DEEP_MATCH_THRESHOLD,
        "requiredIdentityMargin": DEEP_MATCH_MIN_IDENTITY_MARGIN,
        "calibrationLabel": DEEP_MATCH_CALIBRATION_LABEL,
        "eligibleEmbeddingMinimum": DEEP_ENROLLMENT_MIN_EMBEDDINGS,
        "integratedForAttendance": DEEP_RECOGNITION_INTEGRATED_FOR_ATTENDANCE,
        "activeForAttendance": DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
        "controlledAttendanceEnabled": DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED,
        "controlledAttendanceStudentId": DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID,
        "controlledMatchingThreshold": DEEP_CONTROLLED_MATCH_THRESHOLD,
        "controlledRequiredIdentityMargin": DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
        "queryBurstCount": DEEP_QUERY_BURST_COUNT,
        "queryConsensusMinimum": DEEP_QUERY_CONSENSUS_MIN_COUNT,
        "maximumRecognitionRetries": DEEP_QUERY_MAX_RETRIES,
        "queryMinimumFaceAreaRatio": DEEP_QUERY_MIN_FACE_AREA_RATIO,
        "queryMinimumBlurVariance": DEEP_QUERY_MIN_BLUR_VARIANCE,
        "queryMinimumBrightness": DEEP_QUERY_MIN_BRIGHTNESS,
        "queryMaximumBrightness": DEEP_QUERY_MAX_BRIGHTNESS,
        "queryMinimumEdgeClearanceRatio": DEEP_QUERY_MIN_EDGE_CLEARANCE_RATIO,
    }
