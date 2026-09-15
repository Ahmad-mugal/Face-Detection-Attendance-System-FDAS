from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import (
    DEEP_ENROLLMENT_MIN_EMBEDDINGS,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_MATCH_THRESHOLD,
    FACE_MATCH_THRESHOLD,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.models.user import User
from app.services.attendance_sessions import ACTIVE_SESSION_STATUS, ensure_session_access, get_session_or_404
from app.services.face_enrollment import FACE_ENROLLMENT_SAMPLE_COUNT
from app.services.deep_face import DEEP_FACE_PROVIDER
from app.services.face_processing import validate_single_face_bytes
from app.utils.time import utc_now_naive


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


def student_has_required_deep_embeddings(db: Session, studentId: int) -> bool:
    active_count = (
        db.query(func.count(FaceTemplateEmbedding.faceTemplateEmbeddingId))
        .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
        .filter(
            FaceTemplateEmbedding.studentId == studentId,
            FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
            FaceTemplateEmbedding.isActive.is_(True),
            FaceTemplate.isActive.is_(True),
        )
        .scalar()
    )
    return int(active_count or 0) >= DEEP_ENROLLMENT_MIN_EMBEDDINGS


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
    match_result: dict | None = None,
) -> dict:
    student = record.student
    current_match = match_result or {}
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
        "recognitionProvider": record.recognitionProvider,
        "recognitionEncodingVersion": record.recognitionEncodingVersion,
        "recognitionMethod": record.recognitionMethod,
        "identityMargin": record.identityMargin,
        "topStudentId": current_match.get("topStudentId", record.studentId),
        "topStudentName": current_match.get("topStudentName", student.fullName if student else None),
        "topRollNo": current_match.get("topRollNo", student.rollNo if student else None),
        "topScore": current_match.get("topScore", record.recognitionConfidence),
        "secondStudentId": current_match.get("secondStudentId"),
        "secondStudentName": current_match.get("secondStudentName"),
        "secondRollNo": current_match.get("secondRollNo"),
        "secondScore": current_match.get("secondScore"),
        "secondRecognitionConfidence": current_match.get("secondSimilarityScore"),
        "scoreMargin": current_match.get("scoreMargin", record.identityMargin),
        "requiredMargin": current_match.get("requiredMargin"),
        "aggregationMethod": current_match.get("aggregationMethod", record.recognitionMethod),
        "thresholdUsed": threshold_used,
        "livenessStatus": record.livenessStatus,
        "queryCount": current_match.get("queryCount", 0),
        "validQueryCount": current_match.get("validQueryCount", 0),
        "consensusStudentId": current_match.get("consensusStudentId"),
        "consensusCount": current_match.get("consensusCount", 0),
        "queryTopStudentIds": current_match.get("queryTopStudentIds", []),
        "queryTopScores": current_match.get("queryTopScores", []),
        "queryQuality": current_match.get("queryQuality", []),
        "retryable": current_match.get("retryable", False),
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
        "recognitionProvider": match_result.get("recognitionProvider"),
        "recognitionEncodingVersion": match_result.get("encodingVersion"),
        "recognitionMethod": match_result.get("aggregationMethod"),
        "identityMargin": match_result.get("scoreMargin"),
        "topStudentId": match_result.get("topStudentId"),
        "topStudentName": match_result.get("topStudentName"),
        "topRollNo": match_result.get("topRollNo"),
        "topScore": match_result.get("topScore"),
        "secondStudentId": match_result.get("secondStudentId"),
        "secondStudentName": match_result.get("secondStudentName"),
        "secondRollNo": match_result.get("secondRollNo"),
        "secondScore": match_result.get("secondScore"),
        "secondRecognitionConfidence": match_result.get("secondSimilarityScore"),
        "scoreMargin": match_result.get("scoreMargin"),
        "thresholdUsed": match_result.get("thresholdUsed", FACE_MATCH_THRESHOLD),
        "requiredMargin": match_result.get("requiredMargin"),
        "aggregationMethod": match_result.get("aggregationMethod"),
        "livenessStatus": liveness_status or LIVENESS_STATUS_NOT_CHECKED,
        "queryCount": match_result.get("queryCount", 0),
        "validQueryCount": match_result.get("validQueryCount", 0),
        "consensusStudentId": match_result.get("consensusStudentId"),
        "consensusCount": match_result.get("consensusCount", 0),
        "queryTopStudentIds": match_result.get("queryTopStudentIds", []),
        "queryTopScores": match_result.get("queryTopScores", []),
        "queryQuality": match_result.get("queryQuality", []),
        "retryable": match_result.get("retryable", False),
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
        or (
            not student_has_required_deep_embeddings(db, student.studentId)
            if match_result.get("recognitionProvider") == DEEP_FACE_PROVIDER
            else not student_has_required_active_templates(db, student.studentId)
        )
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
            match_result=match_result,
        )

    record = AttendanceRecord(
        sessionId=session.sessionId,
        studentId=student.studentId,
        departmentId=session.departmentId,
        classId=student.classId,
        markedAt=utc_now_naive(),
        status=PRESENT_STATUS,
        recognitionConfidence=match_result.get("similarityScore"),
        recognitionProvider=match_result.get("recognitionProvider"),
        recognitionEncodingVersion=match_result.get("encodingVersion"),
        recognitionMethod=match_result.get("aggregationMethod"),
        identityMargin=match_result.get("scoreMargin"),
        livenessStatus=liveness_status or LIVENESS_STATUS_NOT_CHECKED,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record_to_mark_result(
        record,
        attendance_marked=True,
        status_value="AttendanceMarked",
        message=(
            "Attendance marked from a valid ArcFace deep match."
            if match_result.get("recognitionProvider") == DEEP_FACE_PROVIDER
            else "Attendance marked from a valid face match."
        ),
        threshold_used=match_result.get("thresholdUsed", FACE_MATCH_THRESHOLD),
        match_result=match_result,
    )


def apply_identity_safety_hold(match_result: dict) -> dict:
    if not IDENTITY_MATCHING_SAFETY_HOLD or match_result.get("matched") is not True:
        return match_result
    return {
        **match_result,
        "matched": False,
        "status": "AttendanceSafetyHold",
        "message": "Attendance remains disabled while identity-integrity validation is incomplete.",
        "studentId": None,
        "studentName": None,
        "rollNo": None,
        "classId": None,
        "className": None,
        "departmentId": None,
        "departmentName": None,
        "bestTemplateId": None,
    }


def mark_attendance_by_face(db: Session, currentUser: User, sessionId: int, image_bytes: bytes) -> dict:
    session = get_session_or_404(db, sessionId)
    ensure_session_access(currentUser, session)
    ensure_active_session(session)
    face_guard = validate_single_face_bytes(image_bytes)
    if not face_guard.get("ready"):
        return no_attendance_result(session, face_guard)
    return no_attendance_result(
        session,
        {
            "status": "LivenessRequired",
            "message": "Automatic attendance requires the live liveness endpoint before ArcFace recognition.",
            "thresholdUsed": DEEP_MATCH_THRESHOLD,
            "recognitionProvider": DEEP_FACE_PROVIDER,
            "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        },
    )


def list_session_records(db: Session, currentUser: User, sessionId: int) -> list[AttendanceRecord]:
    session = get_session_or_404(db, sessionId)
    ensure_session_access(currentUser, session)
    return (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.sessionId == session.sessionId)
        .order_by(AttendanceRecord.markedAt.asc(), AttendanceRecord.attendanceId.asc())
        .all()
    )
