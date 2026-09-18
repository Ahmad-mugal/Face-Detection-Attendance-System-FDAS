from datetime import datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    notificationId: int
    type: str
    severity: str
    title: str
    message: str
    actionUrl: str | None = None
    isRead: bool
    readAt: datetime | None = None
    createdAt: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationRead]
    unreadCount: int


class NotificationUnreadCountResponse(BaseModel):
    unreadCount: int


class NotificationMarkAllResponse(BaseModel):
    markedRead: int
