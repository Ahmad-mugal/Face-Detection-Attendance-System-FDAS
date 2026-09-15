from types import SimpleNamespace
from unittest.mock import patch

from app.config import (
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    FACE_MATCH_AGGREGATION,
    FACE_MATCH_THRESHOLD,
    IDENTITY_MATCHING_SAFETY_HOLD,
    MIN_IDENTITY_MARGIN,
)
from app.database import SessionLocal
from app.models.attendance_record import AttendanceRecord
from app.models.face_template import FaceTemplate
from app.services.attendance_marking import apply_identity_safety_hold, create_attendance_from_match_result
from app.services.face_matching import (
    MATCH_AGGREGATION_METHODS,
    MatchCandidate,
    build_diagnostic_response,
    build_match_response,
    calculate_student_aggregate_scores,
    load_candidate_templates,
    matching_info,
)
from app.services.face_processing import ENCODING_VERSION


def candidate(student_id: int, template_id: int, descriptor: list[float]) -> MatchCandidate:
    student = SimpleNamespace(
        studentId=student_id,
        fullName=f"Controlled Student {student_id}",
        rollNo=f"CONTROL-{student_id}",
        classId=1,
        departmentId=1,
        classroom=None,
        department=None,
    )
    template = SimpleNamespace(templateId=template_id, studentId=student_id, student=student)
    return MatchCandidate(template=template, descriptor=descriptor)


def candidate_set(student_id: int, first_template_id: int, descriptor: list[float]) -> list[MatchCandidate]:
    return [candidate(student_id, first_template_id + index, descriptor) for index in range(5)]


def main() -> None:
    aggregate_scores = calculate_student_aggregate_scores([0.9, 0.8, 0.7, 0.6, 0.5, 0.4])

    clear_candidates = candidate_set(22, 2200, [1.0, 0.0]) + candidate_set(27, 2700, [0.0, 1.0])
    clear_result = build_match_response(None, 1, [1.0, 0.0], clear_candidates)

    ambiguous_candidates = candidate_set(22, 3200, [1.0, 0.0]) + candidate_set(
        27,
        3700,
        [0.999, 0.0447],
    )
    ambiguous_result = build_match_response(None, 1, [1.0, 0.0], ambiguous_candidates)

    below_candidates = candidate_set(22, 4200, [1.0, 0.0]) + candidate_set(27, 4700, [0.0, 1.0])
    below_result = build_match_response(None, 1, [0.707106, 0.707106], below_candidates)
    diagnostic = build_diagnostic_response(1, 22, [1.0, 0.0], ambiguous_candidates)

    with patch("app.services.attendance_marking.IDENTITY_MATCHING_SAFETY_HOLD", True):
        held_match = apply_identity_safety_hold(clear_result)
    dummy_session = SimpleNamespace(sessionId=987654, departmentId=1, department=None)
    with SessionLocal() as db:
        attendance_before = db.query(AttendanceRecord).count()
        held_attendance = create_attendance_from_match_result(db, dummy_session, held_match, liveness_status="Passed")
        attendance_after = db.query(AttendanceRecord).count()
        incident = db.query(AttendanceRecord).filter(AttendanceRecord.attendanceId == 39).one_or_none()
        department_candidates = load_candidate_templates(db, 1)
        incompatible_loaded = any(
            item.template.encodingVersion != ENCODING_VERSION
            for item in department_candidates
        )
        student_22_templates = (
            db.query(FaceTemplate)
            .filter(
                FaceTemplate.studentId == 22,
                FaceTemplate.isActive.is_(True),
                FaceTemplate.status == "Encoded",
                FaceTemplate.encodingData.isnot(None),
                FaceTemplate.encodingVersion == ENCODING_VERSION,
            )
            .count()
        )
        student_27_templates = (
            db.query(FaceTemplate)
            .filter(
                FaceTemplate.studentId == 27,
                FaceTemplate.isActive.is_(True),
                FaceTemplate.status == "Encoded",
                FaceTemplate.encodingData.isnot(None),
                FaceTemplate.encodingVersion == ENCODING_VERSION,
            )
            .count()
        )

    info = matching_info()
    aggregation_methods = {item.get("method") for item in diagnostic.get("aggregations", [])}
    results = {
        "face_threshold_unchanged": FACE_MATCH_THRESHOLD == 0.75,
        "selected_aggregation_is_maximum": FACE_MATCH_AGGREGATION == "maximum",
        "identity_margin_is_conservative": MIN_IDENTITY_MARGIN == 0.05,
        "all_required_aggregates_calculated": (
            aggregate_scores
            == {
                "maximum": 0.9,
                "mean_top_3": 0.8,
                "mean_top_5": 0.7,
                "median_top_5": 0.7,
            }
        ),
        "diagnostic_exposes_all_aggregations": aggregation_methods == set(MATCH_AGGREGATION_METHODS),
        "diagnostic_never_creates_attendance": diagnostic.get("attendanceCreated") is False,
        "clear_identity_can_match_before_hold": (
            clear_result.get("matched") is True
            and clear_result.get("studentId") == 22
            and clear_result.get("scoreMargin", 0) >= MIN_IDENTITY_MARGIN
        ),
        "ambiguous_identity_rejected": (
            ambiguous_result.get("matched") is False
            and ambiguous_result.get("status") == "AmbiguousMatch"
            and ambiguous_result.get("studentId") is None
            and ambiguous_result.get("scoreMargin", 1) < MIN_IDENTITY_MARGIN
        ),
        "below_threshold_precedes_margin": (
            below_result.get("matched") is False
            and below_result.get("status") == "MatchBelowThreshold"
        ),
        "final_deep_activation_released_global_hold": (
            IDENTITY_MATCHING_SAFETY_HOLD is False
            and DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE is True
        ),
        "hold_removes_candidate_identity": (
            held_match.get("matched") is False
            and held_match.get("status") == "AttendanceSafetyHold"
            and held_match.get("studentId") is None
        ),
        "held_match_creates_no_attendance": (
            attendance_before == attendance_after
            and held_attendance.get("attendanceMarked") is False
            and held_attendance.get("status") == "AttendanceSafetyHold"
        ),
        "wrong_attendance_evidence_preserved": (
            incident is not None
            and incident.sessionId == 447
            and incident.studentId == 27
            and incident.recognitionConfidence == 0.833374
            and incident.livenessStatus == "Passed"
        ),
        "only_compatible_templates_loaded": incompatible_loaded is False,
        "student_22_encoded_templates_preserved": student_22_templates == 19,
        "student_27_encoded_templates_preserved": student_27_templates == 19,
        "matching_info_reports_safety_policy": (
            info.get("threshold") == 0.75
            and info.get("aggregationMethod") == "maximum"
            and info.get("requiredIdentityMargin") == 0.05
            and info.get("attendanceSafetyHold") is False
        ),
    }
    results["phase10_6b_automated_passed"] = all(results.values())
    for name, passed in results.items():
        print(f"{name}={passed}")
    if not results["phase10_6b_automated_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
