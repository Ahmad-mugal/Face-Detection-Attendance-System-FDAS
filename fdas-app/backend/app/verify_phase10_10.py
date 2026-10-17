from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

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
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    IDENTITY_MATCHING_SAFETY_HOLD,
    LIVENESS_ALLOWED_CHALLENGES,
    LIVENESS_FRAME_COUNT,
    LIVENESS_MIN_AREA_CHANGE_RATIO,
    LIVENESS_MIN_DIRECTIONAL_FRAME_COUNT,
)
from app.database import Base
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.routers.attendance_marking import mark_by_face_live
from app.services.deep_face_matching import (
    load_deep_match_candidates,
    match_deep_face_query_burst_for_attendance,
)
from app.services.liveness import evaluate_liveness_frames
from app.verify_phase10_9 import (
    MemoryUpload,
    ScriptedDeepService,
    accepted_match,
    add_deep_gallery,
    encoded_result,
    live_result,
    png_bytes,
    score,
    synthetic_liveness_frames,
)


PREFLIGHT_ENV = "FDAS_PHASE10_10_PREFLIGHT"


def run_burst(rankings, *, encodings=None) -> dict:
    frame = png_bytes()
    service = ScriptedDeepService(encodings or [encoded_result(), encoded_result(), encoded_result()])
    matcher_user = User(
        userId=900,
        fullName="Phase 10.10 Matcher",
        email="phase10.10.matcher@fdas.local",
        passwordHash="unused",
        accessScope="AllDepartments",
        status="Approved",
    )
    with patch("app.services.deep_face_matching.get_deep_face_service", return_value=service), patch(
        "app.services.deep_face_matching.load_deep_match_candidates", return_value=[object()]
    ), patch("app.services.deep_face_matching.rank_deep_candidates", side_effect=rankings):
        return match_deep_face_query_burst_for_attendance(
            db=None,
            current_user=matcher_user,
            department_id=1,
            image_bytes_list=[frame, frame, frame],
        )


def call_live(
    db,
    user: User,
    session_id: int,
    frame: bytes,
    *,
    liveness_result,
    match_result: dict | None = None,
):
    uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
    queries = [MemoryUpload(frame, index + 100) for index in range(DEEP_QUERY_BURST_COUNT)]
    with patch("app.routers.attendance_marking.DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE", True), patch(
        "app.routers.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", False
    ), patch(
        "app.routers.attendance_marking.ATTENDANCE_MODE", "SECURE_SINGLE_FACE"
    ), patch(
        "app.services.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", False
    ), patch("app.routers.attendance_marking.DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED", False), patch(
        "app.routers.attendance_marking.verify_liveness", return_value=liveness_result
    ), patch("app.routers.attendance_marking.match_face_bytes") as legacy_matcher:
        if match_result is None:
            with patch("app.routers.attendance_marking.match_deep_face_query_burst_for_attendance") as deep_matcher:
                result = asyncio.run(
                    mark_by_face_live(session_id, "MOVE_CLOSER", uploads, queries, False, None, user, db)
                )
        else:
            with patch(
                "app.routers.attendance_marking.match_deep_face_query_burst_for_attendance",
                return_value=match_result,
            ) as deep_matcher:
                result = asyncio.run(
                    mark_by_face_live(session_id, "MOVE_CLOSER", uploads, queries, False, None, user, db)
                )
    return result, deep_matcher.call_count, legacy_matcher.call_count


