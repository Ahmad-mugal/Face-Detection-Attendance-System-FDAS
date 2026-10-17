from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import (
    ATTENDANCE_MODE,
    ATTENDANCE_MODE_FAST_MULTI_FACE,
    ATTENDANCE_MODE_SECURE_SINGLE_FACE,
    DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID,
    DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED,
    DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_CONTROLLED_MATCH_THRESHOLD,
    DEEP_MATCH_MIN_IDENTITY_MARGIN,
    DEEP_MATCH_THRESHOLD,
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    DEEP_QUERY_BURST_COUNT,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.dependencies import require_operator_or_admin
from app.models.attendance_record import AttendanceRecord
from app.models.user import User
from app.schemas.attendance_marking import (
    AttendanceMarkResult,
    AttendanceSessionRecordRead,
    FastAttendanceResult,
)
from app.services.attendance_marking import (
    apply_identity_safety_hold,
    create_attendance_from_match_result,
    ensure_active_session,
    list_session_records,
    mark_attendance_by_face,
    mark_fast_multi_face_attendance,
    no_attendance_result,
)
from app.services.attendance_sessions import ensure_session_access, get_session_or_404
from app.services.face_matching import match_face_bytes
from app.services.face_matching import read_match_upload
from app.services.deep_face_matching import (
    controlled_attendance_student_capability,
    match_deep_face_query_burst_for_attendance,
)
from app.services.liveness import LIVENESS_STATUS_FAILED, LIVENESS_STATUS_PASSED, read_liveness_uploads, verify_liveness


router = APIRouter(tags=["attendance-marking"])


def ensure_attendance_mode(expected_mode: str) -> None:
    if ATTENDANCE_MODE != expected_mode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "AttendanceModeMismatch",
                "activeMode": ATTENDANCE_MODE,
                "requiredMode": expected_mode,
            },
        )


def ensure_deep_attendance_released() -> None:
    if not DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE or IDENTITY_MATCHING_SAFETY_HOLD:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AttendanceSafetyHold",
        )


def to_record_read(record: AttendanceRecord) -> AttendanceSessionRecordRead:
    return AttendanceSessionRecordRead(
        attendanceRecordId=record.attendanceId,
        sessionId=record.sessionId,
        studentId=record.studentId,
        studentName=record.student.fullName if record.student else "",
        rollNo=record.student.rollNo if record.student else "",
        classId=record.classId,
        className=record.classroom.className if record.classroom else None,
        departmentId=record.departmentId,
        departmentName=record.department.departmentName if record.department else None,
        markedAt=record.markedAt,
        status=record.status,
        recognitionConfidence=record.recognitionConfidence,
        recognitionProvider=record.recognitionProvider,
        recognitionEncodingVersion=record.recognitionEncodingVersion,
        recognitionMethod=record.recognitionMethod,
        identityMargin=record.identityMargin,
        livenessStatus=record.livenessStatus,
    )


