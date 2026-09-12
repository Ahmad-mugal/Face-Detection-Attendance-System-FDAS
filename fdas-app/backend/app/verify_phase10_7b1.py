from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.config import DEEP_ENROLLMENT_MIN_EMBEDDINGS, IDENTITY_MATCHING_SAFETY_HOLD
from app.database import Base
from app.models.attendance_record import AttendanceRecord
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.services import deep_enrollment_recovery as recovery
from app.services.deep_face import DeepEncodingResult, deep_face_capability
from app.services.face_enrollment import DEEP_RECOVERY_TEMPLATE_STATUS, student_face_registered
from app.services.face_matching import load_student_candidate_templates


def controlled_legacy_processing(content: bytes):
    if content == b"NO_FACE":
        return SimpleNamespace(status="NoFaceDetected", encodingData=None, faceBoxJson=None)
    if content == b"MULTIPLE":
        return SimpleNamespace(status="MultipleFacesDetected", encodingData=None, faceBoxJson=None)
    descriptor = [0.0, 1.0] if content == b"SWITCH" else [1.0, 0.0]
    return SimpleNamespace(
        status="Encoded",
        encodingData=json.dumps(descriptor),
        faceBoxJson=json.dumps([10, 10, 80, 80]),
    )


class ControlledDeepService:
    def encode_image_bytes(self, content: bytes) -> DeepEncodingResult:
        if content == b"MISMATCH":
            return DeepEncodingResult(
                success=False,
                status="FaceDetectionMismatch",
                message="controlled mismatch",
                haarFaceCount=1,
                deepFaceCount=0,
                embeddingDimension=None,
                l2Norm=None,
                processingMilliseconds=1.0,
            )
        vector = np.full(512, 1.0 / math.sqrt(512), dtype=np.float32)
        return DeepEncodingResult(
            success=True,
            status="Encoded",
            message="controlled success",
            haarFaceCount=1,
            deepFaceCount=1,
            embeddingDimension=512,
            l2Norm=1.0,
            processingMilliseconds=1.0,
            embedding=vector,
        )


def exception_code(callable_) -> str | None:
    try:
        callable_()
    except HTTPException as exc:
        return exc.detail.get("code") if isinstance(exc.detail, dict) else str(exc.detail)
    return None


