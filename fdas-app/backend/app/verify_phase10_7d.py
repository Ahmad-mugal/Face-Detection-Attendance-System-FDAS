from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sqlalchemy import func

from app.config import (
    DEEP_ENROLLMENT_MIN_EMBEDDINGS,
    DEEP_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_MATCH_SCORING_METHOD,
    DEEP_MATCH_THRESHOLD,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.database import SessionLocal
from app.models.attendance_record import AttendanceRecord
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.services.deep_face import DeepEncodingResult
from app.services import deep_face_matching as matching


BACKEND_DIR = Path(__file__).resolve().parent.parent
ENROLLMENT_ROOT = BACKEND_DIR / "storage" / "face_enrollments"


class ExistingEmbeddingQueryService:
    def __init__(self, vector: np.ndarray):
        self.vector = vector.astype(np.float32)

    def encode_image_bytes(self, _content: bytes) -> DeepEncodingResult:
        return DeepEncodingResult(
            success=True,
            status="Encoded",
            message="Phase 10.7D controlled no-write query",
            haarFaceCount=1,
            deepFaceCount=1,
            embeddingDimension=512,
            l2Norm=1.0,
            processingMilliseconds=1.0,
            embedding=self.vector,
        )


def row_fingerprint(db, student_id: int) -> str:
    student = db.query(Student).filter(Student.studentId == student_id).one()
    templates = (
        db.query(FaceTemplate)
        .filter(FaceTemplate.studentId == student_id)
        .order_by(FaceTemplate.templateId)
        .all()
    )
    embeddings = (
        db.query(FaceTemplateEmbedding)
        .filter(FaceTemplateEmbedding.studentId == student_id)
        .order_by(FaceTemplateEmbedding.faceTemplateEmbeddingId)
        .all()
    )
    attendance = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.studentId == student_id)
        .order_by(AttendanceRecord.attendanceId)
        .all()
    )
    values = [
        (
            student.studentId,
            student.rollNo,
            student.fullName,
            student.departmentId,
            student.classId,
            student.status,
            student.createdAt,
            student.updatedAt,
        ),
        *[(item.templateId, item.templatePath, item.status, item.isActive, item.updatedAt) for item in templates],
        *[(item.faceTemplateEmbeddingId, item.faceTemplateId, item.sourceImageSha256, item.isActive, item.updatedAt) for item in embeddings],
        *[(item.attendanceId, item.sessionId, item.status, item.markedAt) for item in attendance],
    ]
    return hashlib.sha256(repr(values).encode("utf-8")).hexdigest()


