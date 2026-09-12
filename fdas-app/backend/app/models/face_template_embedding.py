from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time import utc_now_naive


class FaceTemplateEmbedding(Base):
    __tablename__ = "face_template_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "faceTemplateId",
            "encodingVersion",
            name="uq_face_template_embedding_version",
        ),
        Index(
            "ix_face_template_embeddings_student_version_active",
            "studentId",
            "encodingVersion",
            "isActive",
        ),
    )

    faceTemplateEmbeddingId: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    faceTemplateId: Mapped[int] = mapped_column(
        ForeignKey("face_templates.templateId"),
        nullable=False,
        index=True,
    )
    studentId: Mapped[int] = mapped_column(ForeignKey("students.studentId"), nullable=False, index=True)
    encodingVersion: Mapped[str] = mapped_column(String(80), nullable=False)
    embeddingData: Mapped[str] = mapped_column(Text, nullable=False)
    embeddingDimension: Mapped[int] = mapped_column(Integer, nullable=False)
    modelName: Mapped[str] = mapped_column(String(80), nullable=False)
    sourceImageSha256: Mapped[str] = mapped_column(String(64), nullable=False)
    l2Norm: Mapped[float] = mapped_column(Float, nullable=False)
    processingMilliseconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    isActive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now_naive,
        onupdate=utc_now_naive,
        nullable=False,
    )

    faceTemplate = relationship("FaceTemplate", back_populates="deepEmbeddings")
    student = relationship("Student", back_populates="faceTemplateEmbeddings")
