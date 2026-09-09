from datetime import date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.attendance_session import AttendanceSession
from app.models.attendance_time_window import AttendanceTimeWindow
from app.models.department import Department
from app.models.user import User
from app.services.departments import ensure_department_access, get_department_or_404


ACTIVE_SESSION_STATUS = "Active"
TERMINAL_SESSION_STATUSES = {"Closed", "Cancelled"}


def get_session_or_404(db: Session, sessionId: int) -> AttendanceSession:
    session = db.query(AttendanceSession).filter(AttendanceSession.sessionId == sessionId).one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found")
    return session


def ensure_session_access(user: User, session: AttendanceSession) -> None:
    ensure_department_access(user, session.departmentId)


def scoped_session_query(db: Session, user: User):
    query = db.query(AttendanceSession)
    role_name = user.role.roleName if user.role else ""
    if role_name == "Admin" or user.accessScope == "AllDepartments":
        return query
    return query.filter(AttendanceSession.departmentId == user.assignedDepartmentId)


def get_active_session_for_department(db: Session, departmentId: int) -> AttendanceSession | None:
    return (
        db.query(AttendanceSession)
        .filter(
            AttendanceSession.departmentId == departmentId,
            AttendanceSession.status == ACTIVE_SESSION_STATUS,
        )
        .order_by(AttendanceSession.sessionId.desc())
        .first()
    )


def get_active_time_window_for_department(db: Session, departmentId: int) -> AttendanceTimeWindow | None:
    return (
        db.query(AttendanceTimeWindow)
        .filter(
            AttendanceTimeWindow.departmentId == departmentId,
            AttendanceTimeWindow.status == "Active",
        )
        .order_by(AttendanceTimeWindow.windowId.desc())
        .first()
    )


def build_scheduled_datetimes(now: datetime, window: AttendanceTimeWindow | None) -> tuple[datetime, datetime]:
    if window is None:
        return now, now + timedelta(hours=1)

    scheduled_date = now.date()
    scheduled_start = datetime.combine(scheduled_date, window.startTime)
    scheduled_end = datetime.combine(scheduled_date, window.endTime)
    if scheduled_end <= scheduled_start:
        scheduled_end += timedelta(days=1)
    return scheduled_start, scheduled_end


def start_attendance_session(db: Session, user: User, departmentId: int) -> AttendanceSession:
    get_department_or_404(db, departmentId)
    ensure_department_access(user, departmentId)

    if get_active_session_for_department(db, departmentId) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department already has an active attendance session",
        )

    now = datetime.utcnow()
    active_window = get_active_time_window_for_department(db, departmentId)
    scheduled_start, scheduled_end = build_scheduled_datetimes(now, active_window)

    session = AttendanceSession(
        departmentId=departmentId,
        startedByUserId=user.userId,
        scheduledStartTime=scheduled_start,
        scheduledEndTime=scheduled_end,
        actualStartTime=now,
        actualEndTime=None,
        status=ACTIVE_SESSION_STATUS,
        createdDate=date.today(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def close_attendance_session(db: Session, user: User, sessionId: int, final_status: str) -> AttendanceSession:
    if final_status not in TERMINAL_SESSION_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid final session status")

    session = get_session_or_404(db, sessionId)
    ensure_session_access(user, session)

    if session.status != ACTIVE_SESSION_STATUS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only active sessions can be changed")

    session.status = final_status
    session.actualEndTime = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


def list_accessible_sessions(
    db: Session,
    user: User,
    departmentId: int | None = None,
    session_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    query = scoped_session_query(db, user)

    if departmentId is not None:
        ensure_department_access(user, departmentId)
        query = query.filter(AttendanceSession.departmentId == departmentId)
    if session_status is not None:
        query = query.filter(AttendanceSession.status == session_status)
    if date_from is not None:
        query = query.filter(AttendanceSession.createdDate >= date_from)
    if date_to is not None:
        query = query.filter(AttendanceSession.createdDate <= date_to)

    return query


def validate_session_department(db: Session, departmentId: int) -> Department:
    return get_department_or_404(db, departmentId)
