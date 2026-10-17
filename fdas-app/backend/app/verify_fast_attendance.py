from __future__ import annotations

import asyncio
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.config import DEEP_FACE_EMBEDDING_DIMENSION
from app.database import Base
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.routers.attendance_marking import mark_by_face_fast, mark_by_face_live
from app.services.attendance_marking import mark_fast_multi_face_attendance
from app.services.deep_face import FastFaceEncoding, FastFrameEncoding
from app.services.deep_face_matching import (
    FastDeepGallery,
    FastGalleryIdentity,
    clear_fast_gallery_cache,
    get_cached_fast_gallery,
    match_fast_multi_face_for_attendance,
)
from app.services.liveness import LIVENESS_STATUS_FAILED, LivenessResult
from app.verify_phase10_9 import MemoryUpload, add_deep_gallery, png_bytes


def vector(*values: float) -> np.ndarray:
    result = np.zeros(DEEP_FACE_EMBEDDING_DIMENSION, dtype=np.float32)
    result[: len(values)] = values
    norm = float(np.linalg.norm(result))
    return result / norm


def gallery(student1: Student, student2: Student, second_vector: np.ndarray | None = None) -> FastDeepGallery:
    first = vector(1.0, 0.0)
    second = second_vector if second_vector is not None else vector(0.0, 1.0)
    matrix = np.stack([first, first, first, second, second, second]).astype(np.float32)
    matrix.setflags(write=False)
    identities = (
        FastGalleryIdentity(student1.studentId, student1.fullName, student1.rollNo, student1.classId, "Class 1", student1.departmentId, "Computer Science", (0, 1, 2)),
        FastGalleryIdentity(student2.studentId, student2.fullName, student2.rollNo, student2.classId, "Class 1", student2.departmentId, "Computer Science", (3, 4, 5)),
    )
    return FastDeepGallery(
        departmentId=1,
        fingerprint="fixture",
        identities=identities,
        embeddingMatrix=matrix,
        templateIds=(1, 2, 3, 4, 5, 6),
        embeddingIds=(11, 12, 13, 14, 15, 16),
    )


def frame(*embeddings: np.ndarray) -> FastFrameEncoding:
    faces = tuple(
        FastFaceEncoding(
            faceIndex=index,
            faceBox=(20 + ((index - 1) * 130), 30, 100, 120),
            detectionScore=0.99,
            status="Ready",
            message="ready",
            quality={"passed": True, "reason": "quality_checks_passed"},
            embedding=embedding,
        )
        for index, embedding in enumerate(embeddings, start=1)
    )
    return FastFrameEncoding(
        sourceWidth=640,
        sourceHeight=480,
        faces=faces,
        rawDetectionCount=len(faces),
        duplicateDetectionCount=0,
        invalidDetectionCount=0,
        decodeMilliseconds=1.0,
        detectorMilliseconds=10.0,
        alignmentMilliseconds=2.0,
        embeddingMilliseconds=5.0,
        totalMilliseconds=18.0,
    )


class ScriptedFastService:
    def __init__(self, result: FastFrameEncoding):
        self.result = result

    def encode_fast_attendance_frame_bytes(self, _image_bytes: bytes) -> FastFrameEncoding:
        return self.result


def run_match(db, admin: User, fixture_frame: FastFrameEncoding, fixture_gallery: FastDeepGallery) -> dict:
    with patch(
        "app.services.deep_face_matching.get_deep_face_service",
        return_value=ScriptedFastService(fixture_frame),
    ), patch(
        "app.services.deep_face_matching.get_cached_fast_gallery",
        return_value=(fixture_gallery, True),
    ):
        return match_fast_multi_face_for_attendance(db, admin, 1, png_bytes())


