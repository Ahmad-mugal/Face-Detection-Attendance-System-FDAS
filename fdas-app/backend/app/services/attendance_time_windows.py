from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.attendance_time_window import AttendanceTimeWindow
from app.models.user import User
from app.services.departments import ensure_department_access, get_department_or_404


VALID_TIME_WINDOW_STATUSES = {"Active", "Inactive"}


def get_time_window_or_404(db: Session, windowId: int) -> AttendanceTimeWindow:
    window = db.query(AttendanceTimeWindow).filter(AttendanceTimeWindow.windowId == windowId).one_or_none()
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance time window not found")
    return window


def ensure_time_window_access(user: User, window: AttendanceTimeWindow) -> None:
    ensure_department_access(user, window.departmentId)


def scoped_time_window_query(db: Session, user: User):
    query = db.query(AttendanceTimeWindow)
    role_name = user.role.roleName if user.role else ""
    if role_name == "Admin" or user.accessScope == "AllDepartments":
        return query
    return query.filter(AttendanceTimeWindow.departmentId == user.assignedDepartmentId)


def validate_time_window_status(status_value: str) -> None:
    if status_value not in VALID_TIME_WINDOW_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid time window status")


def validate_time_window_department(db: Session, departmentId: int) -> None:
    get_department_or_404(db, departmentId)
