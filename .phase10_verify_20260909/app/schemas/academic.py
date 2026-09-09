from datetime import datetime, time

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    departmentName: str = Field(min_length=2, max_length=120)
    status: str = "Active"


class DepartmentUpdate(BaseModel):
    departmentName: str | None = Field(default=None, min_length=2, max_length=120)
    status: str | None = None


class DepartmentRead(BaseModel):
    departmentId: int
    departmentName: str
    status: str
    createdAt: datetime
    updatedAt: datetime


class ClassRoomCreate(BaseModel):
    className: str = Field(min_length=2, max_length=120)
    departmentId: int
    yearSemester: str = Field(min_length=1, max_length=50)
    section: str = Field(min_length=1, max_length=30)
    status: str = "Active"


class ClassRoomUpdate(BaseModel):
    className: str | None = Field(default=None, min_length=2, max_length=120)
    departmentId: int | None = None
    yearSemester: str | None = Field(default=None, min_length=1, max_length=50)
    section: str | None = Field(default=None, min_length=1, max_length=30)
    status: str | None = None


class ClassRoomRead(BaseModel):
    classId: int
    className: str
    departmentId: int
    departmentName: str | None = None
    yearSemester: str
    section: str
    status: str
    createdAt: datetime
    updatedAt: datetime


class StudentCreate(BaseModel):
    rollNo: str = Field(min_length=1, max_length=80)
    fullName: str = Field(min_length=2, max_length=150)
    email: str | None = Field(default=None, max_length=180)
    phone: str | None = Field(default=None, max_length=40)
    departmentId: int
    classId: int
    yearSemester: str | None = Field(default=None, max_length=50)
    section: str | None = Field(default=None, max_length=30)
    status: str = "Active"


class StudentUpdate(BaseModel):
    rollNo: str | None = Field(default=None, min_length=1, max_length=80)
    fullName: str | None = Field(default=None, min_length=2, max_length=150)
    email: str | None = Field(default=None, max_length=180)
    phone: str | None = Field(default=None, max_length=40)
    departmentId: int | None = None
    classId: int | None = None
    yearSemester: str | None = Field(default=None, max_length=50)
    section: str | None = Field(default=None, max_length=30)
    status: str | None = None


class StudentRead(BaseModel):
    studentId: int
    rollNo: str
    fullName: str
    email: str | None = None
    phone: str | None = None
    departmentId: int
    departmentName: str | None = None
    classId: int
    className: str | None = None
    yearSemester: str
    section: str
    status: str
    faceRegistered: bool = False
    hasEncodedFaceTemplates: bool = False
    createdAt: datetime
    updatedAt: datetime


class AttendanceTimeWindowCreate(BaseModel):
    departmentId: int
    startTime: time
    endTime: time
    graceMinutes: int = Field(default=10, ge=0, le=240)
    status: str = "Active"


class AttendanceTimeWindowUpdate(BaseModel):
    departmentId: int | None = None
    startTime: time | None = None
    endTime: time | None = None
    graceMinutes: int | None = Field(default=None, ge=0, le=240)
    status: str | None = None


class AttendanceTimeWindowRead(BaseModel):
    windowId: int
    departmentId: int
    departmentName: str | None = None
    startTime: time
    endTime: time
    graceMinutes: int
    status: str
    createdAt: datetime
    updatedAt: datetime
