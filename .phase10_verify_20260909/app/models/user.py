from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    userId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fullName: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    passwordHash: Mapped[str] = mapped_column(String(255), nullable=False)
    roleId: Mapped[int] = mapped_column(ForeignKey("roles.roleId"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Pending", nullable=False)
    assignedDepartmentId: Mapped[int | None] = mapped_column(ForeignKey("departments.departmentId"), nullable=True)
    accessScope: Mapped[str] = mapped_column(String(40), default="Department", nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    role = relationship("Role", back_populates="users")
    assignedDepartment = relationship("Department", back_populates="users")
    attendanceSessions = relationship("AttendanceSession", back_populates="startedByUser")

