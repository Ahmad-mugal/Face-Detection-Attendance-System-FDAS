from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.student import Student
from app.models.user import User
from app.services.attendance_records import scoped_attendance_record_query
from app.services.attendance_sessions import scoped_session_query
from app.services.students import scoped_student_query

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    role_name = current_user.role.roleName if current_user.role else ""
    is_admin = role_name == "Admin"

    # Scoped queries
    students_query = scoped_student_query(db, current_user)
    sessions_query = scoped_session_query(db, current_user)
    records_query = scoped_attendance_record_query(db, current_user)

    # 1. Active students count in scope
    total_students = students_query.filter(Student.status == "Active").count()

    # 2. Today's attendance
    today = date.today()
    today_start = datetime.combine(today, time.min)
    today_end = datetime.combine(today, time.max)

    distinct_students_today = (
        records_query.filter(
            AttendanceRecord.markedAt >= today_start,
            AttendanceRecord.markedAt <= today_end,
        )
        .with_entities(AttendanceRecord.studentId)
        .distinct()
        .count()
    )

    not_marked_today = max(0, total_students - distinct_students_today)
    attendance_rate = round((distinct_students_today / total_students) * 100, 1) if total_students > 0 else 0.0

    # 3. Active sessions
    active_sessions = sessions_query.filter(AttendanceSession.status == "Active").all()
    active_session_name = active_sessions[0].department.departmentName if (active_sessions and active_sessions[0].department) else "None"

    # 4. Weekly trend chart (last 7 days)
    days_list = [today - timedelta(days=i) for i in reversed(range(7))]
    weekly_chart = []
    for day_item in days_list:
        d_start = datetime.combine(day_item, time.min)
        d_end = datetime.combine(day_item, time.max)
        day_count = (
            records_query.filter(
                AttendanceRecord.markedAt >= d_start,
                AttendanceRecord.markedAt <= d_end,
            )
            .with_entities(AttendanceRecord.studentId)
            .distinct()
            .count()
        )
        pct = round((day_count / total_students) * 100) if total_students > 0 else 0
        weekly_chart.append({
            "day": day_item.strftime("%a"),
            "date": day_item.isoformat(),
            "present": pct,
            "absent": max(0, 100 - pct),
            "presentCount": day_count,
            "totalStudents": total_students,
        })

    # 5. Recent attendance records
    recent_records_raw = records_query.order_by(
        AttendanceRecord.markedAt.desc(),
        AttendanceRecord.attendanceId.desc(),
    ).limit(15).all()

    recent_records = []
    for rec in recent_records_raw:
        recent_records.append({
            "id": rec.attendanceId,
            "studentName": rec.student.fullName if rec.student else "Unknown",
            "rollNumber": rec.student.rollNo if rec.student else "",
            "markedAt": rec.markedAt.strftime("%I:%M %p") if rec.markedAt else "",
            "confidence": rec.recognitionConfidence,
            "departmentName": rec.department.departmentName if rec.department else "",
        })

    # Base response
    response_data = {
        "totalStudents": total_students,
        "presentToday": distinct_students_today,
        "notMarkedToday": not_marked_today,
        "attendanceRate": attendance_rate,
        "activeSessionName": active_session_name,
        "activeSessionCount": len(active_sessions),
        "weeklyChart": weekly_chart,
        "recentRecords": recent_records,
    }

    # Admin-specific statistics
    if is_admin:
        response_data["totalUsers"] = db.query(User).count()
        response_data["totalClasses"] = db.query(ClassRoom).count()

        # Department breakdown
        departments = db.query(Department).all()
        dept_summaries = []
        for dept in departments:
            dept_students = db.query(Student).filter(Student.departmentId == dept.departmentId, Student.status == "Active").count()
            dept_present = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.departmentId == dept.departmentId,
                    AttendanceRecord.markedAt >= today_start,
                    AttendanceRecord.markedAt <= today_end,
                )
                .with_entities(AttendanceRecord.studentId)
                .distinct()
                .count()
            )
            dept_rate = round((dept_present / dept_students) * 100, 1) if dept_students > 0 else 0.0
            dept_summaries.append({
                "departmentId": dept.departmentId,
                "departmentName": dept.departmentName,
                "totalStudents": dept_students,
                "presentToday": dept_present,
                "attendanceRate": dept_rate,
            })
        response_data["departmentSummaries"] = dept_summaries

    return response_data
