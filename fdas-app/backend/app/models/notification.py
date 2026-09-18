from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utc_now_naive


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_created", "recipientUserId", "createdAt"),
        Index("ix_notifications_scope_created", "recipientRole", "departmentId", "createdAt"),
        Index("ix_notifications_unread", "readAt", "createdAt"),
    )

    notificationId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipientUserId: Mapped[int | None] = mapped_column(ForeignKey("users.userId"), nullable=True, index=True)
    recipientRole: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    departmentId: Mapped[int | None] = mapped_column(ForeignKey("departments.departmentId"), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default="INFO")
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    actionUrl: Mapped[str | None] = mapped_column(String(255), nullable=True)
    readAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False, index=True)

    recipientUser = relationship("User")
    department = relationship("Department")
