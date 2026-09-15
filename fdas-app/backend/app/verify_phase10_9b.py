from __future__ import annotations

import asyncio
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401
from app.config import (
    DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_CONTROLLED_MATCH_THRESHOLD,
    DEEP_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_MATCH_THRESHOLD,
    DEEP_QUERY_CONSENSUS_MIN_COUNT,
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    IDENTITY_MATCHING_SAFETY_HOLD,
    LIVENESS_ALLOWED_CHALLENGES,
    LIVENESS_FRAME_COUNT,
    LIVENESS_MIN_AREA_CHANGE_RATIO,
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
from app.services.deep_face_matching import match_deep_face_query_burst_for_attendance
from app.services.liveness import LIVENESS_STATUS_FAILED
from app.verify_phase10_9 import (
    MemoryUpload,
    ScriptedDeepService,
    accepted_match,
    add_deep_gallery,
    encoded_result,
    live_result,
    png_bytes,
    score,
)


def run_burst(rankings, *, threshold: float, margin: float) -> dict:
    frame = png_bytes()
    service = ScriptedDeepService([encoded_result(), encoded_result(), encoded_result()])
    with patch("app.services.deep_face_matching.get_deep_face_service", return_value=service), patch(
        "app.services.deep_face_matching.load_deep_match_candidates", return_value=[object()]
    ), patch("app.services.deep_face_matching.rank_deep_candidates", side_effect=rankings):
        return match_deep_face_query_burst_for_attendance(
            db=None,
            current_user=User(
                userId=100,
                fullName="Phase 10.9B Matcher",
                email="phase10.9b.matcher@fdas.local",
                passwordHash="unused",
                accessScope="AllDepartments",
                status="Approved",
            ),
            department_id=1,
            image_bytes_list=[frame, frame, frame],
            threshold=threshold,
            required_margin=margin,
        )


def main() -> None:
    student22 = Student(studentId=22, rollNo="cs-2026-789", fullName="Ahmad Mughal", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
    student24 = Student(studentId=24, rollNo="P109B-24", fullName="Distinct Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
    student28 = Student(studentId=28, rollNo="P109B-28", fullName="Other Student", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")

    two_of_three = [
        [score(student22, 0.81, 1), score(student24, 0.30, 2), score(student28, 0.20, 3)],
        [score(student22, 0.82, 1), score(student24, 0.31, 2), score(student28, 0.20, 3)],
        [score(student24, 0.83, 2), score(student22, 0.79, 1), score(student28, 0.20, 3)],
    ]
    one_of_three = [
        [score(student22, 0.82, 1), score(student24, 0.30, 2), score(student28, 0.20, 3)],
        [score(student24, 0.83, 2), score(student22, 0.81, 1), score(student28, 0.20, 3)],
        [score(student28, 0.84, 3), score(student22, 0.80, 1), score(student24, 0.30, 2)],
    ]
    below_controlled_score = [
        [score(student22, 0.799, 1), score(student24, 0.25, 2), score(student28, 0.20, 3)]
        for _ in range(3)
    ]
    below_controlled_margin = [
        [score(student22, 0.82, 1), score(student24, 0.721, 2), score(student28, 0.20, 3)]
        for _ in range(3)
    ]

    controlled_accept = run_burst(
        two_of_three,
        threshold=DEEP_CONTROLLED_MATCH_THRESHOLD,
        margin=DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
    )
    production_reject = run_burst(
        two_of_three,
        threshold=DEEP_MATCH_THRESHOLD,
        margin=DEEP_MATCH_MIN_IDENTITY_MARGIN,
    )
    consensus_reject = run_burst(
        one_of_three,
        threshold=DEEP_CONTROLLED_MATCH_THRESHOLD,
        margin=DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
    )
    score_reject = run_burst(
        below_controlled_score,
        threshold=DEEP_CONTROLLED_MATCH_THRESHOLD,
        margin=DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
    )
    margin_reject = run_burst(
        below_controlled_margin,
        threshold=DEEP_CONTROLLED_MATCH_THRESHOLD,
        margin=DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
    )

    frame = png_bytes()
    with tempfile.TemporaryDirectory(prefix="fdas-phase10-9b-", ignore_cleanup_errors=True) as temp_directory:
        database_path = Path(temp_directory) / "isolated.db"
        engine = create_engine(f"sqlite:///{database_path.as_posix()}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        with Session() as db:
            department = Department(departmentId=1, departmentName="Computer Science", status="Active")
            classroom = ClassRoom(classId=1, className="BSCS Test", departmentId=1, yearSemester="Test", section="T", status="Active")
            role = Role(roleId=1, roleName="Admin")
            admin = User(userId=1, fullName="Phase 10.9B Admin", email="phase10.9b@fdas.local", passwordHash="unused", roleId=1, accessScope="AllDepartments", status="Approved")
            db_student = Student(studentId=22, rollNo="cs-2026-789", fullName="Ahmad Mughal", departmentId=1, classId=1, yearSemester="Test", section="T", status="Active")
            now = datetime.now()
            session = AttendanceSession(sessionId=1, departmentId=1, startedByUserId=1, scheduledStartTime=now, scheduledEndTime=now + timedelta(hours=1), actualStartTime=now, status="Active", createdDate=date.today())
            db.add_all([department, classroom, role, admin, db_student, session])
            db.flush()
            add_deep_gallery(db, db_student, admin)
            db.commit()

            controlled_match = {
                **accepted_match(),
                "thresholdUsed": DEEP_CONTROLLED_MATCH_THRESHOLD,
                "requiredMargin": DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
            }
            passed_liveness = live_result(passed=True, status_value="LivenessPassed", frame=frame)
            with patch("app.routers.attendance_marking.DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED", True), patch(
                "app.routers.attendance_marking.DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE", False
            ), patch(
                "app.routers.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", True
            ), patch(
                "app.routers.attendance_marking.verify_liveness", return_value=passed_liveness
            ), patch(
                "app.routers.attendance_marking.match_deep_face_query_burst_for_attendance",
                return_value=controlled_match,
            ) as controlled_matcher, patch("app.routers.attendance_marking.match_face_bytes") as legacy_matcher:
                uploads = [MemoryUpload(frame, index) for index in range(LIVENESS_FRAME_COUNT)]
                queries = [MemoryUpload(frame, index + 20) for index in range(3)]
                created = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, queries, True, 22, admin, db))
                call_keywords = controlled_matcher.call_args.kwargs
                uploads = [MemoryUpload(frame, index + 40) for index in range(LIVENESS_FRAME_COUNT)]
                queries = [MemoryUpload(frame, index + 60) for index in range(3)]
                duplicate = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, queries, True, 22, admin, db))
            row_count_after_duplicate = db.query(AttendanceRecord).count()

            failed_liveness = live_result(passed=False, status_value="LivenessFailed", frame=frame)
            with patch("app.routers.attendance_marking.DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED", True), patch(
                "app.routers.attendance_marking.DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE", False
            ), patch(
                "app.routers.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", True
            ), patch(
                "app.routers.attendance_marking.verify_liveness", return_value=failed_liveness
            ), patch("app.routers.attendance_marking.match_deep_face_query_burst_for_attendance") as skipped_matcher:
                uploads = [MemoryUpload(frame, index + 80) for index in range(LIVENESS_FRAME_COUNT)]
                queries = [MemoryUpload(frame, index + 100) for index in range(3)]
                liveness_failure = asyncio.run(mark_by_face_live(1, "MOVE_CLOSER", uploads, queries, True, 22, admin, db))
            final_row_count = db.query(AttendanceRecord).count()
        engine.dispose()

    checks = {
        "production_policy_remains_0_85_0_07": DEEP_MATCH_THRESHOLD == 0.85 and DEEP_MATCH_MIN_IDENTITY_MARGIN == 0.07,
        "controlled_policy_is_0_80_0_10": DEEP_CONTROLLED_MATCH_THRESHOLD == 0.80 and DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN == 0.10,
        "controlled_override_accepts_two_of_three": controlled_accept["matched"] is True and controlled_accept["consensusCount"] == 2 and controlled_accept["thresholdUsed"] == 0.80 and controlled_accept["requiredMargin"] == 0.10,
        "same_evidence_rejected_by_production_threshold": production_reject["matched"] is False and production_reject["status"] == "MatchBelowThreshold" and production_reject["thresholdUsed"] == 0.85,
        "one_of_three_never_accepted": consensus_reject["matched"] is False and consensus_reject["status"] == "QueryConsensusFailed",
        "score_below_0_80_rejected": score_reject["matched"] is False and score_reject["status"] == "MatchBelowThreshold",
        "margin_below_0_10_rejected": margin_reject["matched"] is False and margin_reject["status"] == "AmbiguousMatch",
        "router_applies_override_only_to_controlled_path": call_keywords.get("threshold") == 0.80 and call_keywords.get("required_margin") == 0.10,
        "failed_liveness_creates_no_attendance": liveness_failure["livenessStatus"] == LIVENESS_STATUS_FAILED and skipped_matcher.call_count == 0 and final_row_count == row_count_after_duplicate,
        "duplicate_prevention_intact": created["attendanceMarked"] is True and duplicate["status"] == "DuplicateAttendance" and row_count_after_duplicate == 1,
        "legacy_fallback_never_used": legacy_matcher.call_count == 0,
        "consensus_minimum_unchanged": DEEP_QUERY_CONSENSUS_MIN_COUNT == 2,
        "closer_liveness_safety_unchanged": LIVENESS_ALLOWED_CHALLENGES == ["MOVE_CLOSER"] and LIVENESS_MIN_AREA_CHANGE_RATIO == 0.12,
        "final_deep_activation_released_safety_hold": (
            DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE is True
            and IDENTITY_MATCHING_SAFETY_HOLD is False
        ),
    }
    checks["phase10_9b_passed"] = all(checks.values())
    for name, passed in checks.items():
        print(f"{name}={bool(passed)}")
    if not checks["phase10_9b_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
