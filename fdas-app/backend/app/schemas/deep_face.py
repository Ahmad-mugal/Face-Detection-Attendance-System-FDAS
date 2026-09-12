from pydantic import BaseModel


class DeepFaceInfo(BaseModel):
    deepRecognitionAvailable: bool
    deepRecognitionProvider: str
    deepRecognitionModel: str
    deepEmbeddingDimension: int
    deepRecognitionExecutionProvider: str
    deepRecognitionReady: bool
    encodingVersion: str
    activeForAttendance: bool
    attendanceSafetyHold: bool
    modelDirectory: str
    initializationMilliseconds: float | None = None
    error: str | None = None


class DeepEncodingDryRunResponse(BaseModel):
    success: bool
    status: str
    message: str
    templateId: int
    studentId: int
    imageFound: bool
    haarFaceCount: int | None = None
    deepFaceCount: int | None = None
    embeddingDimension: int | None = None
    encodingVersion: str
    l2Norm: float | None = None
    processingMilliseconds: float | None = None
    model: str
    executionProvider: str
    attendanceCreated: bool = False
    persistentWrite: bool = False
