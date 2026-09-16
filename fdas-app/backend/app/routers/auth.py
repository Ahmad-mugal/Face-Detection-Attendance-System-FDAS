from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_approved_user
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    RegisterRequestResponse,
    RegistrationDepartmentOption,
    UserProfile,
)
from app.utils.jwt import create_access_token
from app.utils.security import hash_password, verify_password


router = APIRouter(prefix="/api/auth", tags=["auth"])


def build_user_profile(user: User) -> UserProfile:
    return UserProfile(
        userId=user.userId,
        fullName=user.fullName,
        email=user.email,
        role=user.role.roleName,
        status=user.status,
        accessScope=user.accessScope,
        assignedDepartmentId=user.assignedDepartmentId,
        assignedDepartmentName=user.assignedDepartment.departmentName if user.assignedDepartment else None,
        createdAt=user.createdAt,
        updatedAt=user.updatedAt,
    )


def build_token_claims(user: User) -> dict:
    return {
        "userId": user.userId,
        "email": user.email,
        "role": user.role.roleName,
        "accessScope": user.accessScope,
        "assignedDepartmentId": user.assignedDepartmentId,
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == payload.email).one_or_none()
    if user is None or not verify_password(payload.password, user.passwordHash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.status != "Approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"User status is {user.status}")

    return {
        "accessToken": create_access_token(build_token_claims(user)),
        "tokenType": "bearer",
        "user": build_user_profile(user),
    }


@router.get("/me", response_model=UserProfile)
def me(current_user: User = Depends(require_approved_user)):
    return build_user_profile(current_user)


@router.patch("/me", response_model=UserProfile)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    current_user.fullName = payload.fullName
    db.commit()
    db.refresh(current_user)
    return build_user_profile(current_user)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(require_approved_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.currentPassword, current_user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if verify_password(payload.newPassword, current_user.passwordHash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )
    current_user.passwordHash = hash_password(payload.newPassword)
    db.commit()
    return {"message": "Password changed successfully."}


@router.get("/registration-departments", response_model=list[RegistrationDepartmentOption])
def registration_departments(db: Session = Depends(get_db)):
    return (
        db.query(Department)
        .filter(Department.status == "Active")
        .order_by(Department.departmentName)
        .all()
    )


@router.post("/register-request", response_model=RegisterRequestResponse, status_code=status.HTTP_201_CREATED)
def register_request(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(func.lower(User.email) == payload.email).one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    department = db.query(Department).filter(Department.departmentId == payload.requestedDepartmentId).one_or_none()
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested department not found")

    role = db.query(Role).filter(Role.roleName == "User").one_or_none()
    if role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User role is not seeded")

    user = User(
        fullName=payload.fullName,
        email=payload.email,
        passwordHash=hash_password(payload.password),
        roleId=role.roleId,
        status="Pending",
        assignedDepartmentId=payload.requestedDepartmentId,
        accessScope="Department",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )
    db.refresh(user)

    return {
        "userId": user.userId,
        "fullName": user.fullName,
        "email": user.email,
        "status": user.status,
        "accessScope": user.accessScope,
        "assignedDepartmentId": user.assignedDepartmentId,
    }
