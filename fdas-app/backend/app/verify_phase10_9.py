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
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.config import (
    DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_MATCH_THRESHOLD,
    DEEP_QUERY_BURST_COUNT,
    DEEP_QUERY_CONSENSUS_MIN_COUNT,
    DEEP_QUERY_MAX_RETRIES,
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    FACE_MATCH_THRESHOLD,
    IDENTITY_MATCHING_SAFETY_HOLD,
    LIVENESS_ALLOWED_CHALLENGES,
    LIVENESS_FRAME_COUNT,
    LIVENESS_MIN_AREA_CHANGE_RATIO,
    LIVENESS_MIN_CENTER_SHIFT_RATIO,
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
from app.services.attendance_marking import create_attendance_from_match_result, mark_attendance_by_face
from app.services.deep_face import DEEP_FACE_PROVIDER, DeepEncodingResult, DeepFaceService
from app.services.deep_face_matching import DeepStudentScore, match_deep_face_query_burst_for_attendance
from app.services.face_processing import validate_single_face_bytes
from app.services.liveness import LIVENESS_STATUS_FAILED, LIVENESS_STATUS_PASSED, LivenessFrame, LivenessResult, analyze_liveness_frames, evaluate_liveness_frames


class MemoryUpload:
    def __init__(self, content: bytes, index: int):
        self.filename = f"phase10_9_{index}.png"
        self.content_type = "image/png"
        self._content = content

    async def read(self) -> bytes:
        return self._content


class ScriptedDeepService:
    def __init__(self, results: list[DeepEncodingResult]):
        self.results = iter(results)

    def encode_attendance_query_bytes(self, _content: bytes) -> DeepEncodingResult:
        return next(self.results)


class BoxDetector:
    def __init__(self, boxes: list[tuple[int, int, int, int]]):
        self.boxes = boxes

    def detect_face_boxes(self, _image):
        return self.boxes


def unit_vector(score: float = 1.0) -> np.ndarray:
    vector = np.zeros(512, dtype=np.float64)
    vector[0] = score
    vector[1] = math.sqrt(max(0.0, 1.0 - score * score))
    return vector


def encoded_result(*, quality_passed: bool = True) -> DeepEncodingResult:
    return DeepEncodingResult(
        success=quality_passed,
        status="Encoded" if quality_passed else "PoorFaceQuality",
        message="controlled quality result",
        haarFaceCount=1,
        deepFaceCount=1,
        embeddingDimension=512 if quality_passed else None,
        l2Norm=1.0 if quality_passed else None,
        processingMilliseconds=1.0,
        embedding=unit_vector().astype(np.float32) if quality_passed else None,
        faceBox=(40, 35, 80, 80),
        quality={"passed": quality_passed, "reason": "quality_checks_passed" if quality_passed else "blurred"},
    )


def score(student: Student, value: float, key: int) -> DeepStudentScore:
    return DeepStudentScore(student, value, key, key, 20)


def png_bytes() -> bytes:
    image = np.full((160, 160, 3), 180, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not create verifier image")
    return encoded.tobytes()


def add_deep_gallery(db, student: Student, admin: User) -> None:
    for index in range(20):
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
                embeddingData=json.dumps(unit_vector().tolist()),
                embeddingDimension=512,
                modelName="buffalo_l",
                sourceImageSha256=hashlib.sha256(f"10.9-{index}".encode()).hexdigest(),
                l2Norm=1.0,
                isActive=True,
            )
        )


def live_result(*, passed: bool, status_value: str, frame: bytes) -> LivenessResult:
    return LivenessResult(
        passed=passed,
        status=status_value,
        message=f"controlled {status_value}",
        livenessStatus=LIVENESS_STATUS_PASSED if passed else LIVENESS_STATUS_FAILED,
        bestFrameBytes=frame if passed else None,
        diagnostics={"challenge": "MOVE_CLOSER", "reason": status_value},
    )


def accepted_match(student_id: int = 22) -> dict:
    return {
        "matched": True,
        "status": "DeepMatched",
        "message": "controlled consensus passed",
        "studentId": student_id,
        "studentName": "Ahmad Mughal" if student_id == 22 else "Wrong Identity",
        "rollNo": "cs-2026-789" if student_id == 22 else "WRONG",
        "classId": 1,
        "departmentId": 1,
        "similarityScore": 0.89,
        "secondSimilarityScore": 0.30,
        "scoreMargin": 0.59,
        "thresholdUsed": DEEP_MATCH_THRESHOLD,
        "requiredMargin": DEEP_MATCH_MIN_IDENTITY_MARGIN,
        "aggregationMethod": "median_of_3_mean_top_3",
        "recognitionProvider": DEEP_FACE_PROVIDER,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "topStudentId": student_id,
        "topScore": 0.89,
        "secondStudentId": 24,
        "secondScore": 0.30,
        "queryCount": 3,
        "validQueryCount": 3,
        "consensusStudentId": student_id,
        "consensusCount": 3,
        "queryTopStudentIds": [student_id, student_id, student_id],
        "queryTopScores": [0.88, 0.89, 0.90],
        "queryQuality": [{"passed": True}] * 3,
        "retryable": False,
    }


