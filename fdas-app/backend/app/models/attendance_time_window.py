from datetime import datetime, time

from sqlalchemy import DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utc_now_naive


class AttendanceTimeWindow(Base):
    __tablename__ = "attendance_time_windows"

    windowId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    departmentId: Mapped[int] = mapped_column(ForeignKey("departments.departmentId"), nullable=False)
    startTime: Mapped[time] = mapped_column(Time, nullable=False)
    endTime: Mapped[time] = mapped_column(Time, nullable=False)
    graceMinutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Active", nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    department = relationship("Department", back_populates="timeWindows")
