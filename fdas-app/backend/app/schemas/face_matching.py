from pydantic import BaseModel, Field


class FaceMatchResult(BaseModel):
    matched: bool
    status: str
    message: str
    studentId: int | None = None
    studentName: str | None = None
    rollNo: str | None = None
    classId: int | None = None
    className: str | None = None
    departmentId: int | None = None
    departmentName: str | None = None
    bestTemplateId: int | None = None
    similarityScore: float | None = None
    secondSimilarityScore: float | None = None
    scoreMargin: float | None = None
    thresholdUsed: float
    aggregationMethod: str
    requiredMargin: float
    candidateCount: int


class FaceMatchingInfo(BaseModel):
    provider: str
    encodingVersion: str
    matchingImplemented: bool
    attendanceMarkingImplemented: bool
    livenessImplemented: bool
    threshold: float
    aggregationMethod: str
    requiredIdentityMargin: float
    attendanceSafetyHold: bool
    notes: str


class FaceMatchCandidateDiagnostic(BaseModel):
    studentId: int
    studentName: str
    rollNo: str
    bestTemplateId: int
    bestScore: float
    maximumScore: float
    meanTop3Score: float
    meanTop5Score: float
    medianTop5Score: float
    templatesEvaluated: int


class FaceMatchAggregationDiagnostic(BaseModel):
    method: str
    expectedStudentScore: float | None = None
    topStudentId: int | None = None
    topScore: float | None = None
    secondStudentId: int | None = None
    secondScore: float | None = None
    scoreMargin: float | None = None
    passesThreshold: bool
    passesMargin: bool


class FaceMatchDiagnosticResult(BaseModel):
    status: str
    message: str
    attendanceCreated: bool
    departmentId: int
    expectedStudentId: int | None = None
    expectedStudentScore: float | None = None
    thresholdUsed: float
    aggregationMethod: str = "maximum"
    requiredMargin: float = 0.05
    candidateStudentCount: int
    candidateTemplateCount: int
    topCandidate: FaceMatchCandidateDiagnostic | None = None
    secondCandidate: FaceMatchCandidateDiagnostic | None = None
    scoreMargin: float | None = None
    topAboveThreshold: bool
    candidates: list[FaceMatchCandidateDiagnostic]
    aggregations: list[FaceMatchAggregationDiagnostic] = Field(default_factory=list)


class SingleFaceCheckResult(BaseModel):
    status: str
    message: str
    faceCount: int
    ready: bool
    continuityPassed: bool | None = None
    continuitySimilarity: float | None = None
    continuityThreshold: float