def storage_fingerprint(student_id: int) -> tuple[int, int, str]:
    root = ENROLLMENT_ROOT / str(student_id)
    files = sorted(item for item in root.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    total_bytes = 0
    for item in files:
        content = item.read_bytes()
        total_bytes += len(content)
        digest.update(item.relative_to(root).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(content).digest())
    return len(files), total_bytes, digest.hexdigest()


def main() -> None:
    with SessionLocal() as db:
        duplicate = db.query(Student).filter(Student.studentId == 19).one()
        canonical = db.query(Student).filter(Student.studentId == 22).one()
        admin = (
            db.query(User)
            .join(Role, Role.roleId == User.roleId)
            .filter(Role.roleName == "Admin", User.status == "Approved")
            .first()
        )
        if admin is None:
            raise RuntimeError("No approved administrator is available for diagnostic verification")

        template_counts_before = {
            student_id: db.query(FaceTemplate).filter(FaceTemplate.studentId == student_id).count()
            for student_id in (19, 22)
        }
        embedding_counts_before = {
            student_id: db.query(FaceTemplateEmbedding)
            .filter(FaceTemplateEmbedding.studentId == student_id)
            .count()
            for student_id in (19, 22)
        }
        attendance_counts_before = {
            student_id: db.query(AttendanceRecord).filter(AttendanceRecord.studentId == student_id).count()
            for student_id in (19, 22)
        }
        row_fingerprints_before = {student_id: row_fingerprint(db, student_id) for student_id in (19, 22)}
        storage_before = {student_id: storage_fingerprint(student_id) for student_id in (19, 22)}

        candidates = matching.load_deep_match_candidates(db, admin, canonical.departmentId)
        candidate_ids = {item.student.studentId for item in candidates}
        expected_active_ids = {
            student_id
            for student_id, count in (
                db.query(FaceTemplateEmbedding.studentId, func.count(FaceTemplateEmbedding.faceTemplateEmbeddingId))
                .join(Student, Student.studentId == FaceTemplateEmbedding.studentId)
                .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
                .filter(
                    Student.departmentId == canonical.departmentId,
                    Student.status == "Active",
                    FaceTemplateEmbedding.encodingVersion == "arcface_v1",
                    FaceTemplateEmbedding.isActive.is_(True),
                    FaceTemplate.isActive.is_(True),
                )
                .group_by(FaceTemplateEmbedding.studentId)
                .all()
            )
            if count >= DEEP_ENROLLMENT_MIN_EMBEDDINGS
        }

        canonical_embedding = next(item.vector for item in candidates if item.student.studentId == 22)
        with patch.object(
            matching,
            "get_deep_face_service",
            return_value=ExistingEmbeddingQueryService(canonical_embedding),
        ):
            diagnostic = matching.diagnose_deep_face_bytes(
                db,
                admin,
                canonical.departmentId,
                22,
                b"phase-10.7d-controlled-transient-query",
            )

        template_counts_after = {
            student_id: db.query(FaceTemplate).filter(FaceTemplate.studentId == student_id).count()
            for student_id in (19, 22)
        }
        embedding_counts_after = {
            student_id: db.query(FaceTemplateEmbedding)
            .filter(FaceTemplateEmbedding.studentId == student_id)
            .count()
            for student_id in (19, 22)
        }
        attendance_counts_after = {
            student_id: db.query(AttendanceRecord).filter(AttendanceRecord.studentId == student_id).count()
            for student_id in (19, 22)
        }
        row_fingerprints_after = {student_id: row_fingerprint(db, student_id) for student_id in (19, 22)}
        storage_after = {student_id: storage_fingerprint(student_id) for student_id in (19, 22)}

    result = {
        "duplicate_19_preserved_and_inactive": (
            duplicate.rollNo == "CS-2022-58"
            and duplicate.fullName == "Ahmad Mughal"
            and duplicate.status == "Inactive"
        ),
        "canonical_22_active": (
            canonical.rollNo == "cs-2026-789"
            and canonical.fullName == "Ahmad Mughal"
            and canonical.status == "Active"
        ),
        "historical_relations_preserved": (
            template_counts_before[19] == template_counts_after[19] == 25
            and embedding_counts_before[19] == embedding_counts_after[19] == 23
            and attendance_counts_before[19] == attendance_counts_after[19] == 4
        ),
        "canonical_deep_ready": embedding_counts_before[22] >= DEEP_ENROLLMENT_MIN_EMBEDDINGS,
        "inactive_duplicate_excluded_from_candidates": 19 not in candidate_ids,
        "canonical_included_in_candidates": 22 in candidate_ids,
        "candidate_scoping_matches_active_deep_ready_students": candidate_ids == expected_active_ids,
        "query_only_creates_no_templates": template_counts_before == template_counts_after,
        "query_only_creates_no_deep_embeddings": embedding_counts_before == embedding_counts_after,
        "query_only_creates_no_attendance": attendance_counts_before == attendance_counts_after,
        "query_only_preserves_identity_rows": row_fingerprints_before == row_fingerprints_after,
        "query_only_preserves_storage": storage_before == storage_after,
        "diagnostic_response_declares_no_write": (
            diagnostic["attendanceCreated"] is False
            and diagnostic["persistentWrite"] is False
            and diagnostic["activeForAttendance"] is False
        ),
        "preliminary_policy_unchanged": (
            DEEP_MATCH_SCORING_METHOD == "mean_top_3"
            and DEEP_MATCH_THRESHOLD == 0.85
            and DEEP_MATCH_MIN_IDENTITY_MARGIN == 0.07
            and diagnostic["scoringMethod"] == "mean_top_3"
            and diagnostic["thresholdUsed"] == 0.85
            and diagnostic["requiredMargin"] == 0.07
        ),
        "threshold_and_margin_applied": (
            diagnostic["topAboveThreshold"] == (diagnostic["topCandidate"]["score"] >= 0.85)
            and diagnostic["marginPassed"] == (
                diagnostic["scoreMargin"] is None or diagnostic["scoreMargin"] >= 0.07
            )
        ),
        "safety_hold_remains_active": (
            IDENTITY_MATCHING_SAFETY_HOLD is True
            and diagnostic["attendanceSafetyHold"] is True
        ),
    }
    result["phase10_7d_passed"] = all(bool(value) for value in result.values())
    for name, passed in result.items():
        print(f"{name}={bool(passed)}")
    if not result["phase10_7d_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