def digest_files(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def digest_rows(rows, model) -> str:
    digest = hashlib.sha256()
    for row in rows:
        values = {column.name: getattr(row, column.name) for column in model.__table__.columns}
        digest.update(json.dumps(values, sort_keys=True, default=str, separators=(",", ":")).encode())
    return digest.hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fdas-phase10-7b1-") as temp_directory:
        temp_root = Path(temp_directory)
        storage_root = temp_root / "storage"
        storage_root.mkdir()
        database_path = temp_root / "isolated.db"
        engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        with TestSession() as db:
            department = Department(departmentId=1, departmentName="Recovery Test", status="Active")
            classroom = ClassRoom(
                classId=1,
                className="Recovery Test Class",
                departmentId=1,
                yearSemester="Test",
                section="T",
                status="Active",
            )
            role = Role(roleId=1, roleName="Admin")
            admin = User(
                userId=1,
                fullName="Recovery Admin",
                email="recovery.admin@fdas.local",
                passwordHash="not-used",
                roleId=1,
                status="Active",
                accessScope="AllDepartments",
            )
            student = Student(
                studentId=9001,
                rollNo="P107B1-001",
                fullName="Recovery Student",
                departmentId=1,
                classId=1,
                yearSemester="Test",
                section="T",
                status="Active",
            )
            db.add_all([department, classroom, role, admin, student])
            db.flush()

            historical_templates = []
            for sample_index in range(1, 26):
                relative = Path("historical") / f"sample_{sample_index:02d}.jpg"
                absolute = storage_root / relative
                absolute.parent.mkdir(parents=True, exist_ok=True)
                content = f"HISTORICAL-{sample_index}".encode()
                absolute.write_bytes(content)
                template = FaceTemplate(
                    studentId=student.studentId,
                    templatePath=relative.as_posix(),
                    encodingData=json.dumps([1.0, 0.0]),
                    encodingVersion="opencv_basic_v1",
                    sampleIndex=sample_index,
                    status="Encoded",
                    isActive=True,
                    createdByUserId=admin.userId,
                )
                db.add(template)
                db.flush()
                historical_templates.append(template)
                if sample_index <= 18:
                    vector = np.full(512, 1.0 / math.sqrt(512), dtype=np.float32)
                    db.add(
                        FaceTemplateEmbedding(
                            faceTemplateId=template.templateId,
                            studentId=student.studentId,
                            encodingVersion="arcface_v1",
                            embeddingData=json.dumps(vector.astype(float).tolist(), separators=(",", ":")),
                            embeddingDimension=512,
                            modelName="buffalo_l",
                            sourceImageSha256=hashlib.sha256(content).hexdigest(),
                            l2Norm=1.0,
                            isActive=True,
                        )
                    )
            db.commit()

        def test_path(student_id: int, sample_index: int, suffix: str):
            filename = f"recovery_{sample_index:03d}{suffix}"
            relative = Path("storage") / "face_enrollments" / str(student_id) / "recovery" / filename
            absolute = storage_root / "face_enrollments" / str(student_id) / "recovery" / filename
            return relative, absolute

        deep_service = ControlledDeepService()
        with TestSession() as db:
            admin = db.query(User).filter(User.userId == 1).one()
            student = db.query(Student).filter(Student.studentId == 9001).one()
            historical_rows = db.query(FaceTemplate).filter(FaceTemplate.studentId == 9001).order_by(FaceTemplate.templateId).all()
            historical_embeddings = db.query(FaceTemplateEmbedding).order_by(FaceTemplateEmbedding.faceTemplateEmbeddingId).all()
            templates_before = digest_rows(historical_rows, FaceTemplate)
            embeddings_before = digest_rows(historical_embeddings, FaceTemplateEmbedding)
            images_before = digest_files(storage_root)
            historical_images_before = digest_files(storage_root / "historical")
            attendance_before = db.query(AttendanceRecord).count()
            legacy_candidates_before = len(load_student_candidate_templates(db, student))
            registered_before = student_face_registered(student)

            patches = (
                patch.object(recovery, "process_image_bytes", side_effect=controlled_legacy_processing),
                patch.object(recovery, "get_deep_face_service", return_value=deep_service),
                patch.object(recovery, "_build_recovery_path", side_effect=test_path),
            )
            with patches[0], patches[1], patches[2]:
                no_face_code = exception_code(
                    lambda: recovery.create_deep_recovery_enrollment(
                        db, admin, 9001, [recovery.RecoveryUpload(".jpg", b"NO_FACE")]
                    )
                )
                multiple_code = exception_code(
                    lambda: recovery.create_deep_recovery_enrollment(
                        db, admin, 9001, [recovery.RecoveryUpload(".jpg", b"MULTIPLE")]
                    )
                )
                mismatch_code = exception_code(
                    lambda: recovery.create_deep_recovery_enrollment(
                        db, admin, 9001, [recovery.RecoveryUpload(".jpg", b"MISMATCH")]
                    )
                )
                continuity_code = exception_code(
                    lambda: recovery.create_deep_recovery_enrollment(
                        db,
                        admin,
                        9001,
                        [
                            recovery.RecoveryUpload(".jpg", b"VALID-CONTINUITY"),
                            recovery.RecoveryUpload(".jpg", b"SWITCH"),
                        ],
                    )
                )
                duplicate_batch_code = exception_code(
                    lambda: recovery.create_deep_recovery_enrollment(
                        db,
                        admin,
                        9001,
                        [
                            recovery.RecoveryUpload(".jpg", b"DUPLICATE"),
                            recovery.RecoveryUpload(".jpg", b"DUPLICATE"),
                        ],
                    )
                )
                recovery_result = recovery.create_deep_recovery_enrollment(
                    db,
                    admin,
                    9001,
                    [
                        recovery.RecoveryUpload(".jpg", b"VALID-A"),
                        recovery.RecoveryUpload(".jpg", b"VALID-B"),
                    ],
                )
                duplicate_existing_code = exception_code(
                    lambda: recovery.create_deep_recovery_enrollment(
                        db, admin, 9001, [recovery.RecoveryUpload(".jpg", b"VALID-A")]
                    )
                )

            all_templates = db.query(FaceTemplate).filter(FaceTemplate.studentId == 9001).order_by(FaceTemplate.templateId).all()
            recovery_templates = [row for row in all_templates if row.status == DEEP_RECOVERY_TEMPLATE_STATUS]
            all_embeddings = db.query(FaceTemplateEmbedding).order_by(FaceTemplateEmbedding.faceTemplateEmbeddingId).all()
            new_embeddings = all_embeddings[18:]
            historical_templates_after = all_templates[:25]
            historical_embeddings_after = all_embeddings[:18]
            legacy_candidates_after = len(load_student_candidate_templates(db, student))
            registered_after = student_face_registered(student)
            attendance_after = db.query(AttendanceRecord).count()
            readiness = recovery.deep_enrollment_readiness(db, admin, 9001)

            recovery_files = [storage_root / Path(row.templatePath).relative_to("storage") for row in recovery_templates]
            result = {
                "supplemental_rows_are_additive": len(all_templates) == 27 and len(recovery_templates) == 2,
                "historical_templates_preserved": digest_rows(historical_templates_after, FaceTemplate) == templates_before,
                "historical_embeddings_preserved": digest_rows(historical_embeddings_after, FaceTemplateEmbedding) == embeddings_before,
                "historical_images_preserved": (
                    historical_images_before == digest_files(storage_root / "historical")
                    and all((storage_root / "historical" / f"sample_{index:02d}.jpg").is_file() for index in range(1, 26))
                ),
                "recovery_images_belong_to_student": (
                    all(f"face_enrollments/9001/recovery" in row.templatePath for row in recovery_templates)
                    and all(path.is_file() for path in recovery_files)
                ),
                "deep_only_rows_excluded_from_legacy": (
                    all(row.encodingData is None and row.encodingVersion is None for row in recovery_templates)
                    and legacy_candidates_before == legacy_candidates_after == 25
                    and registered_before is True
                    and registered_after is True
                ),
                "no_face_rejected_without_write": no_face_code == "NoFaceDetected",
                "multiple_faces_rejected_without_write": multiple_code == "MultipleFacesDetected",
                "deep_detector_mismatch_rejected_without_write": mismatch_code == "FaceDetectionMismatch",
                "face_continuity_loss_rejected_without_write": continuity_code == "FaceContinuityLost",
                "batch_duplicate_rejected": duplicate_batch_code == "DuplicateRecoveryImage",
                "existing_image_duplicate_rejected": duplicate_existing_code == "DuplicateRecoveryImage",
                "valid_samples_create_512d_arcface": (
                    len(new_embeddings) == 2
                    and all(row.encodingVersion == "arcface_v1" for row in new_embeddings)
                    and all(row.embeddingDimension == 512 for row in new_embeddings)
                    and all(row.modelName == "buffalo_l" for row in new_embeddings)
                    and all(abs(row.l2Norm - 1.0) <= 0.001 for row in new_embeddings)
                    and all(len(row.sourceImageSha256) == 64 for row in new_embeddings)
                ),
                "deep_counts_and_readiness_correct": (
                    recovery_result["deepCountBefore"] == 18
                    and recovery_result["deepCountAfter"] == 20
                    and recovery_result["readiness"] == "Ready"
                    and readiness["validDeepEmbeddings"] == 20
                    and readiness["additionalNeeded"] == 0
                ),
                "rejected_attempts_created_no_extra_rows": len(all_templates) == 27 and len(all_embeddings) == 20,
                "attendance_not_created": attendance_before == attendance_after == 0,
                "safety_hold_active": IDENTITY_MATCHING_SAFETY_HOLD is True,
                "minimum_remains_20": DEEP_ENROLLMENT_MIN_EMBEDDINGS == 20,
                "deep_matching_inactive": deep_face_capability(initialize=False)["activeForAttendance"] is False,
                "storage_only_added_expected_recovery_files": images_before != digest_files(storage_root) and len(recovery_files) == 2,
            }

        engine.dispose()
        result["phase10_7b1_passed"] = all(bool(value) for value in result.values())
        for name, passed in result.items():
            print(f"{name}={bool(passed)}")
        if not result["phase10_7b1_passed"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
