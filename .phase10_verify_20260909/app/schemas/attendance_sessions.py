from datetime import date, datetime

from pydantic import BaseModel


class AttendanceSessionStartRequest(BaseModel):
    departmentId: int


class AttendanceSessionRead(BaseModel):
    sessionId: int
    departmentId: int
    departmentName: str | None = None
    startedByUserId: int
    startedByUserName: str | None = None
    scheduledStartTime: datetime
    scheduledEndTime: datetime
    actualStartTime: datetime | None = None
    actualEndTime: datetime | None = None
    status: str
    createdDate: date
    createdAt: datetime
    updatedAt: datetime