def main() -> None:
    preflight = os.getenv(PREFLIGHT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
    frame = png_bytes()
    student22 = Student(studentId=22, rollNo="cs-2026-789", fullName="Ahmad Mughal", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
    student24 = Student(studentId=24, rollNo="P1010-24", fullName="Distinct Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
    student28 = Student(studentId=28, rollNo="P1010-28", fullName="Other Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")

    two_of_three_rankings = [
        [score(student22, 0.90, 1), score(student24, 0.25, 2), score(student28, 0.20, 3)],
        [score(student22, 0.88, 1), score(student24, 0.24, 2), score(student28, 0.20, 3)],
        [score(student24, 0.91, 2), score(student22, 0.87, 1), score(student28, 0.20, 3)],
    ]
    one_of_three_rankings = [
        [score(student22, 0.90, 1), score(student24, 0.30, 2), score(student28, 0.20, 3)],
        [score(student24, 0.91, 2), score(student22, 0.89, 1), score(student28, 0.30, 3)],
        [score(student28, 0.92, 3), score(student22, 0.88, 1), score(student24, 0.30, 2)],
    ]
    below_threshold_rankings = [
        [score(student22, 0.849, 1), score(student24, 0.25, 2), score(student28, 0.20, 3)]
        for _ in range(3)
    ]
    below_margin_rankings = [
        [score(student22, 0.90, 1), score(student24, 0.831, 2), score(student28, 0.20, 3)]
        for _ in range(3)
    ]

    two_of_three = run_burst(two_of_three_rankings)
    one_of_three = run_burst(one_of_three_rankings)
    below_threshold = run_burst(below_threshold_rankings)
    below_margin = run_burst(below_margin_rankings)
    poor_quality = run_burst(
        two_of_three_rankings,
        encodings=[encoded_result(quality_passed=False), encoded_result(), encoded_result()],
    )

    baseline = [(50, 50, 60, 60)] * 2
    sustained_closer = synthetic_liveness_frames(
        baseline
        + [
            (49, 49, 62, 62),
            (47, 47, 65, 65),
            (45, 45, 68, 68),
            (44, 44, 70, 70),
            (43, 43, 72, 72),
            (43, 43, 72, 72),
            (43, 43, 72, 72),
            (44, 44, 70, 70),
            (44, 44, 70, 70),
            (44, 44, 70, 70),
        ]
    )
    static_sequence = synthetic_liveness_frames(baseline + [(50, 50, 60, 60)] * 10)
    sustained_result = evaluate_liveness_frames(sustained_closer, "MOVE_CLOSER")
    static_result = evaluate_liveness_frames(static_sequence, "MOVE_CLOSER")

    with tempfile.TemporaryDirectory(prefix="fdas-phase10-10-", ignore_cleanup_errors=True) as temp_directory:
        database_path = Path(temp_directory) / "isolated.db"
        engine = create_engine(f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        with Session() as db:
            department1 = Department(departmentId=1, departmentName="Computer Science", status="Active")
            department2 = Department(departmentId=2, departmentName="IT", status="Active")
            class1 = ClassRoom(classId=1, className="BSCS Test", departmentId=1, yearSemester="Test", section="T", status="Active")
            class2 = ClassRoom(classId=2, className="BSIT Test", departmentId=2, yearSemester="Test", section="T", status="Active")
            admin_role = Role(roleId=1, roleName="Admin")
            operator_role = Role(roleId=2, roleName="Operator")
            admin = User(userId=1, fullName="Phase 10.10 Admin", email="phase10.10@fdas.local", passwordHash="unused", roleId=1, accessScope="AllDepartments", status="Approved")
            operator = User(userId=2, fullName="IT Operator", email="phase10.10.operator@fdas.local", passwordHash="unused", roleId=2, assignedDepartmentId=2, accessScope="Department", status="Approved")
            db_student22 = Student(studentId=22, rollNo="cs-2026-789", fullName="Ahmad Mughal", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
            db_student24 = Student(studentId=24, rollNo="P1010-24", fullName="Distinct Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
            inactive19 = Student(studentId=19, rollNo="CS-2022-58", fullName="Inactive Duplicate", departmentId=1, classId=1, yearSemester="Test", section="T", status="Inactive")
            incomplete27 = Student(studentId=27, rollNo="P1010-27", fullName="Incomplete Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
            incomplete30 = Student(studentId=30, rollNo="P1010-30", fullName="IT Incomplete", departmentId=2, classId=2, yearSemester="Test", section="T", status="Active")
            now = datetime.now()
            session1 = AttendanceSession(sessionId=1, departmentId=1, startedByUserId=1, scheduledStartTime=now, scheduledEndTime=now + timedelta(hours=1), actualStartTime=now, status="Active", createdDate=date.today())
            session2 = AttendanceSession(sessionId=2, departmentId=2, startedByUserId=1, scheduledStartTime=now, scheduledEndTime=now + timedelta(hours=1), actualStartTime=now, status="Active", createdDate=date.today())
            db.add_all([
                department1,
                department2,
                class1,
                class2,
                admin_role,
                operator_role,
                admin,
                operator,
                db_student22,
                db_student24,
                inactive19,
                incomplete27,
                incomplete30,
                session1,
                session2,
            ])
            db.flush()
            add_deep_gallery(db, db_student22, admin)
            add_deep_gallery(db, db_student24, admin)
            add_deep_gallery(db, inactive19, admin)
            db.commit()

            candidate_ids = {candidate.student.studentId for candidate in load_deep_match_candidates(db, admin, 1)}

            deep_service = ScriptedDeepService([encoded_result(), encoded_result(), encoded_result()])
            with patch("app.services.deep_face_matching.get_deep_face_service", return_value=deep_service):
                deep_incomplete_match = match_deep_face_query_burst_for_attendance(
                    db,
                    admin,
                    2,
                    [frame, frame, frame],
                )

            passed_live = live_result(passed=True, status_value="LivenessPassed", frame=frame)
            multiple_live = live_result(passed=False, status_value="MultipleFacesDetected", frame=frame)
            continuity_live = live_result(passed=False, status_value="FaceContinuityLost", frame=frame)

            multiple_response, multiple_deep_calls, multiple_legacy_calls = call_live(
                db, admin, 1, frame, liveness_result=multiple_live
            )
            continuity_response, continuity_deep_calls, continuity_legacy_calls = call_live(
                db, admin, 1, frame, liveness_result=continuity_live
            )
            poor_response, poor_deep_calls, poor_legacy_calls = call_live(
                db, admin, 1, frame, liveness_result=passed_live, match_result=poor_quality
            )
            incomplete_response, incomplete_deep_calls, incomplete_legacy_calls = call_live(
                db, admin, 2, frame, liveness_result=passed_live, match_result=deep_incomplete_match
            )

            wrong_department_blocked = False
            try:
                call_live(db, operator, 1, frame, liveness_result=passed_live, match_result=two_of_three)
            except HTTPException as exc:
                wrong_department_blocked = exc.status_code == 403

            created, created_deep_calls, created_legacy_calls = call_live(
                db, admin, 1, frame, liveness_result=passed_live, match_result=two_of_three
            )
            duplicate, duplicate_deep_calls, duplicate_legacy_calls = call_live(
                db, admin, 1, frame, liveness_result=passed_live, match_result=two_of_three
            )
            final_row_count = db.query(AttendanceRecord).count()

        engine.dispose()

    expected_activation_state = (
        DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE is False and IDENTITY_MATCHING_SAFETY_HOLD is True
        if preflight
        else DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE is True and IDENTITY_MATCHING_SAFETY_HOLD is False
    )
    all_legacy_calls = sum(
        [
            multiple_legacy_calls,
            continuity_legacy_calls,
            poor_legacy_calls,
            incomplete_legacy_calls,
            created_legacy_calls,
            duplicate_legacy_calls,
        ]
    )
    checks = {
        "activation_state_matches_verification_stage": expected_activation_state,
        "production_policy_remains_0_85_0_07": DEEP_MATCH_THRESHOLD == 0.85 and DEEP_MATCH_MIN_IDENTITY_MARGIN == 0.07,
        "normal_query_policy_is_two_of_three": DEEP_QUERY_BURST_COUNT == 3 and DEEP_QUERY_CONSENSUS_MIN_COUNT == 2,
        "controlled_gate_not_required_for_normal_path": DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED is False,
        "legacy_automatic_matcher_unavailable": all_legacy_calls == 0,
        "exact_one_face_required": multiple_response["status"] == "MultipleFacesDetected" and multiple_deep_calls == 0,
        "continuity_required": continuity_response["status"] == "FaceContinuityLost" and continuity_deep_calls == 0,
        "move_closer_only_policy": LIVENESS_ALLOWED_CHALLENGES == ["MOVE_CLOSER"] and LIVENESS_MIN_AREA_CHANGE_RATIO == 0.12,
        "sustained_move_closer_passes": sustained_result.passed is True and sustained_result.diagnostics.get("maximumConsecutiveSupportingFrames", 0) >= LIVENESS_MIN_DIRECTIONAL_FRAME_COUNT == 2,
        "stationary_static_frames_rejected": static_result.passed is False,
        "poor_face_quality_creates_no_attendance": poor_response["status"] == "PoorFaceQuality" and poor_response["attendanceMarked"] is False and poor_deep_calls == 1,
        "one_of_three_consensus_rejected": one_of_three["status"] == "QueryConsensusFailed" and one_of_three["matched"] is False,
        "two_of_three_consensus_permitted": two_of_three["matched"] is True and two_of_three["consensusCount"] == 2 and two_of_three["thresholdUsed"] == 0.85,
        "score_below_0_85_rejected": below_threshold["status"] == "MatchBelowThreshold" and below_threshold["matched"] is False,
        "margin_below_0_07_rejected": below_margin["status"] == "AmbiguousMatch" and below_margin["matched"] is False,
        "deep_incomplete_student_fails_closed": deep_incomplete_match["status"] == "DeepEnrollmentIncomplete" and incomplete_response["status"] == "DeepEnrollmentIncomplete" and incomplete_response["attendanceMarked"] is False and incomplete_deep_calls == 1,
        "inactive_student_19_excluded": 19 not in candidate_ids,
        "deep_incomplete_student_27_excluded": 27 not in candidate_ids,
        "active_deep_ready_candidates_retained": candidate_ids == {22, 24},
        "wrong_department_rejected": wrong_department_blocked,
        "successful_deep_identity_creates_one_row": created["attendanceMarked"] is True and created["studentId"] == 22 and created_deep_calls == 1,
        "duplicate_creates_no_second_row": duplicate["status"] == "DuplicateAttendance" and duplicate["attendanceMarked"] is False and final_row_count == 1 and duplicate_deep_calls == 1,
    }
    checks["phase10_10_passed"] = all(checks.values())
    print(f"verification_stage={'preflight' if preflight else 'final'}")
    for name, passed in checks.items():
        print(f"{name}={bool(passed)}")
    if not checks["phase10_10_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
