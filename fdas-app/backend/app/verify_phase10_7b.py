from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.config import (
    DEEP_FACE_EMBEDDING_DIMENSION,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_FACE_MODEL_NAME,
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.database import Base
from app.models.attendance_record import AttendanceRecord
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.services import deep_embedding_migration as migration
from app.services.deep_face import DeepEncodingResult, deep_face_capability


LEGACY_VERSION = "opencv_basic_v1"


def controlled_result(status_name: str, success: bool = False) -> DeepEncodingResult:
    embedding = None
    if success:
        embedding = np.full(
            DEEP_FACE_EMBEDDING_DIMENSION,
            1.0 / math.sqrt(DEEP_FACE_EMBEDDING_DIMENSION),
            dtype=np.float32,
        )
    return DeepEncodingResult(
        success=success,
        status=status_name,
        message="controlled migration verifier result",
        haarFaceCount=1 if status_name not in {"NoFaceDetected", "MultipleFacesDetected"} else (0 if status_name == "NoFaceDetected" else 2),
        deepFaceCount=1 if success else None,
        embeddingDimension=DEEP_FACE_EMBEDDING_DIMENSION if success else None,
        l2Norm=1.0 if success else None,
        processingMilliseconds=1.0,
        embedding=embedding,
    )


def controlled_encoder(image_bytes: bytes) -> DeepEncodingResult:
    if image_bytes == b"SUCCESS":
        return controlled_result("Encoded", success=True)
    if image_bytes == b"NO_FACE":
        return controlled_result("NoFaceDetected")
    if image_bytes == b"MULTIPLE":
        return controlled_result("MultipleFacesDetected")
    if image_bytes == b"MISMATCH":
        return controlled_result("FaceDetectionMismatch")
    if image_bytes == b"ERROR":
        raise RuntimeError("controlled per-image failure")
    raise ValueError("unexpected controlled image")


def rows_digest(db, model, order_column) -> str:
    digest = hashlib.sha256()
    for row in db.query(model).order_by(order_column).all():
        values = {
            column.name: getattr(row, column.name)
            for column in model.__table__.columns
        }
        digest.update(json.dumps(values, sort_keys=True, default=str, separators=(",", ":")).encode())
    return digest.hexdigest()


def storage_digest(storage_root: Path) -> str:
    digest = hashlib.sha256()
    for image_path in sorted(storage_root.glob("*"), key=lambda item: item.name):
        if image_path.is_file():
            digest.update(image_path.name.encode())
            digest.update(image_path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fdas-phase10-7b-") as temp_directory:
        temp_root = Path(temp_directory)
        database_path = temp_root / "isolated.db"
        storage_root = temp_root / "storage"
        storage_root.mkdir()
        isolated_engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        tables_without_embeddings = [
            table
            for table in Base.metadata.sorted_tables
            if table.name != FaceTemplateEmbedding.__tablename__
        ]
        Base.metadata.create_all(bind=isolated_engine, tables=tables_without_embeddings)
        IsolatedSession = sessionmaker(bind=isolated_engine, autoflush=False, autocommit=False)

        image_specs = [
            (9001, "success_1.jpg", b"SUCCESS"),
            (9001, "success_2.jpg", b"SUCCESS"),
            (9001, "no_face.jpg", b"NO_FACE"),
            (9001, "multiple.jpg", b"MULTIPLE"),
            (9001, "mismatch.jpg", b"MISMATCH"),
            (9001, "unreadable.jpg", b""),
            (9001, "error.jpg", b"ERROR"),
            (9001, "missing.jpg", None),
            (9002, "success_3.jpg", b"SUCCESS"),
        ]
        for _, filename, content in image_specs:
            if content is not None:
                (storage_root / filename).write_bytes(content)

        with IsolatedSession() as db:
            db.add_all(
                [
                    Student(
                        studentId=9001,
                        rollNo="P107B-READY",
                        fullName="Phase 10.7B Ready",
                        departmentId=1,
                        classId=1,
                        yearSemester="Test",
                        section="T",
                        status="Active",
                    ),
                    Student(
                        studentId=9002,
                        rollNo="P107B-INCOMPLETE",
                        fullName="Phase 10.7B Incomplete",
                        departmentId=1,
                        classId=1,
                        yearSemester="Test",
                        section="T",
                        status="Active",
                    ),
                ]
            )
            db.flush()
            templates = []
            for sample_index, (student_id, filename, _) in enumerate(image_specs, start=1):
                templates.append(
                    FaceTemplate(
                        studentId=student_id,
                        templatePath=filename,
                        encodingData=json.dumps([0.25, 0.75]),
                        encodingVersion=LEGACY_VERSION,
                        sampleIndex=sample_index,
                        status="Encoded",
                        isActive=True,
                    )
                )
            db.add_all(templates)
            db.commit()

        resolver = lambda template: storage_root / str(template.templatePath)
        with IsolatedSession() as db:
            template_digest_before = rows_digest(db, FaceTemplate, FaceTemplate.templateId)
            attendance_before = db.query(AttendanceRecord).count()
            storage_before = storage_digest(storage_root)
            table_before = inspect(isolated_engine).has_table(FaceTemplateEmbedding.__tablename__)
            with patch.object(migration, "resolve_template_image_path", side_effect=resolver):
                dry_run = migration.run_migration(
                    db,
                    apply=False,
                    minimum_embeddings=2,
                    encoder=controlled_encoder,
                    show_progress=False,
                )
            table_after_dry_run = inspect(isolated_engine).has_table(FaceTemplateEmbedding.__tablename__)
            template_digest_after_dry_run = rows_digest(db, FaceTemplate, FaceTemplate.templateId)
            attendance_after_dry_run = db.query(AttendanceRecord).count()

        migration.create_embedding_table(isolated_engine)
        with IsolatedSession() as db:
            with patch.object(migration, "resolve_template_image_path", side_effect=resolver):
                first_apply = migration.run_migration(
                    db,
                    apply=True,
                    minimum_embeddings=2,
                    encoder=controlled_encoder,
                    show_progress=False,
                )
                second_apply = migration.run_migration(
                    db,
                    apply=True,
                    minimum_embeddings=2,
                    encoder=controlled_encoder,
                    show_progress=False,
                )

            persisted = db.query(FaceTemplateEmbedding).order_by(FaceTemplateEmbedding.faceTemplateEmbeddingId).all()
            migrated_template_ids = {row.faceTemplateId for row in persisted}
            success_template_ids = {
                template.templateId
                for template, (_, _, content) in zip(
                    db.query(FaceTemplate).order_by(FaceTemplate.templateId).all(),
                    image_specs,
                )
                if content == b"SUCCESS"
            }
            all_dimensions_valid = all(row.embeddingDimension == 512 for row in persisted)
            all_versions_valid = all(row.encodingVersion == "arcface_v1" for row in persisted)
            all_models_valid = all(row.modelName == "buffalo_l" for row in persisted)
            all_norms_valid = all(
                abs(float(np.linalg.norm(np.asarray(json.loads(row.embeddingData), dtype=np.float32))) - 1.0) <= 0.001
                for row in persisted
            )
            template_digest_after_apply = rows_digest(db, FaceTemplate, FaceTemplate.templateId)
            attendance_after_apply = db.query(AttendanceRecord).count()

            duplicate_prevented = False
            duplicate_source = persisted[0]
            db.add(
                FaceTemplateEmbedding(
                    faceTemplateId=duplicate_source.faceTemplateId,
                    studentId=duplicate_source.studentId,
                    encodingVersion=duplicate_source.encodingVersion,
                    embeddingData=duplicate_source.embeddingData,
                    embeddingDimension=duplicate_source.embeddingDimension,
                    modelName=duplicate_source.modelName,
                    sourceImageSha256=duplicate_source.sourceImageSha256,
                    l2Norm=duplicate_source.l2Norm,
                    isActive=True,
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                duplicate_prevented = True
            final_embedding_count = db.query(FaceTemplateEmbedding).count()

        storage_after = storage_digest(storage_root)
        ready_summary = next(item for item in first_apply["students"] if item["studentId"] == 9001)
        incomplete_summary = next(item for item in first_apply["students"] if item["studentId"] == 9002)
        capability = deep_face_capability(initialize=False)
        isolated_engine.dispose()
        results = {
            "dry_run_created_no_schema_or_rows": (
                table_before is False
                and table_after_dry_run is False
                and dry_run["persistentEmbeddingsCreated"] == 0
                and dry_run["persistentEmbeddingCount"] == 0
            ),
            "dry_run_created_zero_db_changes": (
                template_digest_before == template_digest_after_dry_run
                and attendance_before == attendance_after_dry_run
            ),
            "dry_run_categories_correct": (
                dry_run["counts"]["EncodedSuccessfully"] == 3
                and dry_run["counts"]["NoFaceDetected"] == 1
                and dry_run["counts"]["MultipleFacesDetected"] == 1
                and dry_run["counts"]["FaceDetectionMismatch"] == 1
                and dry_run["counts"]["MissingFile"] == 1
                and dry_run["counts"]["UnreadableImage"] == 1
                and dry_run["counts"]["EmbeddingError"] == 1
            ),
            "apply_created_only_valid_embeddings": (
                first_apply["persistentEmbeddingsCreated"] == 3
                and first_apply["persistentEmbeddingCount"] == 3
                and migrated_template_ids == success_template_ids
            ),
            "arcface_dimension_512": all_dimensions_valid,
            "arcface_embeddings_l2_normalized": all_norms_valid,
            "version_and_model_recorded": all_versions_valid and all_models_valid,
            "second_apply_idempotent": (
                second_apply["persistentEmbeddingsCreated"] == 0
                and second_apply["persistentEmbeddingCount"] == 3
                and second_apply["alreadyMigrated"] == 3
            ),
            "duplicate_constraint_prevents_duplicate_version": duplicate_prevented and final_embedding_count == 3,
            "failed_images_not_migrated": migrated_template_ids == success_template_ids,
            "failed_image_did_not_break_migration": first_apply["counts"]["EmbeddingError"] == 1 and len(persisted) == 3,
            "student_eligibility_counts_correct": (
                ready_summary["validDeepEmbeddings"] == 2
                and ready_summary["deepEligibility"] == "Ready"
                and incomplete_summary["validDeepEmbeddings"] == 1
                and incomplete_summary["deepEligibility"] == "DeepEnrollmentIncomplete"
            ),
            "legacy_version_and_data_preserved": template_digest_before == template_digest_after_apply,
            "image_files_preserved": storage_before == storage_after,
            "attendance_untouched": attendance_before == attendance_after_apply == 0,
            "encoding_version_is_arcface_v1": DEEP_FACE_ENCODING_VERSION == "arcface_v1",
            "configured_minimum_is_20": migration.DEEP_ENROLLMENT_MIN_EMBEDDINGS == 20,
            "final_deep_activation_released_hold": (
                DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE is True
                and IDENTITY_MATCHING_SAFETY_HOLD is False
            ),
            "deep_recognition_active_for_attendance": (
                capability["activeForAttendance"] is True
                and capability["attendanceSafetyHold"] is False
            ),
        }
        results["phase10_7b_passed"] = all(bool(value) for value in results.values())
        for name, passed in results.items():
            print(f"{name}={bool(passed)}")
        if not results["phase10_7b_passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
