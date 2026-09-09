from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utc_now_naive


class FaceTemplate(Base):
    __tablename__ = "face_templates"

    templateId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    studentId: Mapped[int] = mapped_column(ForeignKey("students.studentId"), nullable=False, index=True)
    templatePath: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encodingData: Mapped[str | None] = mapped_column(Text, nullable=True)
    encodingVersion: Mapped[str | None] = mapped_column(String(80), nullable=True)
    faceBoxJson: Mapped[str | None] = mapped_column(Text, nullable=True)
    sampleIndex: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Pending", nullable=False)
    isActive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    createdByUserId: Mapped[int | None] = mapped_column(ForeignKey("users.userId"), nullable=True)
    processedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    student = relationship("Student", back_populates="faceTemplates")
