from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FaceTemplate(Base):
    __tablename__ = "face_templates"

    templateId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    studentId: Mapped[int] = mapped_column(ForeignKey("students.studentId"), nullable=False, index=True)
    templatePath: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encodingData: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Pending", nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student = relationship("Student", back_populates="faceTemplates")

