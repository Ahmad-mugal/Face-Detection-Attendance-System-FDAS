from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utc_now_naive


class ClassRoom(Base):
    __tablename__ = "classrooms"

    classId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    className: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    departmentId: Mapped[int] = mapped_column(ForeignKey("departments.departmentId"), nullable=False)
    yearSemester: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Active", nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    department = relationship("Department", back_populates="classrooms")
    students = relationship("Student", back_populates="classroom")
    attendanceRecords = relationship("AttendanceRecord", back_populates="classroom")
