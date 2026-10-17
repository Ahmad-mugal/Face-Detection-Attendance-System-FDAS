from datetime import datetime

from pydantic import BaseModel, Field


class AttendanceMarkResult(BaseModel):
    attendanceMarked: bool
    status: str
    message: str
    attendanceRecordId: int | None = None
    sessionId: int | None = None
    studentId: int | None = None
    studentName: str | None = None
    rollNo: str | None = None
    classId: int | None = None
    className: str | None = None
    departmentId: int | None = None
    departmentName: str | None = None
    markedAt: datetime | None = None
    recognitionConfidence: float | None = None
    recognitionProvider: str | None = None
    recognitionEncodingVersion: str | None = None
    recognitionMethod: str | None = None
    identityMargin: float | None = None
    topStudentId: int | None = None
    topStudentName: str | None = None
    topRollNo: str | None = None
    topScore: float | None = None
    secondStudentId: int | None = None
    secondStudentName: str | None = None
    secondRollNo: str | None = None
    secondScore: float | None = None
    secondRecognitionConfidence: float | None = None
    scoreMargin: float | None = None
    thresholdUsed: float | None = None
    requiredMargin: float | None = None
    aggregationMethod: str | None = None
    livenessStatus: str | None = None
    controlledTest: bool = False
    livenessDiagnostics: dict[str, bool | int | float | str | None] | None = None
    queryCount: int = 0
    validQueryCount: int = 0
    consensusStudentId: int | None = None
    consensusCount: int = 0
    queryTopStudentIds: list[int] = Field(default_factory=list)
    queryTopScores: list[float] = Field(default_factory=list)
    queryQuality: list[dict] = Field(default_factory=list)
    retryable: bool = False


class AttendanceSessionRecordRead(BaseModel):
    attendanceRecordId: int
    sessionId: int
    studentId: int
    studentName: str
    rollNo: str
    classId: int
    className: str | None = None
    departmentId: int
    departmentName: str | None = None
    markedAt: datetime
    status: str
    recognitionConfidence: float | None = None
    recognitionProvider: str | None = None
    recognitionEncodingVersion: str | None = None
    recognitionMethod: str | None = None
    identityMargin: float | None = None
    livenessStatus: str | None = None


class FastFaceBoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int
    normalizedX: float
    normalizedY: float
    normalizedWidth: float
    normalizedHeight: float


class FastFaceOutcome(BaseModel):
    faceId: str
    faceIndex: int
    bbox: FastFaceBoundingBox
    detectionScore: float
    status: str
    message: str
    quality: dict[str, bool | float | str] = Field(default_factory=dict)
    attendanceMarked: bool = False
    attendanceRecordId: int | None = None
    studentId: int | None = None
    studentName: str | None = None
    rollNo: str | None = None
    classId: int | None = None
    className: str | None = None
    recognitionConfidence: float | None = None
    secondRecognitionConfidence: float | None = None
    identityMargin: float | None = None
    thresholdUsed: float
    requiredMargin: float
    recognitionProvider: str
    recognitionEncodingVersion: str
    recognitionMethod: str
    livenessStatus: str


class FastAttendanceTiming(BaseModel):
    decodeMilliseconds: float
    detectorMilliseconds: float
    alignmentMilliseconds: float
    embeddingMilliseconds: float
    galleryMilliseconds: float
    matchingMilliseconds: float
    recognitionMilliseconds: float
    serviceMilliseconds: float
    databaseMilliseconds: float
    totalMilliseconds: float


class FastAttendanceResult(BaseModel):
    attendanceMode: str
    sessionId: int
    departmentId: int
    departmentName: str | None = None
    sourceWidth: int
    sourceHeight: int
    rotationDegrees: int = 0
    mirroredPreview: bool = True
    faces: list[FastFaceOutcome] = Field(default_factory=list)
    facesDetected: int
    markedCount: int
    alreadyMarkedCount: int
    rejectedCount: int
    qualityIssueCount: int = 0
    candidateStudentCount: int
    candidateEmbeddingCount: int
    galleryCacheHit: bool
    timing: FastAttendanceTiming
    diagnostics: dict[str, int] = Field(default_factory=dict)
