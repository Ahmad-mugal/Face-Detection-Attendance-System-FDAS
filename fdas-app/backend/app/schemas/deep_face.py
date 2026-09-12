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
    diagnosticMatchingImplemented: bool = False
    scoringMethod: str | None = None
    threshold: float | None = None
    requiredIdentityMargin: float | None = None
    calibrationLabel: str | None = None
    eligibleEmbeddingMinimum: int | None = None


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


class DeepRecoverySampleValidation(BaseModel):
    success: bool
    status: str
    message: str
    haarFaceCount: int
    deepFaceCount: int | None = None
    embeddingDimension: int | None = None
    encodingVersion: str
    l2Norm: float | None = None
    processingMilliseconds: float
    persistentWrite: bool = False


class DeepDiagnosticCandidate(BaseModel):
    studentId: int
    studentName: str
    rollNo: str
    score: float
    bestTemplateId: int
    bestEmbeddingId: int
    templatesEvaluated: int


class DeepDiagnosticMatchResponse(BaseModel):
    matched: bool
    status: str
    message: str
    attendanceCreated: bool = False
    persistentWrite: bool = False
    activeForAttendance: bool = False
    attendanceSafetyHold: bool
    encodingVersion: str
    calibrationLabel: str
    scoringMethod: str
    thresholdUsed: float
    requiredMargin: float
    candidateStudentCount: int
    candidateEmbeddingCount: int
    excludedCandidateCount: int
    expectedStudentId: int | None = None
    expectedStudentScore: float | None = None
    topCandidate: DeepDiagnosticCandidate | None = None
    secondCandidate: DeepDiagnosticCandidate | None = None
    scoreMargin: float | None = None
    topAboveThreshold: bool
    marginPassed: bool
