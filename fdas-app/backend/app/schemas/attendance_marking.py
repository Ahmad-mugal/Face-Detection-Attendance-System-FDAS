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
