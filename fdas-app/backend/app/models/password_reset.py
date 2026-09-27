from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.time import utc_now_naive


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        Index("ix_password_reset_user_type", "userId", "tokenType", "createdAt"),
        Index("ix_password_reset_active", "usedAt", "revokedAt", "expiresAt"),
    )

    passwordResetTokenId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    userId: Mapped[int] = mapped_column(ForeignKey("users.userId"), nullable=False, index=True)
    tokenHash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    tokenType: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    expiresAt: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    usedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    createdByAdminUserId: Mapped[int | None] = mapped_column(ForeignKey("users.userId"), nullable=True)
    failedAttemptCount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revokedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PasswordResetThrottle(Base):
    __tablename__ = "password_reset_throttles"
    __table_args__ = (
        Index("ix_password_reset_throttle_email_created", "emailKeyHash", "createdAt"),
        Index("ix_password_reset_throttle_client_created", "clientKeyHash", "createdAt"),
    )

    passwordResetThrottleId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    emailKeyHash: Mapped[str] = mapped_column(String(64), nullable=False)
    clientKeyHash: Mapped[str] = mapped_column(String(64), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
