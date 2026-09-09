from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utc_now_naive


class Department(Base):
    __tablename__ = "departments"

    departmentId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    departmentName: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="Active", nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    users = relationship("User", back_populates="assignedDepartment")
    classrooms = relationship("ClassRoom", back_populates="department")
    students = relationship("Student", back_populates="department")
    timeWindows = relationship("AttendanceTimeWindow", back_populates="department")
    sessions = relationship("AttendanceSession", back_populates="department")
    attendanceRecords = relationship("AttendanceRecord", back_populates="department")
