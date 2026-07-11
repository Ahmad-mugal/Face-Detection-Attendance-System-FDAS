from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.attendance_session import AttendanceSession
from app.models.user import User
from app.schemas.attendance_sessions import AttendanceSessionRead, AttendanceSessionStartRequest
from app.services.attendance_sessions import (
    ACTIVE_SESSION_STATUS,
    close_attendance_session,
    ensure_session_access,
    get_session_or_404,
    list_accessible_sessions,
    start_attendance_session,
)


router = APIRouter(prefix="/api/attendance-sessions", tags=["attendance-sessions"])


def to_session_read(session: AttendanceSession) -> AttendanceSessionRead:
    return AttendanceSessionRead(
        sessionId=session.sessionId,
        departmentId=session.departmentId,
        departmentName=session.department.departmentName if session.department else None,
        startedByUserId=session.startedByUserId,
        startedByUserName=session.startedByUser.fullName if session.startedByUser else None,
        scheduledStartTime=session.scheduledStartTime,
        scheduledEndTime=session.scheduledEndTime,
        actualStartTime=session.actualStartTime,
        actualEndTime=session.actualEndTime,
        status=session.status,
        createdDate=session.createdDate,
        createdAt=session.createdAt,
        updatedAt=session.updatedAt,
    )


@router.post("/start", response_model=AttendanceSessionRead, status_code=201)
def start_session(
    payload: AttendanceSessionStartRequest,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    session = start_attendance_session(db, current_user, payload.departmentId)
    return to_session_read(session)


@router.post("/{sessionId}/stop", response_model=AttendanceSessionRead)
def stop_session(
    sessionId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    session = close_attendance_session(db, current_user, sessionId, "Closed")
    return to_session_read(session)


@router.post("/{sessionId}/cancel", response_model=AttendanceSessionRead)
def cancel_session(
    sessionId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    session = close_attendance_session(db, current_user, sessionId, "Cancelled")
    return to_session_read(session)


@router.get("/active", response_model=list[AttendanceSessionRead])
def list_active_sessions(
    departmentId: int | None = Query(default=None),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    sessions = (
        list_accessible_sessions(
            db,
            current_user,
            departmentId=departmentId,
            session_status=ACTIVE_SESSION_STATUS,
        )
        .order_by(AttendanceSession.departmentId, AttendanceSession.actualStartTime.desc())
        .all()
    )
    return [to_session_read(session) for session in sessions]


@router.get("", response_model=list[AttendanceSessionRead])
def list_sessions(
    departmentId: int | None = Query(default=None),
    status: str | None = Query(default=None),
    dateFrom: date | None = Query(default=None),
    dateTo: date | None = Query(default=None),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    sessions = (
        list_accessible_sessions(
            db,
            current_user,
            departmentId=departmentId,
            session_status=status,
            date_from=dateFrom,
            date_to=dateTo,
        )
        .order_by(AttendanceSession.createdDate.desc(), AttendanceSession.sessionId.desc())
        .all()
    )
    return [to_session_read(session) for session in sessions]


@router.get("/{sessionId}", response_model=AttendanceSessionRead)
def get_session(
    sessionId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, sessionId)
    ensure_session_access(current_user, session)
    return to_session_read(session)
