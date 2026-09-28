from datetime import datetime, timezone

from pydantic import BaseModel, field_serializer


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

    @field_serializer("readAt", "createdAt", when_used="json")
    def serialize_utc_timestamp(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return utc_value.isoformat().replace("+00:00", "Z")


class NotificationListResponse(BaseModel):
    notifications: list[NotificationRead]
    unreadCount: int


class NotificationUnreadCountResponse(BaseModel):
    unreadCount: int


class NotificationMarkAllResponse(BaseModel):
    markedRead: int
