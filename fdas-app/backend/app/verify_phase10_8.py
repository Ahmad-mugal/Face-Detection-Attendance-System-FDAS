from __future__ import annotations

import asyncio
import hashlib
import json
import math
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.config import (
    DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED,
    DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_CONTROLLED_MATCH_THRESHOLD,
    DEEP_ENROLLMENT_MIN_EMBEDDINGS,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_MATCH_SCORING_METHOD,
    DEEP_MATCH_THRESHOLD,
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    DEEP_RECOGNITION_INTEGRATED_FOR_ATTENDANCE,
    FACE_MATCH_THRESHOLD,
    IDENTITY_MATCHING_SAFETY_HOLD,
    LIVENESS_FRAME_COUNT,
)
from app.database import Base
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.routers.attendance_marking import mark_by_face_live
from app.services import deep_face_matching as matching
from app.services.attendance_marking import mark_attendance_by_face, student_has_required_deep_embeddings
from app.services.deep_face import DEEP_FACE_PROVIDER, DeepEncodingResult
from app.services.liveness import LIVENESS_STATUS_FAILED, LIVENESS_STATUS_PASSED, LivenessResult


class MemoryUpload:
    def __init__(self, content: bytes, index: int):
        self.filename = f"phase10_8_{index}.png"
        self.content_type = "image/png"
        self._content = content

    async def read(self) -> bytes:
        return self._content


class ControlledDeepService:
    def __init__(self, vector: np.ndarray | None = None, *, unavailable: bool = False):
        self.vector = (vector if vector is not None else unit_vector(1.0)).astype(np.float32)
        self.unavailable = unavailable

    def encode_image_bytes(self, _content: bytes) -> DeepEncodingResult:
        if self.unavailable:
            raise RuntimeError("controlled missing model")
        return DeepEncodingResult(
            success=True,
            status="Encoded",
            message="controlled ArcFace query",
            haarFaceCount=1,
            deepFaceCount=1,
            embeddingDimension=512,
            l2Norm=1.0,
            processingMilliseconds=1.0,
            embedding=self.vector,
        )

    def encode_attendance_query_bytes(self, content: bytes) -> DeepEncodingResult:
        return self.encode_image_bytes(content)


def unit_vector(score: float) -> np.ndarray:
    vector = np.zeros(512, dtype=np.float64)
    vector[0] = score
    vector[1] = math.sqrt(max(0.0, 1.0 - score * score))
    return vector


def serialize(vector: np.ndarray) -> str:
    return json.dumps(vector.astype(float).tolist(), separators=(",", ":"))


