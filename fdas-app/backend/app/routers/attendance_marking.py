from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.attendance_record import AttendanceRecord
from app.models.user import User
from app.schemas.attendance_marking import AttendanceMarkResult, AttendanceSessionRecordRead
from app.services.attendance_marking import (
    apply_identity_safety_hold,
    create_attendance_from_match_result,
    ensure_active_session,
    list_session_records,
    mark_attendance_by_face,
)
from app.services.attendance_sessions import ensure_session_access, get_session_or_404
from app.services.face_matching import match_face_bytes
from app.services.face_matching import read_match_upload
from app.services.liveness import LIVENESS_STATUS_FAILED, LIVENESS_STATUS_PASSED, read_liveness_uploads, verify_liveness


router = APIRouter(tags=["attendance-marking"])


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
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    frame_bytes = await read_liveness_uploads(files)
    session = get_session_or_404(db, sessionId)
    ensure_session_access(current_user, session)
    ensure_active_session(session)

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
        }

    match_result = match_face_bytes(db, current_user, session.departmentId, liveness_result.bestFrameBytes)
    match_result = apply_identity_safety_hold(match_result)
    attendance_result = create_attendance_from_match_result(
        db,
        session,
        match_result,
        liveness_status=LIVENESS_STATUS_PASSED,
    )
    attendance_result["livenessDiagnostics"] = liveness_result.diagnostics
    return attendance_result


@router.get("/api/attendance-sessions/{sessionId}/records", response_model=list[AttendanceSessionRecordRead])
def get_session_records(
    sessionId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    records = list_session_records(db, current_user, sessionId)
    return [to_record_read(record) for record in records]