def synthetic_liveness_frames(boxes: list[tuple[int, int, int, int]]) -> list[LivenessFrame]:
    return [
        LivenessFrame(
            image_bytes=f"phase10.9a-{index}".encode("ascii"),
            width=200,
            height=200,
            face_count=1,
            face_box=box,
            face_descriptor=[1.0, 0.0, 0.0],
        )
        for index, box in enumerate(boxes)
    ]


def main() -> None:
    frame = png_bytes()
    student22 = Student(studentId=22, rollNo="cs-2026-789", fullName="Ahmad Mughal", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
    student24 = Student(studentId=24, rollNo="P109-24", fullName="Distinct Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
    student28 = Student(studentId=28, rollNo="P109-28", fullName="Other Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
    admin_for_matching = User(userId=100, fullName="Matcher Admin", email="matcher@fdas.local", passwordHash="unused", accessScope="AllDepartments", status="Approved")
    accepted_rankings = [
        [score(student22, 0.88, 1), score(student24, 0.30, 2)],
        [score(student22, 0.90, 1), score(student24, 0.31, 2)],
        [score(student22, 0.89, 1), score(student24, 0.29, 2)],
    ]
    split_rankings = [
        [score(student22, 0.90, 1), score(student24, 0.40, 2), score(student28, 0.30, 3)],
        [score(student24, 0.91, 2), score(student22, 0.89, 1), score(student28, 0.35, 3)],
        [score(student28, 0.92, 3), score(student22, 0.88, 1), score(student24, 0.40, 2)],
    ]
    below_rankings = [[score(student22, 0.848, 1), score(student24, 0.30, 2)] for _ in range(3)]
    margin_rankings = [[score(student22, 0.90, 1), score(student24, 0.85, 2)] for _ in range(3)]

    def run_burst(rankings, encodings=None):
        service = ScriptedDeepService(encodings or [encoded_result(), encoded_result(), encoded_result()])
        with patch("app.services.deep_face_matching.get_deep_face_service", return_value=service), patch(
            "app.services.deep_face_matching.load_deep_match_candidates", return_value=[object()]
        ), patch("app.services.deep_face_matching.rank_deep_candidates", side_effect=rankings):
            return match_deep_face_query_burst_for_attendance(
                db=None,
                current_user=admin_for_matching,
                department_id=1,
                image_bytes_list=[frame, frame, frame],
            )

    consensus = run_burst(accepted_rankings)
    split = run_burst(split_rankings)
    below = run_burst(below_rankings)
    narrow = run_burst(margin_rankings)
    poor = run_burst(accepted_rankings, [encoded_result(quality_passed=False), encoded_result(), encoded_result()])

    baseline = [(50, 50, 60, 60)] * 2
    sustained_closer = synthetic_liveness_frames(
        baseline + [(49, 49, 62, 62), (47, 47, 65, 65), (45, 45, 68, 68), (44, 44, 70, 70), (43, 43, 72, 72), (43, 43, 72, 72), (43, 43, 72, 72), (44, 44, 70, 70), (44, 44, 70, 70), (44, 44, 70, 70)]
    )
    static_sequence = synthetic_liveness_frames(baseline + [(50, 50, 60, 60)] * 10)
    one_frame_spike = synthetic_liveness_frames(
        baseline + [(50, 50, 60, 60), (50, 50, 60, 60), (45, 45, 72, 72), (50, 50, 60, 60), (50, 50, 60, 60), (50, 50, 60, 60), (50, 50, 60, 60), (50, 50, 60, 60), (50, 50, 60, 60), (50, 50, 60, 60)]
    )
    sustained_result = evaluate_liveness_frames(sustained_closer, "MOVE_CLOSER")
    static_result = evaluate_liveness_frames(static_sequence, "MOVE_CLOSER")
    spike_result = evaluate_liveness_frames(one_frame_spike, "MOVE_CLOSER")
    lateral_rejected = True
    for removed_challenge in ("MOVE_LEFT", "MOVE_RIGHT"):
        try:
            evaluate_liveness_frames(static_sequence, removed_challenge)
            lateral_rejected = False
        except HTTPException as exc:
            lateral_rejected = lateral_rejected and exc.status_code == 422

    textured = np.indices((160, 160)).sum(axis=0) % 2 * 80 + 100
    textured = np.repeat(textured[:, :, None], 3, axis=2).astype(np.uint8)
    quality_good = DeepFaceService._query_quality(textured, (35, 35, 90, 90))
    quality_bad = DeepFaceService._query_quality(np.full((160, 160, 3), 180, dtype=np.uint8), (70, 70, 12, 12))

    with patch("app.services.face_processing.detect_faces", return_value=[(20, 20, 80, 80), (4, 4, 25, 25)]), patch(
        "app.services.liveness.detect_faces", return_value=[(20, 20, 80, 80), (4, 4, 25, 25)]
    ), patch(
        "app.services.deep_face.get_deep_face_service", return_value=BoxDetector([(20, 20, 80, 80)])
    ):
        reconciled_guard = validate_single_face_bytes(frame, allow_deep_reconciliation=True)
        reconciled_liveness = analyze_liveness_frames([frame])[0]
    with patch("app.services.face_processing.detect_faces", return_value=[(20, 20, 80, 80), (4, 4, 25, 25)]), patch(
        "app.services.deep_face.get_deep_face_service", return_value=BoxDetector([(20, 20, 70, 70), (90, 30, 55, 55)])
    ):
        genuine_multiple_guard = validate_single_face_bytes(frame, allow_deep_reconciliation=True)

    with tempfile.TemporaryDirectory(prefix="fdas-phase10-9-", ignore_cleanup_errors=True) as temp_directory:
        database_path = Path(temp_directory) / "isolated.db"
        engine = create_engine(f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        with Session() as db:
            department = Department(departmentId=1, departmentName="Computer Science", status="Active")
            classroom = ClassRoom(classId=1, className="BSCS Test", departmentId=1, yearSemester="Test", section="T", status="Active")
            role = Role(roleId=1, roleName="Admin")
            admin = User(userId=1, fullName="Phase 10.9 Admin", email="phase10.9@fdas.local", passwordHash="unused", roleId=1, accessScope="AllDepartments", status="Approved")
            db_student = Student(studentId=22, rollNo="cs-2026-789", fullName="Ahmad Mughal", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
            now = datetime.now()
            session = AttendanceSession(sessionId=1, departmentId=1, startedByUserId=1, scheduledStartTime=now, scheduledEndTime=now + timedelta(hours=1), actualStartTime=now, status="Active", createdDate=date.today())
            db.add_all([department, classroom, role, admin, db_student, session])
            db.flush()
            add_deep_gallery(db, db_student, admin)
            db.commit()

            transient = {**accepted_match(), "matched": False, "status": "MatchBelowThreshold", "message": "fresh query required", "retryable": True}
            first_failure = create_attendance_from_match_result(db, session, transient, LIVENESS_STATUS_PASSED)
            second_failure = create_attendance_from_match_result(db, session, transient, LIVENESS_STATUS_PASSED)
            rows_before_success = db.query(AttendanceRecord).count()
            created = create_attendance_from_match_result(db, session, accepted_match(), LIVENESS_STATUS_PASSED)
            duplicate = create_attendance_from_match_result(db, session, accepted_match(), LIVENESS_STATUS_PASSED)
            rows_after_duplicate = db.query(AttendanceRecord).count()
            db.query(AttendanceRecord).delete()
            db.commit()

            uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
            queries = [MemoryUpload(frame, index + 20) for index in range(3)]
            multiple = live_result(passed=False, status_value="MultipleFacesDetected", frame=frame)
            with patch("app.routers.attendance_marking.DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED", True), patch(
                "app.routers.attendance_marking.DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE", False
            ), patch(
                "app.routers.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", True
            ), patch(
                "app.routers.attendance_marking.verify_liveness", return_value=multiple
            ), patch(
                "app.routers.attendance_marking.match_deep_face_query_burst_for_attendance"
            ) as deep_matcher, patch("app.routers.attendance_marking.match_face_bytes") as legacy_matcher:
                multiple_response = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, queries, True, 22, admin, db))
            rows_after_multiple = db.query(AttendanceRecord).count()

            uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
            queries = [MemoryUpload(frame, index + 20) for index in range(3)]
            passed_live = live_result(passed=True, status_value="LivenessPassed", frame=frame)
            with patch("app.routers.attendance_marking.DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED", True), patch(
                "app.routers.attendance_marking.DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE", False
            ), patch(
                "app.routers.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", True
            ), patch(
                "app.routers.attendance_marking.verify_liveness", return_value=passed_live
            ), patch(
                "app.routers.attendance_marking.match_deep_face_query_burst_for_attendance", return_value=accepted_match(24)
            ), patch("app.routers.attendance_marking.match_face_bytes") as legacy_wrong:
                wrong_response = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, queries, True, 22, admin, db))
            rows_after_wrong = db.query(AttendanceRecord).count()

            with patch("app.services.attendance_marking.validate_single_face_bytes", return_value={"ready": True, "status": "SingleFaceDetected", "message": "ready"}):
                no_liveness = mark_attendance_by_face(db, admin, 1, frame)

        engine.dispose()

    checks = {
        "three_query_consensus_accepts_same_identity": consensus["matched"] is True and consensus["consensusCount"] == 3,
        "split_identity_queries_fail_closed": split["status"] == "QueryConsensusFailed" and split["matched"] is False,
        "deep_threshold_0_85_enforced": below["status"] == "MatchBelowThreshold" and DEEP_MATCH_THRESHOLD == 0.85,
        "identity_margin_0_07_enforced": narrow["status"] == "AmbiguousMatch" and DEEP_MATCH_MIN_IDENTITY_MARGIN == 0.07,
        "quality_rejection_is_retryable": poor["status"] == "PoorFaceQuality" and poor["retryable"] is True,
        "quality_gate_measures_evidence": quality_good["passed"] is True and quality_bad["passed"] is False,
        "haar_background_false_positive_reconciled": reconciled_guard["ready"] is True and reconciled_guard["deepReconciled"] is True and reconciled_liveness.deep_reconciled is True,
        "two_genuine_deep_faces_remain_blocked": genuine_multiple_guard["status"] == "MultipleFacesDetected" and genuine_multiple_guard["ready"] is False,
        "retry_failures_create_no_premature_attendance": first_failure["attendanceMarked"] is False and second_failure["attendanceMarked"] is False and rows_before_success == 0,
        "successful_retry_creates_exactly_one_row": created["attendanceMarked"] is True and rows_after_duplicate == 1,
        "duplicate_prevention_intact": duplicate["status"] == "DuplicateAttendance" and duplicate["attendanceMarked"] is False,
        "liveness_multiple_face_short_circuits_recognition": multiple_response["status"] == "MultipleFacesDetected" and deep_matcher.call_count == 0 and rows_after_multiple == 0,
        "controlled_wrong_identity_creates_no_attendance": wrong_response["status"] == "ControlledIdentityMismatch" and rows_after_wrong == 0,
        "legacy_matcher_never_used": legacy_matcher.call_count == 0 and legacy_wrong.call_count == 0,
        "liveness_endpoint_remains_required": no_liveness["status"] == "LivenessRequired",
        "retry_limit_is_two_fresh_attempts": DEEP_QUERY_MAX_RETRIES == 2,
        "consensus_policy_is_two_of_three": DEEP_QUERY_BURST_COUNT == 3 and DEEP_QUERY_CONSENSUS_MIN_COUNT == 2,
        "legacy_threshold_unchanged": FACE_MATCH_THRESHOLD == 0.75,
        "final_deep_activation_released_safety_hold": (
            DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE is True
            and IDENTITY_MATCHING_SAFETY_HOLD is False
        ),
        "controlled_test_default_remains_fail_closed": DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED is False,
        "liveness_thresholds_not_lowered": LIVENESS_MIN_CENTER_SHIFT_RATIO == 0.08 and LIVENESS_MIN_AREA_CHANGE_RATIO == 0.12,
        "closer_only_challenge_policy": LIVENESS_ALLOWED_CHALLENGES == ["MOVE_CLOSER"] and lateral_rejected,
        "sustained_closer_passes": sustained_result.passed is True and sustained_result.diagnostics.get("maximumConsecutiveSupportingFrames", 0) >= 2,
        "static_sequence_fails": static_result.passed is False,
        "single_frame_area_spike_fails": spike_result.passed is False and spike_result.diagnostics.get("maximumConsecutiveSupportingFrames") == 1,
        "post_go_sampling_window_extended": LIVENESS_FRAME_COUNT == 12,
    }
    checks["phase10_9_passed"] = all(checks.values())
    for name, passed in checks.items():
        print(f"{name}={bool(passed)}")
    if not checks["phase10_9_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
