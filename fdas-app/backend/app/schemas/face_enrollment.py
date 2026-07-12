from datetime import datetime

from pydantic import BaseModel


class FaceTemplateRead(BaseModel):
    templateId: int
    studentId: int
    templatePath: str | None = None
    sampleIndex: int | None = None
    status: str
    isActive: bool
    createdAt: datetime
    updatedAt: datetime
    createdByUserId: int | None = None


class FaceEnrollmentUploadResponse(BaseModel):
    studentId: int
    faceRegistered: bool
    uploadedSamples: list[FaceTemplateRead]


class FaceEnrollmentListResponse(BaseModel):
    studentId: int
    faceRegistered: bool
    templates: list[FaceTemplateRead]


class FaceEnrollmentClearResponse(BaseModel):
    studentId: int
    deactivatedCount: int
    faceRegistered: bool
