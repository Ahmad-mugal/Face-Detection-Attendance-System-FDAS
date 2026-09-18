from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_approved_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationMarkAllResponse,
    NotificationRead,
    NotificationUnreadCountResponse,
)
from app.services.notifications import (
    get_visible_notification,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    unread_count,
)


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def to_notification_read(notification: Notification) -> NotificationRead:
    return NotificationRead(
        notificationId=notification.notificationId,
        type=notification.type,
        severity=notification.severity,
        title=notification.title,
        message=notification.message,
        actionUrl=notification.actionUrl,
        isRead=notification.readAt is not None,
        readAt=notification.readAt,
        createdAt=notification.createdAt,
    )


@router.get("", response_model=NotificationListResponse)
def get_notifications(
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    items = list_notifications(db, current_user, limit)
    return NotificationListResponse(
        notifications=[to_notification_read(item) for item in items],
        unreadCount=unread_count(db, current_user),
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_unread_count(
    current_user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    return NotificationUnreadCountResponse(unreadCount=unread_count(db, current_user))


@router.patch("/{notificationId}/read", response_model=NotificationRead)
def read_notification(
    notificationId: int,
    current_user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    notification = get_visible_notification(db, current_user, notificationId)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return to_notification_read(mark_notification_read(db, notification))


@router.post("/mark-all-read", response_model=NotificationMarkAllResponse)
def mark_all_read(
    current_user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    return NotificationMarkAllResponse(markedRead=mark_all_notifications_read(db, current_user))
