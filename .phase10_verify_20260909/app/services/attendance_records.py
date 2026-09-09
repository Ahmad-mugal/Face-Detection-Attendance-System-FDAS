import csv
import io
from datetime import date, datetime, time

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.attendance_record import AttendanceRecord
from app.models.student import Student
from app.models.user import User
from app.services.departments import ensure_department_access


def _end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max)


def _start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min)


def scoped_attendance_record_query(db: Session, user: User):
    query = db.query(AttendanceRecord)
    role_name = user.role.roleName if user.role else ""
    if role_name == "Admin" or user.accessScope == "AllDepartments":
        return query
    if user.assignedDepartmentId is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")
    return query.filter(AttendanceRecord.departmentId == user.assignedDepartmentId)


def filtered_attendance_record_query(
    db: Session,
    user: User,
    departmentId: int | None = None,
    classId: int | None = None,
    studentId: int | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    statusValue: str | None = None,
):
    query = scoped_attendance_record_query(db, user)

    if departmentId is not None:
        ensure_department_access(user, departmentId)
        query = query.filter(AttendanceRecord.departmentId == departmentId)
    if classId is not None:
        query = query.filter(AttendanceRecord.classId == classId)
    if studentId is not None:
        query = query.filter(AttendanceRecord.studentId == studentId)
    if dateFrom is not None:
        query = query.filter(AttendanceRecord.markedAt >= _start_of_day(dateFrom))
    if dateTo is not None:
        query = query.filter(AttendanceRecord.markedAt <= _end_of_day(dateTo))
    if statusValue:
        query = query.filter(AttendanceRecord.status == statusValue)

    return query


def list_attendance_records(
    db: Session,
    user: User,
    departmentId: int | None = None,
    classId: int | None = None,
    studentId: int | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    statusValue: str | None = None,
) -> list[AttendanceRecord]:
    return (
        filtered_attendance_record_query(
            db,
            user,
            departmentId=departmentId,
            classId=classId,
            studentId=studentId,
            dateFrom=dateFrom,
            dateTo=dateTo,
            statusValue=statusValue,
        )
        .order_by(AttendanceRecord.markedAt.desc(), AttendanceRecord.attendanceId.desc())
        .all()
    )


def summarize_attendance_records(
    db: Session,
    user: User,
    departmentId: int | None = None,
    classId: int | None = None,
    studentId: int | None = None,
    dateFrom: date | None = None,
    dateTo: date | None = None,
    statusValue: str | None = None,
) -> dict:
    records = list_attendance_records(
        db,
        user,
        departmentId=departmentId,
        classId=classId,
        studentId=studentId,
        dateFrom=dateFrom,
        dateTo=dateTo,
        statusValue=statusValue,
    )
    confidences = [record.recognitionConfidence for record in records if record.recognitionConfidence is not None]
    average_confidence = round(sum(confidences) / len(confidences), 6) if confidences else None
    return {
        "totalRecords": len(records),
        "presentCount": sum(1 for record in records if record.status == "Present"),
        "uniqueStudentsMarked": len({record.studentId for record in records}),
        "averageRecognitionConfidence": average_confidence,
    }


def attendance_record_to_dict(record: AttendanceRecord) -> dict:
    return {
        "attendanceRecordId": record.attendanceId,
        "sessionId": record.sessionId,
        "studentId": record.studentId,
        "studentName": record.student.fullName if record.student else "",
        "rollNo": record.student.rollNo if record.student else "",
        "departmentId": record.departmentId,
        "departmentName": record.department.departmentName if record.department else None,
        "classId": record.classId,
        "className": record.classroom.className if record.classroom else None,
        "markedAt": record.markedAt,
        "status": record.status,
        "recognitionConfidence": record.recognitionConfidence,
        "livenessStatus": record.livenessStatus,
    }


def records_to_csv(records: list[AttendanceRecord]) -> str:
    output = io.StringIO()
    fieldnames = [
        "attendanceRecordId",
        "sessionId",
        "studentId",
        "studentName",
        "rollNo",
        "departmentName",
        "className",
        "markedAt",
        "status",
        "recognitionConfidence",
        "livenessStatus",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for record in records:
        row = attendance_record_to_dict(record)
        writer.writerow({
            "attendanceRecordId": row["attendanceRecordId"],
            "sessionId": row["sessionId"],
            "studentId": row["studentId"],
            "studentName": row["studentName"],
            "rollNo": row["rollNo"],
            "departmentName": row["departmentName"],
            "className": row["className"],
            "markedAt": row["markedAt"].isoformat() if row["markedAt"] else "",
            "status": row["status"],
            "recognitionConfidence": row["recognitionConfidence"],
            "livenessStatus": row["livenessStatus"],
        })
    return output.getvalue()


def student_belongs_to_accessible_department(db: Session, user: User, studentId: int) -> bool:
    student = db.query(Student).filter(Student.studentId == studentId).one_or_none()
    if student is None:
        return False
    ensure_department_access(user, student.departmentId)
    return True