def make_png() -> bytes:
    image = np.full((160, 160, 3), 180, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not generate verifier frame")
    return encoded.tobytes()


def add_gallery(db, student: Student, admin: User, scores: list[float], *, count: int = 20) -> None:
    for index in range(count):
        score = scores[index] if index < len(scores) else scores[-1]
        template = FaceTemplate(
            studentId=student.studentId,
            templatePath=f"storage/isolated/{student.studentId}/{index}.jpg",
            sampleIndex=index + 1,
            status="DeepRecovery",
            isActive=True,
            createdByUserId=admin.userId,
        )
        db.add(template)
        db.flush()
        db.add(
            FaceTemplateEmbedding(
                faceTemplateId=template.templateId,
                studentId=student.studentId,
                encodingVersion=DEEP_FACE_ENCODING_VERSION,
                embeddingData=serialize(unit_vector(score)),
                embeddingDimension=512,
                modelName="buffalo_l",
                sourceImageSha256=hashlib.sha256(f"10.8-{student.studentId}-{index}".encode()).hexdigest(),
                l2Norm=1.0,
                isActive=True,
            )
        )


def controlled_candidates(student_scores: dict[int, list[float]]) -> list[matching.DeepMatchCandidate]:
    result: list[matching.DeepMatchCandidate] = []
    next_id = 10000
    for student_id, scores in student_scores.items():
        student = Student(
            studentId=student_id,
            rollNo=f"P108-{student_id}",
            fullName=f"Student {student_id}",
            departmentId=1,
            classId=1,
            yearSemester="Test",
            section="T",
            status="Active",
        )
        for score in scores:
            template = FaceTemplate(templateId=next_id, studentId=student_id, status="DeepRecovery", isActive=True)
            embedding = FaceTemplateEmbedding(
                faceTemplateEmbeddingId=next_id,
                faceTemplateId=next_id,
                studentId=student_id,
                encodingVersion=DEEP_FACE_ENCODING_VERSION,
                embeddingData=serialize(unit_vector(score)),
                embeddingDimension=512,
                modelName="buffalo_l",
                sourceImageSha256=hashlib.sha256(f"controlled-{next_id}".encode()).hexdigest(),
                l2Norm=1.0,
                isActive=True,
            )
            result.append(matching.DeepMatchCandidate(embedding, template, student, unit_vector(score)))
            next_id += 1
    return result


def liveness_result(status_value: str, *, passed: bool = False, frame: bytes | None = None) -> LivenessResult:
    return LivenessResult(
        passed=passed,
        status=status_value,
        message=f"controlled {status_value}",
        livenessStatus=LIVENESS_STATUS_PASSED if passed else LIVENESS_STATUS_FAILED,
        bestFrameBytes=frame if passed else None,
        diagnostics={"challenge": "MOVE_CLOSER", "reason": f"controlled {status_value}"},
    )


async def call_live(db, admin: User, session_id: int, frame: bytes, live: LivenessResult, deep_result: dict | None = None):
    uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
    query_uploads = [MemoryUpload(frame, index + 20) for index in range(3)]
    patches = [
        patch("app.routers.attendance_marking.DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED", True),
        patch("app.routers.attendance_marking.verify_liveness", return_value=live),
        patch("app.routers.attendance_marking.match_face_bytes"),
    ]
    if deep_result is not None:
        patches.append(patch("app.routers.attendance_marking.match_deep_face_query_burst_for_attendance", return_value=deep_result))
    started = [item.start() for item in patches]
    try:
        response = await mark_by_face_live(
            sessionId=session_id,
            challengeType="MOVE_CLOSER",
            files=uploads,
            queryFiles=query_uploads,
            controlledTest=True,
            expectedStudentId=22,
            current_user=admin,
            db=db,
        )
        legacy_mock = started[2]
        return response, legacy_mock.call_count
    finally:
        for item in reversed(patches):
            item.stop()


def failure_match(status_value: str) -> dict:
    return {
        "matched": False,
        "status": status_value,
        "message": f"controlled {status_value}",
        "studentId": None,
        "similarityScore": 0.84 if status_value == "MatchBelowThreshold" else 0.90,
        "secondSimilarityScore": 0.83,
        "scoreMargin": 0.01,
        "thresholdUsed": DEEP_MATCH_THRESHOLD,
        "requiredMargin": DEEP_MATCH_MIN_IDENTITY_MARGIN,
        "aggregationMethod": DEEP_MATCH_SCORING_METHOD,
        "recognitionProvider": DEEP_FACE_PROVIDER,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "topStudentId": 22,
        "topStudentName": "Ahmad Mughal",
        "topRollNo": "cs-2026-789",
        "topScore": 0.84 if status_value == "MatchBelowThreshold" else 0.90,
        "secondStudentId": 24,
        "secondStudentName": "Distinct Student",
        "secondRollNo": "P108-24",
        "secondScore": 0.83,
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fdas-phase10-8-", ignore_cleanup_errors=True) as temp_directory:
        temp_root = Path(temp_directory)
        database_path = temp_root / "isolated.db"
        storage_marker = temp_root / "storage-marker.bin"
        storage_marker.write_bytes(b"phase10.8-isolated-storage")
        storage_before = hashlib.sha256(storage_marker.read_bytes()).hexdigest()
        engine = create_engine(f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        with TestSession() as db:
            department = Department(departmentId=1, departmentName="Computer Science", status="Active")
            other_department = Department(departmentId=2, departmentName="Business Administration", status="Active")
            classroom = ClassRoom(
                classId=1,
                className="BSCS Test",
                departmentId=1,
                yearSemester="Test",
                section="T",
                status="Active",
            )
            other_classroom = ClassRoom(
                classId=2,
                className="BBA Test",
                departmentId=2,
                yearSemester="Test",
                section="T",
                status="Active",
            )
            admin_role = Role(roleId=1, roleName="Admin")
            operator_role = Role(roleId=2, roleName="Operator")
            admin = User(
                userId=1,
                fullName="Phase 10.8 Admin",
                email="phase10.8.admin@fdas.local",
                passwordHash="not-used",
                roleId=1,
                status="Approved",
                accessScope="AllDepartments",
            )
            operator = User(
                userId=2,
                fullName="Phase 10.8 Operator",
                email="phase10.8.operator@fdas.local",
                passwordHash="not-used",
                roleId=2,
                status="Approved",
                assignedDepartmentId=1,
                accessScope="Department",
            )
            students = {
                19: Student(studentId=19, rollNo="CS-2022-58", fullName="Ahmad Mughal", departmentId=1, classId=1, yearSemester="Test", section="T", status="Inactive"),
                22: Student(studentId=22, rollNo="cs-2026-789", fullName="Ahmad Mughal", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active"),
                24: Student(studentId=24, rollNo="P108-24", fullName="Distinct Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active"),
                27: Student(studentId=27, rollNo="P108-27", fullName="Incomplete Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active"),
            }
            now = datetime.now()
            session = AttendanceSession(
                sessionId=1,
                departmentId=1,
                startedByUserId=1,
                scheduledStartTime=now,
                scheduledEndTime=now + timedelta(hours=1),
                actualStartTime=now,
                status="Active",
                createdDate=date.today(),
            )
            other_session = AttendanceSession(
                sessionId=2,
                departmentId=2,
                startedByUserId=1,
                scheduledStartTime=now,
                scheduledEndTime=now + timedelta(hours=1),
                actualStartTime=now,
                status="Active",
                createdDate=date.today(),
            )
            db.add_all([
                department,
                other_department,
                classroom,
                other_classroom,
                admin_role,
                operator_role,
                admin,
                operator,
                *students.values(),
                session,
                other_session,
            ])
            db.flush()
            add_gallery(db, students[19], admin, [0.99, 0.98, 0.97])
            add_gallery(db, students[22], admin, [0.92, 0.91, 0.90, 0.87])
            add_gallery(db, students[24], admin, [0.80, 0.79, 0.78, 0.74])
            add_gallery(db, students[27], admin, [0.99, 0.98, 0.97], count=19)
            db.add(FaceTemplate(studentId=22, templatePath="storage/legacy/22.jpg", encodingData="[1.0,0.0]", encodingVersion="opencv_basic_v1", status="Encoded", isActive=True))
            db.commit()

        frame = make_png()
        query = unit_vector(1.0)
        ambiguous = matching.classify_deep_embedding(
            query,
            controlled_candidates({22: [0.90, 0.89, 0.88], 24: [0.85, 0.84, 0.83]}),
        )
        below = matching.classify_deep_embedding(
            query,
            controlled_candidates({22: [0.84, 0.83, 0.82], 24: [0.80, 0.79, 0.78]}),
        )

        with TestSession() as db:
            admin = db.query(User).filter(User.userId == 1).one()
            operator = db.query(User).filter(User.userId == 2).one()
            session = db.query(AttendanceSession).filter(AttendanceSession.sessionId == 1).one()
            other_session = db.query(AttendanceSession).filter(AttendanceSession.sessionId == 2).one()
            candidate_ids = {item.student.studentId for item in matching.load_deep_match_candidates(db, admin, 1)}
            deep_ready_22 = student_has_required_deep_embeddings(db, 22)
            deep_ready_27 = student_has_required_deep_embeddings(db, 27)
            legacy_before = db.query(FaceTemplate).filter(FaceTemplate.encodingVersion == "opencv_basic_v1").count()

            negative_statuses = ("NoFaceDetected", "MultipleFacesDetected", "FaceContinuityLost", "LivenessFailed")
            negative_results = {}
            no_legacy_calls = True
            for status_value in negative_statuses:
                before = db.query(AttendanceRecord).count()
                response, legacy_calls = asyncio.run(
                    call_live(db, admin, session.sessionId, frame, liveness_result(status_value))
                )
                negative_results[status_value] = response.get("status") == status_value and db.query(AttendanceRecord).count() == before
                no_legacy_calls = no_legacy_calls and legacy_calls == 0

            passed_liveness = liveness_result("LivenessPassed", passed=True, frame=frame)
            controlled_gate_checks = []
            for current_user, target_session_id, expected_student_id in (
                (admin, session.sessionId, 27),
                (operator, session.sessionId, 22),
                (admin, other_session.sessionId, 22),
            ):
                with patch("app.routers.attendance_marking.DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED", True), patch(
                    "app.routers.attendance_marking.verify_liveness"
                ) as rejected_liveness, patch(
                    "app.routers.attendance_marking.match_deep_face_query_burst_for_attendance"
                ) as rejected_matcher:
                    uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
                    query_uploads = [MemoryUpload(frame, index + 20) for index in range(3)]
                    rejected = asyncio.run(
                        mark_by_face_live(
                            sessionId=target_session_id,
                            challengeType="MOVE_CLOSER",
                            files=uploads,
                            queryFiles=query_uploads,
                            controlledTest=True,
                            expectedStudentId=expected_student_id,
                            current_user=current_user,
                            db=db,
                        )
                    )
                    controlled_gate_checks.append(
                        rejected.get("status") == "ControlledAttendanceUnavailable"
                        and rejected.get("attendanceMarked") is False
                        and rejected_liveness.call_count == 0
                        and rejected_matcher.call_count == 0
                    )
            below_response, legacy_calls = asyncio.run(
                call_live(db, admin, session.sessionId, frame, passed_liveness, failure_match("MatchBelowThreshold"))
            )
            no_legacy_calls = no_legacy_calls and legacy_calls == 0
            ambiguous_response, legacy_calls = asyncio.run(
                call_live(db, admin, session.sessionId, frame, passed_liveness, failure_match("AmbiguousMatch"))
            )
            no_legacy_calls = no_legacy_calls and legacy_calls == 0
            pre_success_count = db.query(AttendanceRecord).count()

            with patch.object(matching, "get_deep_face_service", return_value=ControlledDeepService(unavailable=True)):
                unavailable_result = matching.match_deep_face_bytes_for_attendance(db, admin, 1, frame)

            with patch.object(matching, "get_deep_face_service", return_value=ControlledDeepService()):
                with patch("app.routers.attendance_marking.DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED", True), patch(
                    "app.routers.attendance_marking.verify_liveness", return_value=passed_liveness
                ), patch("app.routers.attendance_marking.match_face_bytes") as legacy_matcher:
                    uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
                    query_uploads = [MemoryUpload(frame, index + 20) for index in range(3)]
                    created = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, query_uploads, True, 22, admin, db))
                    uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
                    query_uploads = [MemoryUpload(frame, index + 20) for index in range(3)]
                    duplicate = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, query_uploads, True, 22, admin, db))
                    no_legacy_calls = no_legacy_calls and legacy_matcher.call_count == 0

            row_count = db.query(AttendanceRecord).filter(AttendanceRecord.sessionId == 1).count()
            record = db.query(AttendanceRecord).filter(AttendanceRecord.sessionId == 1).one()
            legacy_after = db.query(FaceTemplate).filter(FaceTemplate.encodingVersion == "opencv_basic_v1").count()

            with patch("app.services.attendance_marking.validate_single_face_bytes", return_value={"ready": True, "status": "SingleFaceDetected", "message": "ready"}):
                no_liveness_result = mark_attendance_by_face(db, admin, 1, frame)

            with patch("app.routers.attendance_marking.verify_liveness", return_value=passed_liveness), patch(
                "app.routers.attendance_marking.match_deep_face_query_burst_for_attendance"
            ) as held_deep_matcher:
                uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
                query_uploads = [MemoryUpload(frame, index + 20) for index in range(3)]
                held = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, query_uploads, False, None, admin, db))

            result = {
                "arcface_matcher_integrated_for_attendance": DEEP_RECOGNITION_INTEGRATED_FOR_ATTENDANCE is True,
                "global_deep_attendance_remains_disabled": DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE is False,
                "legacy_matcher_not_used_for_automatic_decision": no_legacy_calls,
                "active_deep_ready_candidates_only": candidate_ids == {22, 24},
                "inactive_19_excluded": 19 not in candidate_ids,
                "deep_incomplete_27_excluded": 27 not in candidate_ids and deep_ready_27 is False,
                "canonical_22_deep_ready": deep_ready_22 is True,
                "controlled_gate_closed_by_default_and_scoped_to_admin_22_department": (
                    DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED is False
                    and all(controlled_gate_checks)
                ),
                "exactly_one_face_failures_create_no_attendance": all(negative_results.values()),
                "liveness_required_before_recognition": (
                    no_liveness_result.get("status") == "LivenessRequired"
                    and no_liveness_result.get("attendanceMarked") is False
                ),
                "deep_threshold_applied": below["status"] == "MatchBelowThreshold" and below["thresholdUsed"] == 0.85,
                "deep_margin_applied": ambiguous["status"] == "AmbiguousMatch" and ambiguous["requiredMargin"] == 0.07,
                "below_threshold_creates_no_attendance": below_response.get("status") == "MatchBelowThreshold" and pre_success_count == 0,
                "ambiguous_match_creates_no_attendance": ambiguous_response.get("status") == "AmbiguousMatch" and pre_success_count == 0,
                "deep_unavailable_fails_closed": unavailable_result.get("status") == "DeepRecognitionUnavailable",
                "successful_deep_match_creates_one_row": (
                    created.get("attendanceMarked") is True
                    and created.get("status") == "AttendanceMarked"
                    and created.get("studentId") == 22
                    and row_count == 1
                ),
                "duplicate_attempt_creates_no_second_row": (
                    duplicate.get("attendanceMarked") is False
                    and duplicate.get("status") == "DuplicateAttendance"
                    and row_count == 1
                ),
                "attendance_metadata_identifies_deep_recognition": (
                    record.recognitionProvider == DEEP_FACE_PROVIDER
                    and record.recognitionEncodingVersion == DEEP_FACE_ENCODING_VERSION
                    and record.recognitionMethod == "median_of_3_mean_top_3"
                    and record.identityMargin is not None
                    and record.livenessStatus == "Passed"
                    and created.get("thresholdUsed") == DEEP_CONTROLLED_MATCH_THRESHOLD == 0.80
                    and created.get("requiredMargin") == DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN == 0.10
                ),
                "raw_embeddings_not_exposed": "embedding" not in json.dumps(created, default=str).lower(),
                "legacy_data_preserved_for_rollback": legacy_before == legacy_after == 1,
                "safety_hold_blocks_noncontrolled_requests": (
                    IDENTITY_MATCHING_SAFETY_HOLD is True
                    and held.get("status") == "AttendanceSafetyHold"
                    and held.get("attendanceMarked") is False
                    and held_deep_matcher.call_count == 0
                ),
                "isolated_storage_preserved": storage_before == hashlib.sha256(storage_marker.read_bytes()).hexdigest(),
                "preliminary_policy_unchanged": (
                    DEEP_MATCH_SCORING_METHOD == "mean_top_3"
                    and DEEP_MATCH_THRESHOLD == 0.85
                    and DEEP_MATCH_MIN_IDENTITY_MARGIN == 0.07
                    and DEEP_CONTROLLED_MATCH_THRESHOLD == 0.80
                    and DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN == 0.10
                    and FACE_MATCH_THRESHOLD == 0.75
                ),
            }

        engine.dispose()

    result["phase10_8_passed"] = all(bool(value) for value in result.values())
    for name, passed in result.items():
        print(f"{name}={bool(passed)}")
    if not result["phase10_8_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
