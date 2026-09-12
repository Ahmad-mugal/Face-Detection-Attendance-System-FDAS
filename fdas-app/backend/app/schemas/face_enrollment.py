from datetime import datetime

from pydantic import BaseModel


class FaceTemplateRead(BaseModel):
    templateId: int
    studentId: int
    templatePath: str | None = None
    encodingVersion: str | None = None
    faceBoxJson: str | None = None
    hasEncodingData: bool = False
    sampleIndex: int | None = None
    status: str
    isActive: bool
    processedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime
    createdByUserId: int | None = None


class FaceEnrollmentUploadResponse(BaseModel):
    studentId: int
    faceRegistered: bool
    hasEncodedTemplates: bool = False
    uploadedSamples: list[FaceTemplateRead]


class FaceEnrollmentListResponse(BaseModel):
    studentId: int
    faceRegistered: bool
    hasEncodedTemplates: bool = False
    templates: list[FaceTemplateRead]


class FaceEnrollmentClearResponse(BaseModel):
    studentId: int
    deactivatedCount: int
    faceRegistered: bool
    hasEncodedTemplates: bool = False


class FaceTemplateProcessResponse(BaseModel):
    template: FaceTemplateRead
    processingSucceeded: bool
    noFaceDetected: bool


class FaceEnrollmentProcessAllResponse(BaseModel):
    studentId: int
    processed: int
    noFaceDetected: int
    failed: int


class FaceProcessingInfo(BaseModel):
    provider: str
    encodingVersion: str
    recognitionMatchingImplemented: bool
    livenessImplemented: bool


class DeepEnrollmentReadinessResponse(BaseModel):
    studentId: int
    studentName: str
    rollNo: str
    validDeepEmbeddings: int
    requiredMinimum: int
    additionalNeeded: int
    readiness: str
    existingHistoricalImages: int
    missingHistoricalImages: int
    attendanceSafetyHold: bool
    activeForAttendance: bool


class DeepRecoveryUploadResponse(BaseModel):
    studentId: int
    studentName: str
    rollNo: str
    deepCountBefore: int
    deepCountAfter: int
    requiredMinimum: int
    additionalNeeded: int
    readiness: str
    recoverySamples: list[FaceTemplateRead]
    deepEmbeddingIds: list[int]
    attendanceCreated: bool
    attendanceSafetyHold: bool
    activeForAttendance: bool
