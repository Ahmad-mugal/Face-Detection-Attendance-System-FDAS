from pydantic import BaseModel


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
    thresholdUsed: float
    candidateCount: int


class FaceMatchingInfo(BaseModel):
    provider: str
    encodingVersion: str
    matchingImplemented: bool
    attendanceMarkingImplemented: bool
    livenessImplemented: bool
    threshold: float
    notes: str
