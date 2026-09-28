from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_operator_or_admin
from app.models.attendance_time_window import AttendanceTimeWindow
from app.models.user import User
from app.schemas.academic import AttendanceTimeWindowCreate, AttendanceTimeWindowRead, AttendanceTimeWindowUpdate
from app.services.attendance_time_windows import (
    deactivate_other_active_time_windows,
    ensure_time_window_access,
    get_time_window_or_404,
    scoped_time_window_query,
    validate_time_window_department,
    validate_time_window_status,
)


router = APIRouter(prefix="/api/attendance-time-windows", tags=["attendance-time-windows"])


def to_time_window_read(window: AttendanceTimeWindow) -> AttendanceTimeWindowRead:
    return AttendanceTimeWindowRead(
        windowId=window.windowId,
        departmentId=window.departmentId,
        departmentName=window.department.departmentName if window.department else None,
        startTime=window.startTime,
        endTime=window.endTime,
        graceMinutes=window.graceMinutes,
        status=window.status,
        createdAt=window.createdAt,
        updatedAt=window.updatedAt,
    )


@router.get("", response_model=list[AttendanceTimeWindowRead])
def list_time_windows(current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    windows = scoped_time_window_query(db, current_user).order_by(AttendanceTimeWindow.departmentId).all()
    return [to_time_window_read(window) for window in windows]


@router.get("/{windowId}", response_model=AttendanceTimeWindowRead)
def get_time_window(windowId: int, current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    window = get_time_window_or_404(db, windowId)
    ensure_time_window_access(current_user, window)
    return to_time_window_read(window)


@router.post("", response_model=AttendanceTimeWindowRead, status_code=201)
def create_time_window(payload: AttendanceTimeWindowCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    validate_time_window_department(db, payload.departmentId)
    validate_time_window_status(payload.status)
    window = AttendanceTimeWindow(
        departmentId=payload.departmentId,
        startTime=payload.startTime,
        endTime=payload.endTime,
        graceMinutes=payload.graceMinutes,
        status=payload.status,
    )
    if payload.status == "Active":
        deactivate_other_active_time_windows(db, payload.departmentId)
    db.add(window)
    db.commit()
    db.refresh(window)
    return to_time_window_read(window)


@router.patch("/{windowId}", response_model=AttendanceTimeWindowRead)
def update_time_window(
    windowId: int,
    payload: AttendanceTimeWindowUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    window = get_time_window_or_404(db, windowId)
    if payload.departmentId is not None:
        validate_time_window_department(db, payload.departmentId)
        window.departmentId = payload.departmentId
    if payload.startTime is not None:
        window.startTime = payload.startTime
    if payload.endTime is not None:
        window.endTime = payload.endTime
    if payload.graceMinutes is not None:
        window.graceMinutes = payload.graceMinutes
    if payload.status is not None:
        validate_time_window_status(payload.status)
        window.status = payload.status
    if window.status == "Active":
        deactivate_other_active_time_windows(db, window.departmentId, exclude_window_id=window.windowId)
    db.commit()
    db.refresh(window)
    return to_time_window_read(window)


@router.patch("/{windowId}/activate", response_model=AttendanceTimeWindowRead)
def activate_time_window(windowId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    window = get_time_window_or_404(db, windowId)
    deactivate_other_active_time_windows(db, window.departmentId, exclude_window_id=window.windowId)
    window.status = "Active"
    db.commit()
    db.refresh(window)
    return to_time_window_read(window)


@router.patch("/{windowId}/deactivate", response_model=AttendanceTimeWindowRead)
def deactivate_time_window(windowId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    window = get_time_window_or_404(db, windowId)
    window.status = "Inactive"
    db.commit()
    db.refresh(window)
    return to_time_window_read(window)
