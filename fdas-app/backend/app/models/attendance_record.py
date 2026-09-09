from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utc_now_naive


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("sessionId", "studentId", name="uq_attendance_session_student"),
    )

    attendanceId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sessionId: Mapped[int] = mapped_column(ForeignKey("attendance_sessions.sessionId"), nullable=False)
    studentId: Mapped[int] = mapped_column(ForeignKey("students.studentId"), nullable=False)
    departmentId: Mapped[int] = mapped_column(ForeignKey("departments.departmentId"), nullable=False)
    classId: Mapped[int] = mapped_column(ForeignKey("classrooms.classId"), nullable=False)
    markedAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    recognitionConfidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    livenessStatus: Mapped[str | None] = mapped_column(String(30), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)

    session = relationship("AttendanceSession", back_populates="attendanceRecords")
    student = relationship("Student", back_populates="attendanceRecords")
    department = relationship("Department", back_populates="attendanceRecords")
    classroom = relationship("ClassRoom", back_populates="attendanceRecords")
