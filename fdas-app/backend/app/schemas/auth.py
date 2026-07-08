from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    fullName: str = Field(min_length=2, max_length=150)
    email: str
    password: str = Field(min_length=8, max_length=128)
    requestedDepartmentId: int


class UserProfile(BaseModel):
    userId: int
    fullName: str
    email: str
    role: str
    status: str
    accessScope: str
    assignedDepartmentId: int | None = None
    assignedDepartmentName: str | None = None


class LoginResponse(BaseModel):
    accessToken: str
    tokenType: str
    user: UserProfile


class RegisterRequestResponse(BaseModel):
    userId: int
    fullName: str
    email: str
    status: str
    accessScope: str
    assignedDepartmentId: int


class AccessUpdateRequest(BaseModel):
    assignedDepartmentId: int | None = None
    accessScope: str


class AdminUserListItem(BaseModel):
    userId: int
    fullName: str
    email: str
    role: str
    status: str
    assignedDepartment: str | None = None
    assignedDepartmentId: int | None = None
    accessScope: str
    createdAt: datetime
    updatedAt: datetime
