from datetime import timedelta

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query, Session

from app.models.notification import Notification
from app.models.user import User
from app.utils.time import utc_now_naive


VALID_SEVERITIES = {"INFO", "SUCCESS", "WARNING", "ACTION_REQUIRED"}
READ_RETENTION_DAYS = 90
DEFAULT_NOTIFICATION_LIMIT = 30
MAX_NOTIFICATION_LIMIT = 100


def create_notification(
    db: Session,
    *,
    type: str,
    severity: str,
    title: str,
    message: str,
    action_url: str | None = None,
    recipient_user_id: int | None = None,
    recipient_role: str | None = None,
    department_id: int | None = None,
    commit: bool = False,
) -> Notification:
    if (recipient_user_id is None) == (recipient_role is None):
        raise ValueError("A notification must target exactly one user or one role scope.")
    normalized_severity = severity.strip().upper()
    if normalized_severity not in VALID_SEVERITIES:
        raise ValueError("Invalid notification severity.")

    notification = Notification(
        recipientUserId=recipient_user_id,
        recipientRole=recipient_role,
        departmentId=department_id,
        type=type.strip()[:60],
        severity=normalized_severity,
        title=title.strip()[:160],
        message=message.strip()[:500],
        actionUrl=action_url,
    )
    db.add(notification)
    purge_expired_read_notifications(db)
    if commit:
        db.commit()
        db.refresh(notification)
    else:
        db.flush()
    return notification


def purge_expired_read_notifications(db: Session) -> int:
    cutoff = utc_now_naive() - timedelta(days=READ_RETENTION_DAYS)
    return (
        db.query(Notification)
        .filter(Notification.readAt.is_not(None), Notification.readAt < cutoff)
        .delete(synchronize_session=False)
    )


def visible_notifications_query(db: Session, user: User) -> Query:
    role_name = user.role.roleName if user.role else ""
    private_scope = Notification.recipientUserId == user.userId

    if role_name == "Admin":
        role_scope = Notification.recipientRole == "Admin"
    elif role_name == "User" and user.accessScope == "AllDepartments":
        role_scope = and_(
            Notification.recipientRole == "User",
            Notification.departmentId.is_not(None),
        )
    elif role_name == "User" and user.assignedDepartmentId is not None:
        role_scope = and_(
            Notification.recipientRole == "User",
            Notification.departmentId == user.assignedDepartmentId,
        )
    else:
        role_scope = Notification.notificationId == -1

    return db.query(Notification).filter(or_(private_scope, role_scope))


def list_notifications(db: Session, user: User, limit: int = DEFAULT_NOTIFICATION_LIMIT) -> list[Notification]:
    safe_limit = max(1, min(limit, MAX_NOTIFICATION_LIMIT))
    return (
        visible_notifications_query(db, user)
        .order_by(Notification.createdAt.desc(), Notification.notificationId.desc())
        .limit(safe_limit)
        .all()
    )


def unread_count(db: Session, user: User) -> int:
    return visible_notifications_query(db, user).filter(Notification.readAt.is_(None)).count()


def get_visible_notification(db: Session, user: User, notification_id: int) -> Notification | None:
    return visible_notifications_query(db, user).filter(Notification.notificationId == notification_id).one_or_none()


def mark_notification_read(db: Session, notification: Notification) -> Notification:
    if notification.readAt is None:
        notification.readAt = utc_now_naive()
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_notifications_read(db: Session, user: User) -> int:
    unread = visible_notifications_query(db, user).filter(Notification.readAt.is_(None)).all()
    now = utc_now_naive()
    for notification in unread:
        notification.readAt = now
    db.commit()
    return len(unread)
