from datetime import datetime

from pydantic import BaseModel


class AttendanceRecordRead(BaseModel):
    attendanceRecordId: int
    sessionId: int
    studentId: int
    studentName: str
    rollNo: str
    departmentId: int
    departmentName: str | None = None
    classId: int
    className: str | None = None
    markedAt: datetime
    status: str
    recognitionConfidence: float | None = None
    recognitionProvider: str | None = None
    recognitionEncodingVersion: str | None = None
    recognitionMethod: str | None = None
    identityMargin: float | None = None
    livenessStatus: str | None = None


class AttendanceRecordsSummary(BaseModel):
    totalRecords: int
    presentCount: int
    uniqueStudentsMarked: int
    averageRecognitionConfidence: float | None = None
