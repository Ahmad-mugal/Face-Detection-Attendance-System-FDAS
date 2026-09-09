from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Student(Base):
    __tablename__ = "students"

    studentId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rollNo: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    fullName: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    departmentId: Mapped[int] = mapped_column(ForeignKey("departments.departmentId"), nullable=False)
    classId: Mapped[int] = mapped_column(ForeignKey("classrooms.classId"), nullable=False)
    yearSemester: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Active", nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    department = relationship("Department", back_populates="students")
    classroom = relationship("ClassRoom", back_populates="students")
    faceTemplates = relationship("FaceTemplate", back_populates="student")
    attendanceRecords = relationship("AttendanceRecord", back_populates="student")

