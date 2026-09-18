from datetime import datetime
import re

from pydantic import BaseModel, Field, field_validator


FULL_NAME_MIN_LENGTH = 2
FULL_NAME_MAX_LENGTH = 150
EMAIL_MAX_LENGTH = 180
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not email:
        raise ValueError("Email is required.")
    if len(email) > EMAIL_MAX_LENGTH:
        raise ValueError(f"Email must be at most {EMAIL_MAX_LENGTH} characters long.")
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_login_password(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("Password is required.")
    return value


class LoginRequest(BaseModel):
    email: str
    password: str

    _normalize_email = field_validator("email")(normalize_email)
    _validate_password = field_validator("password")(validate_login_password)


class RegisterRequest(BaseModel):
    fullName: str
    email: str
    password: str
    requestedDepartmentId: int = Field(gt=0)

    @field_validator("fullName")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        full_name = value.strip()
        if not full_name:
            raise ValueError("Full name is required.")
        if len(full_name) < FULL_NAME_MIN_LENGTH:
            raise ValueError(f"Full name must be at least {FULL_NAME_MIN_LENGTH} characters long.")
        if len(full_name) > FULL_NAME_MAX_LENGTH:
            raise ValueError(f"Full name must be at most {FULL_NAME_MAX_LENGTH} characters long.")
        return full_name

    _normalize_email = field_validator("email")(normalize_email)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Password is required.")
        if len(value) < PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
        if len(value) > PASSWORD_MAX_LENGTH:
            raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters long.")
        return value


class UserProfile(BaseModel):
    userId: int
    fullName: str
    email: str
    role: str
    status: str
    accessScope: str
    assignedDepartmentId: int | None = None
    assignedDepartmentName: str | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class ProfileUpdateRequest(BaseModel):
    fullName: str

    @field_validator("fullName")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        return RegisterRequest.validate_full_name(value)


class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str

    _validate_current_password = field_validator("currentPassword")(validate_login_password)

    @field_validator("newPassword")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return RegisterRequest.validate_password(value)


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


class RegistrationDepartmentOption(BaseModel):
    departmentId: int
    departmentName: str


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


class ApprovalNotificationResponse(BaseModel):
    user: AdminUserListItem
    emailNotificationSent: bool
    emailNotificationMessage: str


class EmailCapabilityResponse(BaseModel):
    configured: bool
    deliveryOptional: bool
    message: str


class DeleteUserResponse(BaseModel):
    deleted: bool
    message: str
