from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import (
    DEEP_ENROLLMENT_MIN_EMBEDDINGS,
    DEEP_FACE_EMBEDDING_DIMENSION,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_FACE_MODEL_NAME,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.models.user import User
from app.services.deep_embedding_migration import embedding_table_exists, serialize_embedding
from app.services.deep_face import get_deep_face_service, resolve_template_image_path
from app.services.face_enrollment import (
    DEEP_RECOVERY_TEMPLATE_STATUS,
    FACE_ENROLLMENT_SAMPLE_COUNT,
    STORAGE_ABSOLUTE_ROOT,
    STORAGE_RELATIVE_ROOT,
    ensure_enrollment_face_continuity,
    ensure_exactly_one_face,
    next_sample_index,
)
from app.services.face_processing import process_image_bytes
from app.services.students import ensure_student_access, get_student_or_404
from app.utils.time import utc_now_naive


@dataclass(frozen=True)
class RecoveryUpload:
    suffix: str
    content: bytes


def count_student_deep_embeddings(db: Session, student_id: int) -> int:
    if not embedding_table_exists(db):
        return 0
    return (
        db.query(func.count(FaceTemplateEmbedding.faceTemplateEmbeddingId))
        .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
        .filter(
            FaceTemplateEmbedding.studentId == student_id,
            FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
            FaceTemplateEmbedding.isActive.is_(True),
            FaceTemplate.isActive.is_(True),
        )
        .scalar()
        or 0
    )


def _existing_source_file_counts(student: Student) -> tuple[int, int]:
    existing = 0
    missing = 0
    for template in student.faceTemplates:
        if not template.isActive or template.status == DEEP_RECOVERY_TEMPLATE_STATUS:
            continue
        try:
            path = resolve_template_image_path(template)
        except HTTPException:
            missing += 1
            continue
        if path is not None and path.is_file():
            existing += 1
        else:
            missing += 1
    return existing, missing


def deep_enrollment_readiness(db: Session, user: User, student_id: int) -> dict:
    student = get_student_or_404(db, student_id)
    ensure_student_access(user, student)
    deep_count = count_student_deep_embeddings(db, student_id)
    existing_files, missing_files = _existing_source_file_counts(student)
    if deep_count >= DEEP_ENROLLMENT_MIN_EMBEDDINGS:
        readiness = "Ready"
    elif existing_files == 0 and missing_files > 0:
        readiness = "SourceImagesMissing"
    else:
        readiness = "NeedsAdditionalSamples"
    return {
        "studentId": student.studentId,
        "studentName": student.fullName,
        "rollNo": student.rollNo,
        "validDeepEmbeddings": deep_count,
        "requiredMinimum": DEEP_ENROLLMENT_MIN_EMBEDDINGS,
        "additionalNeeded": max(0, DEEP_ENROLLMENT_MIN_EMBEDDINGS - deep_count),
        "readiness": readiness,
        "existingHistoricalImages": existing_files,
        "missingHistoricalImages": missing_files,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
        "activeForAttendance": False,
    }


def _build_recovery_path(student_id: int, sample_index: int, suffix: str) -> tuple[Path, Path]:
    timestamp = utc_now_naive().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"recovery_{timestamp}_{sample_index:03d}_{uuid4().hex[:8]}{suffix}"
    relative = STORAGE_RELATIVE_ROOT / str(student_id) / "recovery" / filename
    return relative, STORAGE_ABSOLUTE_ROOT / str(student_id) / "recovery" / filename


def create_deep_recovery_enrollment(
    db: Session,
    user: User,
    student_id: int,
    uploads: list[RecoveryUpload],
) -> dict:
    if not uploads or len(uploads) > FACE_ENROLLMENT_SAMPLE_COUNT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "InvalidRecoverySampleCount",
                "message": f"Provide between 1 and {FACE_ENROLLMENT_SAMPLE_COUNT} recovery samples.",
            },
        )
    if not embedding_table_exists(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DeepEmbeddingStorageUnavailable",
                "message": "Deep embedding storage is unavailable. Recovery stopped safely.",
            },
        )

    student = get_student_or_404(db, student_id)
    ensure_student_access(user, student)
    before_count = count_student_deep_embeddings(db, student_id)
    legacy_results = []
    deep_results = []
    source_hashes = []
    for upload in uploads:
        legacy_result = process_image_bytes(upload.content)
        ensure_exactly_one_face(legacy_result)
        deep_result = get_deep_face_service().encode_image_bytes(upload.content)
        if not deep_result.success or deep_result.embedding is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": deep_result.status,
                    "message": deep_result.message,
                },
            )
        legacy_results.append(legacy_result)
        deep_results.append(deep_result)
        source_hashes.append(hashlib.sha256(upload.content).hexdigest())

    ensure_enrollment_face_continuity(legacy_results)
    if len(set(source_hashes)) != len(source_hashes):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DuplicateRecoveryImage",
                "message": "The recovery batch contains duplicate image bytes.",
            },
        )
    existing_hashes = {
        row.sourceImageSha256
        for row in db.query(FaceTemplateEmbedding.sourceImageSha256)
        .filter(
            FaceTemplateEmbedding.studentId == student_id,
            FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
        )
        .all()
    }
    duplicate_hashes = sorted(set(source_hashes).intersection(existing_hashes))
    if duplicate_hashes:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DuplicateRecoveryImage",
                "message": "A recovery image is already represented by this student's deep enrollment.",
            },
        )

    sample_index = next_sample_index(db, student_id)
    created_files: list[Path] = []
    templates: list[FaceTemplate] = []
    embeddings: list[FaceTemplateEmbedding] = []
    try:
        for upload, legacy_result, deep_result, source_hash in zip(
            uploads,
            legacy_results,
            deep_results,
            source_hashes,
        ):
            relative_path, absolute_path = _build_recovery_path(student_id, sample_index, upload.suffix)
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            absolute_path.write_bytes(upload.content)
            created_files.append(absolute_path)

            template = FaceTemplate(
                studentId=student_id,
                templatePath=relative_path.as_posix(),
                encodingData=None,
                encodingVersion=None,
                faceBoxJson=legacy_result.faceBoxJson,
                sampleIndex=sample_index,
                status=DEEP_RECOVERY_TEMPLATE_STATUS,
                isActive=True,
                createdByUserId=user.userId,
                processedAt=utc_now_naive(),
            )
            db.add(template)
            db.flush()
            embedding = FaceTemplateEmbedding(
                faceTemplateId=template.templateId,
                studentId=student_id,
                encodingVersion=DEEP_FACE_ENCODING_VERSION,
                embeddingData=serialize_embedding(deep_result.embedding),
                embeddingDimension=DEEP_FACE_EMBEDDING_DIMENSION,
                modelName=DEEP_FACE_MODEL_NAME,
                sourceImageSha256=source_hash,
                l2Norm=float(deep_result.l2Norm or 1.0),
                processingMilliseconds=deep_result.processingMilliseconds,
                isActive=True,
            )
            db.add(embedding)
            templates.append(template)
            embeddings.append(embedding)
            sample_index += 1
        db.commit()
    except Exception:
        db.rollback()
        for path in created_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    for template in templates:
        db.refresh(template)
    for embedding in embeddings:
        db.refresh(embedding)
    after_count = count_student_deep_embeddings(db, student_id)
    return {
        "studentId": student_id,
        "studentName": student.fullName,
        "rollNo": student.rollNo,
        "deepCountBefore": before_count,
        "deepCountAfter": after_count,
        "requiredMinimum": DEEP_ENROLLMENT_MIN_EMBEDDINGS,
        "additionalNeeded": max(0, DEEP_ENROLLMENT_MIN_EMBEDDINGS - after_count),
        "readiness": "Ready" if after_count >= DEEP_ENROLLMENT_MIN_EMBEDDINGS else "NeedsAdditionalSamples",
        "recoveryTemplates": templates,
        "deepEmbeddingIds": [embedding.faceTemplateEmbeddingId for embedding in embeddings],
        "attendanceCreated": False,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
        "activeForAttendance": False,
    }
