from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.attendance_record import AttendanceRecord
from app.models.user import User
from app.schemas.attendance_marking import AttendanceMarkResult, AttendanceSessionRecordRead
from app.services.attendance_marking import list_session_records, mark_attendance_by_face
from app.services.face_matching import read_match_upload


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


@router.get("/api/attendance-sessions/{sessionId}/records", response_model=list[AttendanceSessionRecordRead])
def get_session_records(
    sessionId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    records = list_session_records(db, current_user, sessionId)
    return [to_record_read(record) for record in records]
