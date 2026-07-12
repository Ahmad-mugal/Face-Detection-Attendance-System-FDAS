from datetime import datetime

from pydantic import BaseModel


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
    thresholdUsed: float | None = None
    livenessStatus: str | None = None


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
    livenessStatus: str | None = None
