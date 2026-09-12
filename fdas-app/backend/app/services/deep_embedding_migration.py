from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

import numpy as np
from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import (
    DEEP_FACE_EMBEDDING_DIMENSION,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_FACE_EXECUTION_PROVIDER,
    DEEP_FACE_MODEL_NAME,
    DEEP_ENROLLMENT_MIN_EMBEDDINGS,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.models.attendance_record import AttendanceRecord
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.services.deep_face import DeepEncodingResult, get_deep_face_service, resolve_template_image_path


MIGRATION_STATUSES = (
    "EncodedSuccessfully",
    "NoFaceDetected",
    "MultipleFacesDetected",
    "FaceDetectionMismatch",
    "MissingFile",
    "UnreadableImage",
    "EmbeddingError",
)
Encoder = Callable[[bytes], DeepEncodingResult]


def embedding_table_exists(db: Session) -> bool:
    return inspect(db.get_bind()).has_table(FaceTemplateEmbedding.__tablename__)


def create_embedding_table(engine) -> None:
    FaceTemplateEmbedding.__table__.create(bind=engine, checkfirst=True)


def serialize_embedding(embedding: np.ndarray) -> str:
    values = np.asarray(embedding, dtype=np.float32).reshape(-1)
    if values.size != DEEP_FACE_EMBEDDING_DIMENSION or not np.all(np.isfinite(values)):
        raise ValueError("Deep embedding must contain exactly 512 finite values")
    norm = float(np.linalg.norm(values))
    if abs(norm - 1.0) > 0.001:
        raise ValueError(f"Deep embedding must be L2 normalized; norm was {norm}")
    return json.dumps(values.astype(float).tolist(), separators=(",", ":"))


def _result(
    template: FaceTemplate,
    status: str,
    *,
    image_found: bool,
    processing_milliseconds: float = 0.0,
    embedding: np.ndarray | None = None,
    source_sha256: str | None = None,
) -> dict:
    return {
        "templateId": template.templateId,
        "studentId": template.studentId,
        "status": status,
        "imageFound": image_found,
        "processingMilliseconds": round(processing_milliseconds, 3),
        "embedding": embedding,
        "sourceImageSha256": source_sha256,
    }


def analyze_template(template: FaceTemplate, encoder: Encoder | None = None) -> dict:
    started = time.perf_counter()
    try:
        image_path = resolve_template_image_path(template)
    except HTTPException:
        return _result(
            template,
            "EmbeddingError",
            image_found=False,
            processing_milliseconds=(time.perf_counter() - started) * 1000.0,
        )

    if image_path is None or not image_path.is_file():
        return _result(
            template,
            "MissingFile",
            image_found=False,
            processing_milliseconds=(time.perf_counter() - started) * 1000.0,
        )

    try:
        image_bytes = image_path.read_bytes()
    except OSError:
        return _result(
            template,
            "UnreadableImage",
            image_found=True,
            processing_milliseconds=(time.perf_counter() - started) * 1000.0,
        )
    if not image_bytes:
        return _result(
            template,
            "UnreadableImage",
            image_found=True,
            processing_milliseconds=(time.perf_counter() - started) * 1000.0,
        )

    source_sha256 = hashlib.sha256(image_bytes).hexdigest()
    try:
        deep_result = (encoder or get_deep_face_service().encode_image_bytes)(image_bytes)
    except HTTPException:
        return _result(
            template,
            "UnreadableImage",
            image_found=True,
            processing_milliseconds=(time.perf_counter() - started) * 1000.0,
            source_sha256=source_sha256,
        )
    except Exception:
        return _result(
            template,
            "EmbeddingError",
            image_found=True,
            processing_milliseconds=(time.perf_counter() - started) * 1000.0,
            source_sha256=source_sha256,
        )

    status_name = "EncodedSuccessfully" if deep_result.success else deep_result.status
    if status_name not in MIGRATION_STATUSES:
        status_name = "EmbeddingError"
    embedding = deep_result.embedding if status_name == "EncodedSuccessfully" else None
    if status_name == "EncodedSuccessfully":
        try:
            serialize_embedding(embedding)
        except (TypeError, ValueError):
            status_name = "EmbeddingError"
            embedding = None
    return _result(
        template,
        status_name,
        image_found=True,
        processing_milliseconds=(time.perf_counter() - started) * 1000.0,
        embedding=embedding,
        source_sha256=source_sha256,
    )


def _persistent_counts(db: Session) -> dict[int, int]:
    if not embedding_table_exists(db):
        return {}
    rows = (
        db.query(FaceTemplateEmbedding.studentId, FaceTemplateEmbedding.faceTemplateEmbeddingId)
        .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
        .filter(
            FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
            FaceTemplateEmbedding.isActive.is_(True),
            FaceTemplate.isActive.is_(True),
        )
        .all()
    )
    counts: Counter[int] = Counter(int(row.studentId) for row in rows)
    return dict(counts)


def _existing_keys(db: Session) -> set[tuple[int, str]]:
    if not embedding_table_exists(db):
        return set()
    return {
        (int(row.faceTemplateId), str(row.encodingVersion))
        for row in db.query(
            FaceTemplateEmbedding.faceTemplateId,
            FaceTemplateEmbedding.encodingVersion,
        ).all()
    }


def _student_status(
    *,
    valid_count: int,
    minimum: int,
    existing_files: int,
    missing_files: int,
    failure_counts: Counter,
) -> tuple[str, bool]:
    if valid_count >= minimum:
        return "Ready", False
    if existing_files == 0 and missing_files > 0:
        return "SourceImagesMissing", True
    re_enrollment_recommended = bool(
        failure_counts["MultipleFacesDetected"]
        or failure_counts["NoFaceDetected"]
        or failure_counts["FaceDetectionMismatch"]
        or failure_counts["UnreadableImage"]
        or failure_counts["EmbeddingError"]
    )
    return "DeepEnrollmentIncomplete", re_enrollment_recommended


def run_migration(
    db: Session,
    *,
    apply: bool,
    student_id: int | None = None,
    minimum_embeddings: int = DEEP_ENROLLMENT_MIN_EMBEDDINGS,
    encoder: Encoder | None = None,
    show_progress: bool = True,
) -> dict:
    if minimum_embeddings <= 0:
        raise ValueError("minimum_embeddings must be positive")
    if apply and not embedding_table_exists(db):
        raise RuntimeError("Embedding table must be created before apply mode")

    template_query = (
        db.query(FaceTemplate)
        .filter(FaceTemplate.isActive.is_(True))
        .order_by(FaceTemplate.studentId, FaceTemplate.sampleIndex, FaceTemplate.templateId)
    )
    if student_id is not None:
        template_query = template_query.filter(FaceTemplate.studentId == student_id)
    templates = template_query.all()

    student_ids = sorted({int(template.studentId) for template in templates})
    students = {
        int(student.studentId): student
        for student in db.query(Student).filter(Student.studentId.in_(student_ids)).all()
    } if student_ids else {}
    existing_keys = _existing_keys(db)
    attendance_before = db.query(AttendanceRecord).count()
    started = time.perf_counter()
    results: list[dict] = []
    created = 0
    already_migrated = 0

    for index, template in enumerate(templates, start=1):
        key = (int(template.templateId), DEEP_FACE_ENCODING_VERSION)
        if apply and key in existing_keys:
            already_migrated += 1
            results.append(
                _result(template, "AlreadyMigrated", image_found=bool(template.templatePath))
            )
            continue

        image_result = analyze_template(template, encoder=encoder)
        results.append(image_result)
        embedding = image_result.pop("embedding")
        if apply and image_result["status"] == "EncodedSuccessfully":
            row = FaceTemplateEmbedding(
                faceTemplateId=template.templateId,
                studentId=template.studentId,
                encodingVersion=DEEP_FACE_ENCODING_VERSION,
                embeddingData=serialize_embedding(embedding),
                embeddingDimension=DEEP_FACE_EMBEDDING_DIMENSION,
                modelName=DEEP_FACE_MODEL_NAME,
                sourceImageSha256=image_result["sourceImageSha256"],
                l2Norm=1.0,
                processingMilliseconds=image_result["processingMilliseconds"],
                isActive=True,
            )
            try:
                db.add(row)
                db.commit()
                created += 1
                existing_keys.add(key)
            except IntegrityError:
                db.rollback()
                already_migrated += 1
                image_result["status"] = "AlreadyMigrated"
            except Exception:
                db.rollback()
                image_result["status"] = "EmbeddingError"

        if show_progress and (index == len(templates) or index % 25 == 0):
            print(
                f"processed={index}/{len(templates)} mode={'apply' if apply else 'dry-run'}",
                file=sys.stderr,
                flush=True,
            )

    attendance_after = db.query(AttendanceRecord).count()
    if attendance_before != attendance_after:
        raise RuntimeError("Attendance row count changed during deep embedding migration")

    persistent_counts = _persistent_counts(db)
    by_student_results: dict[int, list[dict]] = defaultdict(list)
    for item in results:
        by_student_results[int(item["studentId"])].append(item)

    student_summaries = []
    for current_student_id in student_ids:
        student = students[current_student_id]
        student_results = by_student_results[current_student_id]
        status_counts = Counter(item["status"] for item in student_results)
        existing_files = sum(1 for item in student_results if item["imageFound"])
        missing_files = status_counts["MissingFile"]
        valid_count = (
            persistent_counts.get(current_student_id, 0)
            if apply
            else status_counts["EncodedSuccessfully"]
        )
        eligibility, re_enrollment = _student_status(
            valid_count=valid_count,
            minimum=minimum_embeddings,
            existing_files=existing_files,
            missing_files=missing_files,
            failure_counts=status_counts,
        )
        student_summaries.append(
            {
                "studentId": current_student_id,
                "name": student.fullName,
                "rollNo": student.rollNo,
                "activeTemplateRows": len(student_results),
                "linkedImagesExisting": existing_files,
                "linkedImagesMissing": missing_files,
                "legacyEncodings": sum(
                    1
                    for template in templates
                    if template.studentId == current_student_id
                    and template.encodingVersion == "opencv_basic_v1"
                    and bool(template.encodingData)
                ),
                "validDeepEmbeddings": valid_count,
                "requiredMinimum": minimum_embeddings,
                "deepEligibility": eligibility,
                "reEnrollmentRecommended": re_enrollment,
                "counts": {status_name: status_counts[status_name] for status_name in MIGRATION_STATUSES},
                "alreadyMigrated": status_counts["AlreadyMigrated"],
            }
        )

    aggregate_counts = Counter(item["status"] for item in results)
    total_failures = sum(aggregate_counts[name] for name in MIGRATION_STATUSES if name != "EncodedSuccessfully")
    candidate_readiness = {
        str(candidate): sum(
            1
            for summary in student_summaries
            if summary["validDeepEmbeddings"] >= candidate
        )
        for candidate in (10, 15, 20)
    }
    return {
        "mode": "apply" if apply else "dry-run",
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "model": DEEP_FACE_MODEL_NAME,
        "executionProvider": DEEP_FACE_EXECUTION_PROVIDER,
        "embeddingDimension": DEEP_FACE_EMBEDDING_DIMENSION,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
        "activeForAttendance": False,
        "studentFilter": student_id,
        "studentsWithActiveEnrollment": len(student_ids),
        "totalImagesEvaluated": len(results),
        "counts": {status_name: aggregate_counts[status_name] for status_name in MIGRATION_STATUSES},
        "alreadyMigrated": already_migrated,
        "totalFailures": total_failures,
        "persistentEmbeddingsCreated": created,
        "persistentEmbeddingCount": sum(persistent_counts.values()),
        "minimumDeepEmbeddings": minimum_embeddings,
        "studentsReadyByCandidateMinimum": candidate_readiness,
        "studentsReady": sum(1 for summary in student_summaries if summary["deepEligibility"] == "Ready"),
        "students": student_summaries,
        "attendanceRowsBefore": attendance_before,
        "attendanceRowsAfter": attendance_after,
        "processingSeconds": round(time.perf_counter() - started, 3),
    }
