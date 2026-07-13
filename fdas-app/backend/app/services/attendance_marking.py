from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import FACE_MATCH_THRESHOLD
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.models.user import User
from app.services.attendance_sessions import ACTIVE_SESSION_STATUS, ensure_session_access, get_session_or_404
from app.services.face_enrollment import FACE_ENROLLMENT_SAMPLE_COUNT
from app.services.face_matching import match_face_bytes


PRESENT_STATUS = "Present"
LIVENESS_STATUS_NOT_CHECKED = "NotChecked"


def ensure_active_session(session: AttendanceSession) -> None:
    if session.status != ACTIVE_SESSION_STATUS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NoActiveSession")


def student_has_required_active_templates(db: Session, studentId: int) -> bool:
    active_count = (
        db.query(func.count(FaceTemplate.templateId))
        .filter(FaceTemplate.studentId == studentId, FaceTemplate.isActive.is_(True))
        .scalar()
    )
    return int(active_count or 0) >= FACE_ENROLLMENT_SAMPLE_COUNT


def get_existing_record(db: Session, sessionId: int, studentId: int) -> AttendanceRecord | None:
    return (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.sessionId == sessionId, AttendanceRecord.studentId == studentId)
        .one_or_none()
    )


def record_to_mark_result(
    record: AttendanceRecord,
    attendance_marked: bool,
    status_value: str,
    message: str,
    threshold_used: float | None = FACE_MATCH_THRESHOLD,
) -> dict:
    student = record.student
    return {
        "attendanceMarked": attendance_marked,
        "status": status_value,
        "message": message,
        "attendanceRecordId": record.attendanceId,
        "sessionId": record.sessionId,
        "studentId": record.studentId,
        "studentName": student.fullName if student else None,
        "rollNo": student.rollNo if student else None,
        "classId": record.classId,
        "className": record.classroom.className if record.classroom else None,
        "departmentId": record.departmentId,
        "departmentName": record.department.departmentName if record.department else None,
        "markedAt": record.markedAt,
        "recognitionConfidence": record.recognitionConfidence,
        "thresholdUsed": threshold_used,
        "livenessStatus": record.livenessStatus,
    }


def no_attendance_result(session: AttendanceSession, match_result: dict, liveness_status: str | None = None) -> dict:
    return {
        "attendanceMarked": False,
        "status": str(match_result.get("status") or "NoAttendanceCreated"),
        "message": str(match_result.get("message") or "Attendance was not marked."),
        "attendanceRecordId": None,
        "sessionId": session.sessionId,
        "studentId": match_result.get("studentId"),
        "studentName": match_result.get("studentName"),
        "rollNo": match_result.get("rollNo"),
        "classId": match_result.get("classId"),
        "className": match_result.get("className"),
        "departmentId": session.departmentId,
        "departmentName": session.department.departmentName if session.department else match_result.get("departmentName"),
        "markedAt": None,
        "recognitionConfidence": match_result.get("similarityScore"),
        "thresholdUsed": match_result.get("thresholdUsed", FACE_MATCH_THRESHOLD),
        "livenessStatus": liveness_status or LIVENESS_STATUS_NOT_CHECKED,
    }


def create_attendance_from_match_result(
    db: Session,
    session: AttendanceSession,
    match_result: dict,
    liveness_status: str | None = None,
) -> dict:
    if match_result.get("matched") is not True:
        return no_attendance_result(session, match_result, liveness_status=liveness_status)

    student_id = match_result.get("studentId")
    if not isinstance(student_id, int):
        return no_attendance_result(
            session,
            {
                **match_result,
                "status": "StudentNotEligible",
                "message": "Matched result did not include a valid student.",
            },
            liveness_status=liveness_status,
        )

    student = db.query(Student).filter(Student.studentId == student_id).one_or_none()
    if (
        student is None
        or student.status != "Active"
        or student.departmentId != session.departmentId
        or not student_has_required_active_templates(db, student.studentId)
    ):
        return no_attendance_result(
            session,
            {
                **match_result,
                "status": "StudentNotEligible",
                "message": "Matched student is not eligible for this attendance session.",
            },
            liveness_status=liveness_status,
        )

    existing = get_existing_record(db, session.sessionId, student.studentId)
    if existing is not None:
        return record_to_mark_result(
            existing,
            attendance_marked=False,
            status_value="DuplicateAttendance",
            message="Attendance is already marked for this student in this session.",
            threshold_used=match_result.get("thresholdUsed", FACE_MATCH_THRESHOLD),
        )

    record = AttendanceRecord(
        sessionId=session.sessionId,
        studentId=student.studentId,
        departmentId=session.departmentId,
        classId=student.classId,
        markedAt=datetime.utcnow(),
        status=PRESENT_STATUS,
        recognitionConfidence=match_result.get("similarityScore"),
        livenessStatus=liveness_status or LIVENESS_STATUS_NOT_CHECKED,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record_to_mark_result(
        record,
        attendance_marked=True,
        status_value="AttendanceMarked",
        message="Attendance marked from a valid face match.",
        threshold_used=match_result.get("thresholdUsed", FACE_MATCH_THRESHOLD),
    )


def mark_attendance_by_face(db: Session, currentUser: User, sessionId: int, image_bytes: bytes) -> dict:
    session = get_session_or_404(db, sessionId)
    ensure_session_access(currentUser, session)
    ensure_active_session(session)
    match_result = match_face_bytes(db, currentUser, session.departmentId, image_bytes)
    return create_attendance_from_match_result(db, session, match_result)


def list_session_records(db: Session, currentUser: User, sessionId: int) -> list[AttendanceRecord]:
    session = get_session_or_404(db, sessionId)
    ensure_session_access(currentUser, session)
    return (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.sessionId == session.sessionId)
        .order_by(AttendanceRecord.markedAt.asc(), AttendanceRecord.attendanceId.asc())
        .all()
    )
