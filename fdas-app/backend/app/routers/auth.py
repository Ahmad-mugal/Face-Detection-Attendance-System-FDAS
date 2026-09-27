from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import FRONTEND_BASE_URL
from app.database import SessionLocal, get_db
from app.dependencies import require_approved_user
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.schemas.auth import (
    AdminCodePasswordResetRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GenericPasswordRecoveryResponse,
    LoginRequest,
    LoginResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    RegisterRequestResponse,
    RegistrationDepartmentOption,
    PasswordResetRequest,
    UserProfile,
)
from app.utils.jwt import create_access_token
from app.utils.security import hash_password, verify_password
from app.services.notifications import create_notification
from app.services.email_service import load_smtp_settings, send_password_reset_email
from app.services.password_recovery import (
    PUBLIC_RECOVERY_MESSAGE,
    enforce_recovery_rate_limit,
    is_recovery_eligible,
    issue_email_token,
    reset_with_admin_code,
    reset_with_email_token,
)
from app.models.password_reset import PasswordResetToken
from app.utils.time import utc_now_naive


router = APIRouter(prefix="/api/auth", tags=["auth"])


def deliver_password_reset_email(
    *,
    password_reset_token_id: int,
    user_name: str,
    recipient_email: str,
    reset_url: str,
) -> None:
    delivery = send_password_reset_email(
        user_name=user_name,
        recipient_email=recipient_email,
        reset_url=reset_url,
    )
    if delivery.sent:
        return
    with SessionLocal() as db:
        credential = db.get(PasswordResetToken, password_reset_token_id)
        if credential is not None and credential.usedAt is None and credential.revokedAt is None:
            credential.revokedAt = utc_now_naive()
        create_notification(
            db,
            recipient_role="Admin",
            type="PASSWORD_RESET_EMAIL_FAILED",
            severity="ACTION_REQUIRED",
            title="Password reset email failed",
            message="A requested password reset email could not be delivered. The reset link was revoked.",
            action_url="/admin/users",
        )
        db.commit()


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


@router.post("/forgot-password", response_model=GenericPasswordRecoveryResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    client_identity = request.client.host if request.client else "local-unknown"
    enforce_recovery_rate_limit(db, email=payload.email, client_identity=client_identity)
    user = db.query(User).filter(func.lower(User.email) == payload.email).one_or_none()
    if is_recovery_eligible(user) and load_smtp_settings().configured:
        raw_token, credential = issue_email_token(db, user)
        reset_url = f"{FRONTEND_BASE_URL}/reset-password?{urlencode({'token': raw_token})}"
        db.commit()
        background_tasks.add_task(
            deliver_password_reset_email,
            password_reset_token_id=credential.passwordResetTokenId,
            user_name=user.fullName,
            recipient_email=user.email,
            reset_url=reset_url,
        )
    else:
        db.commit()
    return {"message": PUBLIC_RECOVERY_MESSAGE}


@router.post("/reset-password", response_model=GenericPasswordRecoveryResponse)
def reset_password(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    reset_with_email_token(db, raw_token=payload.token, new_password=payload.newPassword)
    return {"message": "Password reset successfully. Please sign in with your new password."}


@router.post("/reset-password/admin-code", response_model=GenericPasswordRecoveryResponse)
def reset_password_with_admin_code(
    payload: AdminCodePasswordResetRequest,
    db: Session = Depends(get_db),
):
    reset_with_admin_code(
        db,
        email=payload.email,
        recovery_code=payload.recoveryCode,
        new_password=payload.newPassword,
    )
    return {"message": "Password reset successfully. Please sign in with your new password."}


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
        db.flush()
        create_notification(
            db,
            recipient_role="Admin",
            type="OPERATOR_REGISTRATION_REQUEST",
            severity="ACTION_REQUIRED",
            title="New operator registration request",
            message=f"{user.fullName} requested operator access for {department.departmentName}.",
            action_url="/admin/requests",
        )
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