def main() -> None:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="fdas-fast-attendance-", ignore_cleanup_errors=True) as temporary:
        database_path = Path(temporary) / "isolated.db"
        engine = create_engine(f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        with Session() as db:
            department1 = Department(departmentId=1, departmentName="Computer Science", status="Active")
            department2 = Department(departmentId=2, departmentName="IT", status="Active")
            class1 = ClassRoom(classId=1, className="Class 1", departmentId=1, yearSemester="Test", section="T", status="Active")
            class2 = ClassRoom(classId=2, className="Class 2", departmentId=2, yearSemester="Test", section="T", status="Active")
            admin_role = Role(roleId=1, roleName="Admin")
            operator_role = Role(roleId=2, roleName="Operator")
            admin = User(userId=1, fullName="Admin", email="admin@fast.test", passwordHash="unused", roleId=1, accessScope="AllDepartments", status="Approved")
            operator = User(userId=2, fullName="IT Operator", email="operator@fast.test", passwordHash="unused", roleId=2, assignedDepartmentId=2, accessScope="Department", status="Approved")
            student1 = Student(studentId=1, rollNo="FAST-1", fullName="Fast One", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
            student2 = Student(studentId=2, rollNo="FAST-2", fullName="Fast Two", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
            inactive = Student(studentId=3, rollNo="FAST-3", fullName="Inactive", departmentId=1, classId=1, yearSemester="Test", section="T", status="Inactive")
            incomplete = Student(studentId=4, rollNo="FAST-4", fullName="Incomplete", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
            now = datetime.now()
            session = AttendanceSession(sessionId=1, departmentId=1, startedByUserId=1, scheduledStartTime=now, scheduledEndTime=now + timedelta(hours=1), actualStartTime=now, status="Active", createdDate=date.today())
            closed_session = AttendanceSession(sessionId=2, departmentId=1, startedByUserId=1, scheduledStartTime=now, scheduledEndTime=now + timedelta(hours=1), actualStartTime=now, actualEndTime=now, status="Closed", createdDate=date.today())
            concurrent_session = AttendanceSession(sessionId=3, departmentId=1, startedByUserId=1, scheduledStartTime=now, scheduledEndTime=now + timedelta(hours=1), actualStartTime=now, status="Active", createdDate=date.today())
            db.add_all([department1, department2, class1, class2, admin_role, operator_role, admin, operator, student1, student2, inactive, incomplete, session, closed_session, concurrent_session])
            db.flush()
            add_deep_gallery(db, student1, admin)
            add_deep_gallery(db, student2, admin)
            add_deep_gallery(db, inactive, admin)
            db.commit()

            fixture_gallery = gallery(student1, student2)
            empty = run_match(db, admin, frame(), fixture_gallery)
            checks["zero_faces_returns_empty_without_error"] = empty["faces"] == []
            distinct = run_match(db, admin, frame(vector(1, 0), vector(0, 1), vector(0, 0, 1)), fixture_gallery)
            checks["three_faces_return_three_independent_outcomes"] = len(distinct["faces"]) == 3
            checks["two_distinct_faces_recognized"] = [face["studentId"] for face in distinct["faces"][:2]] == [1, 2]
            checks["unknown_face_not_identified"] = distinct["faces"][2]["status"] == "Unknown" and distinct["faces"][2]["studentId"] is None
            no_candidates = run_match(
                db,
                admin,
                frame(vector(1, 0)),
                FastDeepGallery(1, "empty", (), np.empty((0, 512), dtype=np.float32), (), ()),
            )
            checks["no_recognized_candidates_fails_closed"] = (
                no_candidates["faces"][0]["status"] == "NotEligible"
                and no_candidates["faces"][0]["studentId"] is None
            )

            conflict = run_match(db, admin, frame(vector(1, 0), vector(1, 0)), fixture_gallery)
            checks["one_to_one_assignment_blocks_duplicate_identity"] = (
                sum(face["studentId"] == 1 for face in conflict["faces"]) == 1
                and sum(face["status"] == "IdentityConflict" for face in conflict["faces"]) == 1
            )

            close_identity = vector(0.995, 0.1)
            ambiguous = run_match(db, admin, frame(vector(1, 0)), gallery(student1, student2, close_identity))
            checks["margin_below_0_07_rejected"] = ambiguous["faces"][0]["status"] == "Ambiguous"
            checks["threshold_below_0_85_rejected"] = distinct["faces"][2]["recognitionConfidence"] < 0.85
            poor_frame = FastFrameEncoding(
                sourceWidth=640,
                sourceHeight=480,
                faces=(FastFaceEncoding(1, (20, 30, 40, 50), 0.99, "PoorFaceQuality", "blurred", {"passed": False, "reason": "blurred"}, None),),
                rawDetectionCount=1,
                duplicateDetectionCount=0,
                invalidDetectionCount=0,
                decodeMilliseconds=1.0,
                detectorMilliseconds=10.0,
                alignmentMilliseconds=0.0,
                embeddingMilliseconds=0.0,
                totalMilliseconds=11.0,
            )
            poor = run_match(db, admin, poor_frame, fixture_gallery)
            checks["poor_quality_face_visible_but_unmarked"] = poor["faces"][0]["status"] == "PoorFaceQuality" and poor["faces"][0]["studentId"] is None

            with patch(
                "app.services.attendance_marking.match_fast_multi_face_for_attendance",
                return_value=distinct,
            ):
                created = mark_fast_multi_face_attendance(db, admin, 1, png_bytes())
                repeated = mark_fast_multi_face_attendance(db, admin, 1, png_bytes())
            records = db.query(AttendanceRecord).order_by(AttendanceRecord.studentId).all()
            checks["partial_success_persists_two_known_only"] = created["markedCount"] == 2 and len(records) == 2
            checks["fast_records_truthfully_not_checked"] = all(record.livenessStatus == "NotChecked" for record in records)
            checks["repeated_frame_is_idempotent"] = repeated["alreadyMarkedCount"] == 2 and db.query(AttendanceRecord).count() == 2
            checks["arcface_audit_metadata_preserved"] = all(record.recognitionProvider == "InsightFace" and record.recognitionEncodingVersion == "arcface_v1" for record in records)

            wrong_department_blocked = False
            try:
                with patch("app.services.attendance_marking.match_fast_multi_face_for_attendance", return_value=distinct):
                    mark_fast_multi_face_attendance(db, operator, 1, png_bytes())
            except HTTPException as exc:
                wrong_department_blocked = exc.status_code == 403
            checks["wrong_department_operator_blocked"] = wrong_department_blocked

            closed_session_blocked = False
            try:
                with patch("app.services.attendance_marking.match_fast_multi_face_for_attendance", return_value=distinct):
                    mark_fast_multi_face_attendance(db, admin, 2, png_bytes())
            except HTTPException as exc:
                closed_session_blocked = exc.status_code == 409
            checks["closed_session_creates_no_attendance"] = closed_session_blocked and db.query(AttendanceRecord).filter(AttendanceRecord.sessionId == 2).count() == 0

            def concurrent_submission() -> dict:
                with Session() as concurrent_db:
                    concurrent_admin = concurrent_db.query(User).filter(User.userId == 1).one()
                    return mark_fast_multi_face_attendance(concurrent_db, concurrent_admin, 3, png_bytes())

            with patch("app.services.attendance_marking.match_fast_multi_face_for_attendance", return_value=distinct):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    concurrent_results = list(executor.map(lambda _index: concurrent_submission(), range(2)))
            concurrent_rows = db.query(AttendanceRecord).filter(AttendanceRecord.sessionId == 3).count()
            checks["simultaneous_submissions_remain_idempotent"] = (
                concurrent_rows == 2
                and sum(result["markedCount"] for result in concurrent_results) == 2
                and sum(result["alreadyMarkedCount"] for result in concurrent_results) == 2
            )

            clear_fast_gallery_cache()
            eligible_gallery, first_hit = get_cached_fast_gallery(db, admin, 1)
            cached_gallery, second_hit = get_cached_fast_gallery(db, admin, 1)
            checks["gallery_excludes_inactive_and_incomplete"] = {identity.studentId for identity in eligible_gallery.identities} == {1, 2}
            checks["gallery_cache_reused"] = not first_hit and second_hit and eligible_gallery is cached_gallery
            incomplete.fullName = "Incomplete Updated"
            db.commit()
            _updated_gallery, updated_hit = get_cached_fast_gallery(db, admin, 1)
            checks["gallery_invalidates_on_student_change"] = updated_hit is False

            invalid_image_rejected = False
            try:
                match_fast_multi_face_for_attendance(db, admin, 1, b"not-an-image")
            except HTTPException as exc:
                invalid_image_rejected = exc.status_code == 422
            checks["corrupted_image_rejected_without_write"] = invalid_image_rejected and db.query(AttendanceRecord).count() == 4

            fast_response = {
                **created,
                "faces": [],
                "facesDetected": 0,
                "markedCount": 0,
                "alreadyMarkedCount": 0,
                "rejectedCount": 0,
            }
            upload = MemoryUpload(png_bytes(), 1)
            with patch("app.routers.attendance_marking.ATTENDANCE_MODE", "FAST_MULTI_FACE"), patch(
                "app.routers.attendance_marking.DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE", True
            ), patch("app.routers.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", False), patch(
                "app.routers.attendance_marking.mark_fast_multi_face_attendance", return_value=fast_response
            ) as fast_service, patch("app.routers.attendance_marking.verify_liveness") as liveness:
                asyncio.run(mark_by_face_fast(1, upload, admin, db))
            checks["fast_endpoint_never_calls_liveness"] = fast_service.call_count == 1 and liveness.call_count == 0

            safety_hold_blocks_fast = False
            try:
                with patch("app.routers.attendance_marking.ATTENDANCE_MODE", "FAST_MULTI_FACE"), patch(
                    "app.routers.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", True
                ):
                    asyncio.run(mark_by_face_fast(1, MemoryUpload(png_bytes(), 3), admin, db))
            except HTTPException as exc:
                safety_hold_blocks_fast = exc.status_code == 409
            checks["backend_safety_hold_blocks_fast_endpoint"] = safety_hold_blocks_fast

            fast_rejected_in_secure = False
            try:
                with patch("app.routers.attendance_marking.ATTENDANCE_MODE", "SECURE_SINGLE_FACE"):
                    asyncio.run(mark_by_face_fast(1, MemoryUpload(png_bytes(), 2), admin, db))
            except HTTPException as exc:
                fast_rejected_in_secure = exc.status_code == 409
            checks["fast_endpoint_rejected_in_secure_mode"] = fast_rejected_in_secure

            failed_liveness = LivenessResult(False, "LivenessFailed", "failed", LIVENESS_STATUS_FAILED, None, {"reason": "static"})
            uploads = [MemoryUpload(png_bytes(), index) for index in range(12)]
            with patch("app.routers.attendance_marking.ATTENDANCE_MODE", "SECURE_SINGLE_FACE"), patch(
                "app.routers.attendance_marking.verify_liveness", return_value=failed_liveness
            ) as secure_liveness:
                secure_result = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, None, False, None, admin, db))
            checks["secure_mode_still_invokes_liveness"] = secure_liveness.call_count == 1 and secure_result["status"] == "LivenessFailed"

        engine.dispose()

    checks["fast_attendance_verifier_passed"] = all(checks.values())
    for name, passed in checks.items():
        print(f"{name}={bool(passed)}")
    if not checks["fast_attendance_verifier_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
