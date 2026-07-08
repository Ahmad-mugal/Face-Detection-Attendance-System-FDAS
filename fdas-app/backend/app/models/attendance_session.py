from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    sessionId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    departmentId: Mapped[int] = mapped_column(ForeignKey("departments.departmentId"), nullable=False)
    startedByUserId: Mapped[int] = mapped_column(ForeignKey("users.userId"), nullable=False)
    scheduledStartTime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    scheduledEndTime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actualStartTime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actualEndTime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Active", nullable=False)
    createdDate: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    department = relationship("Department", back_populates="sessions")
    startedByUser = relationship("User", back_populates="attendanceSessions")
    attendanceRecords = relationship("AttendanceRecord", back_populates="session")