@router.post("/api/attendance/mark-by-face", response_model=AttendanceMarkResult)
async def mark_by_face(
    sessionId: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    image_bytes = await read_match_upload(file)
    return mark_attendance_by_face(db, current_user, sessionId, image_bytes)


@router.post("/api/attendance/mark-by-face-live", response_model=AttendanceMarkResult)
async def mark_by_face_live(
    sessionId: int = Form(...),
    challengeType: str = Form(...),
    files: list[UploadFile] = File(...),
    queryFiles: list[UploadFile] | None = File(None),
    controlledTest: bool = Form(False),
    expectedStudentId: int | None = Form(None),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    ensure_attendance_mode(ATTENDANCE_MODE_SECURE_SINGLE_FACE)
    frame_bytes = await read_liveness_uploads(files)
    session = get_session_or_404(db, sessionId)
    ensure_session_access(current_user, session)
    ensure_active_session(session)

    role_name = current_user.role.roleName if current_user.role else ""
    controlled_student = controlled_attendance_student_capability(db)
    controlled_allowed = (
        controlledTest
        and DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED
        and IDENTITY_MATCHING_SAFETY_HOLD
        and not DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE
        and role_name == "Admin"
        and expectedStudentId == DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID
        and controlled_student["controlledAttendanceStudentReady"]
        and controlled_student["controlledAttendanceDepartmentId"] == session.departmentId
    )
    if controlledTest and not controlled_allowed:
        return no_attendance_result(
            session,
            {
                "status": "ControlledAttendanceUnavailable",
                "message": "The controlled deep-attendance test prerequisites are unavailable or not authorized.",
            },
        )

    liveness_result = verify_liveness(frame_bytes, challengeType)
    if not liveness_result.passed or not liveness_result.bestFrameBytes:
        return {
            "attendanceMarked": False,
            "status": liveness_result.status,
            "message": liveness_result.message,
            "attendanceRecordId": None,
            "sessionId": session.sessionId,
            "studentId": None,
            "studentName": None,
            "rollNo": None,
            "classId": None,
            "className": None,
            "departmentId": session.departmentId,
            "departmentName": session.department.departmentName if session.department else None,
            "markedAt": None,
            "recognitionConfidence": None,
            "thresholdUsed": None,
            "livenessStatus": LIVENESS_STATUS_FAILED,
            "livenessDiagnostics": liveness_result.diagnostics,
            "controlledTest": controlledTest,
        }

    globally_allowed = DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE and not IDENTITY_MATCHING_SAFETY_HOLD
    if not controlled_allowed and not globally_allowed:
        held_result = no_attendance_result(
            session,
            {
                "status": "AttendanceSafetyHold",
                "message": "Deep attendance is integrated but remains disabled pending explicit approval.",
            },
            liveness_status=LIVENESS_STATUS_PASSED,
        )
        held_result["livenessDiagnostics"] = liveness_result.diagnostics
        held_result["controlledTest"] = False
        return held_result

    if not queryFiles or len(queryFiles) != DEEP_QUERY_BURST_COUNT:
        missing_query_result = no_attendance_result(
            session,
            {
                "status": "InvalidQueryBurst",
                "message": f"Exactly {DEEP_QUERY_BURST_COUNT} fresh centered recognition images are required after liveness.",
                "queryCount": len(queryFiles or []),
            },
            liveness_status=LIVENESS_STATUS_PASSED,
        )
        missing_query_result["livenessDiagnostics"] = liveness_result.diagnostics
        missing_query_result["controlledTest"] = controlled_allowed
        return missing_query_result

    query_bytes = [await read_match_upload(query_file) for query_file in queryFiles]
    match_result = match_deep_face_query_burst_for_attendance(
        db,
        current_user,
        session.departmentId,
        query_bytes,
        threshold=(DEEP_CONTROLLED_MATCH_THRESHOLD if controlled_allowed else DEEP_MATCH_THRESHOLD),
        required_margin=(
            DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN
            if controlled_allowed
            else DEEP_MATCH_MIN_IDENTITY_MARGIN
        ),
    )
    if controlled_allowed and match_result.get("matched") is True and match_result.get("studentId") != expectedStudentId:
        match_result = {
            **match_result,
            "matched": False,
            "status": "ControlledIdentityMismatch",
            "message": "The controlled query did not match the authorized test student.",
            "studentId": None,
            "studentName": None,
            "rollNo": None,
            "classId": None,
            "className": None,
        }
    if not controlled_allowed:
        match_result = apply_identity_safety_hold(match_result)
    attendance_result = create_attendance_from_match_result(
        db,
        session,
        match_result,
        liveness_status=LIVENESS_STATUS_PASSED,
    )
    attendance_result["livenessDiagnostics"] = liveness_result.diagnostics
    attendance_result["controlledTest"] = controlled_allowed
    return attendance_result


@router.post("/api/attendance/mark-by-face-fast", response_model=FastAttendanceResult)
async def mark_by_face_fast(
    sessionId: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    ensure_attendance_mode(ATTENDANCE_MODE_FAST_MULTI_FACE)
    ensure_deep_attendance_released()
    image_bytes = await read_match_upload(file)
    return mark_fast_multi_face_attendance(
        db,
        current_user,
        sessionId,
        image_bytes,
    )


@router.get("/api/attendance-sessions/{sessionId}/records", response_model=list[AttendanceSessionRecordRead])
def get_session_records(
    sessionId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    records = list_session_records(db, current_user, sessionId)
    return [to_record_read(record) for record in records]
