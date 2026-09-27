from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.department import Department
from app.models.attendance_session import AttendanceSession
from app.models.face_template import FaceTemplate
from app.models.notification import Notification
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from app.schemas.auth import AccessUpdateRequest, AdminRecoveryCodeResponse, AdminUserListItem, ApprovalNotificationResponse, DeleteUserResponse, EmailCapabilityResponse
from app.services.email_service import get_email_capability, send_approval_email
from app.services.notifications import create_notification
from app.services.password_recovery import issue_admin_code


router = APIRouter(prefix="/api/admin", tags=["admin-users"])


def to_admin_user_item(user: User) -> AdminUserListItem:
    return AdminUserListItem(
        userId=user.userId,
        fullName=user.fullName,
        email=user.email,
        role=user.role.roleName,
        status=user.status,
        assignedDepartment=user.assignedDepartment.departmentName if user.assignedDepartment else None,
        assignedDepartmentId=user.assignedDepartmentId,
        accessScope=user.accessScope,
        createdAt=user.createdAt,
        updatedAt=user.updatedAt,
    )


def get_user_or_404(db: Session, userId: int) -> User:
    user = db.query(User).filter(User.userId == userId).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def validate_access_update(payload: AccessUpdateRequest, db: Session) -> None:
    if payload.accessScope not in {"Department", "AllDepartments"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid accessScope")
    if payload.accessScope == "Department":
        if payload.assignedDepartmentId is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="assignedDepartmentId is required for Department access",
            )
        department = db.query(Department).filter(Department.departmentId == payload.assignedDepartmentId).one_or_none()
        if department is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")


def apply_access_update(user: User, payload: AccessUpdateRequest) -> None:
    user.accessScope = payload.accessScope
    user.assignedDepartmentId = payload.assignedDepartmentId if payload.accessScope == "Department" else None


@router.get("/users", response_model=list[AdminUserListItem])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.createdAt.desc(), User.userId.desc()).all()
    return [to_admin_user_item(user) for user in users]


@router.get("/user-requests", response_model=list[AdminUserListItem])
def list_user_requests(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).filter(User.status == "Pending").order_by(User.createdAt.desc()).all()
    return [to_admin_user_item(user) for user in users]


@router.get("/email-status", response_model=EmailCapabilityResponse)
def email_status(_: User = Depends(require_admin)):
    return get_email_capability()


def send_user_approval_notification(user: User):
    department_name = user.assignedDepartment.departmentName if user.assignedDepartment else None
    return send_approval_email(
        operator_name=user.fullName,
        recipient_email=user.email,
        department_name=department_name,
    )


@router.patch("/users/{userId}/approve", response_model=ApprovalNotificationResponse)
def approve_user(
    userId: int,
    payload: AccessUpdateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_access_update(payload, db)
    user = get_user_or_404(db, userId)
    if user.status == "Approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already approved. Use Resend Approval Email if another notification is needed.",
        )
    if user.status != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending user requests can be approved.",
        )
    user.status = "Approved"
    apply_access_update(user, payload)
    create_notification(
        db,
        recipient_user_id=user.userId,
        type="ACCOUNT_APPROVED",
        severity="SUCCESS",
        title="Account approved",
        message="Your FDAS account was approved. Review your assigned access scope before beginning work.",
        action_url="/account/profile",
    )
    db.commit()
    db.refresh(user)
    delivery = send_user_approval_notification(user)
    create_notification(
        db,
        recipient_role="Admin",
        type="OPERATOR_APPROVED" if delivery.sent else "APPROVAL_EMAIL_FAILED",
        severity="SUCCESS" if delivery.sent else "ACTION_REQUIRED",
        title="Operator account approved" if delivery.sent else "Approval email failed",
        message=(
            f"{user.fullName} was approved by {current_admin.fullName}."
            if delivery.sent
            else f"{user.fullName} was approved, but the approval email could not be delivered."
        ),
        action_url="/admin/users",
        commit=True,
    )
    return {
        "user": to_admin_user_item(user),
        "emailNotificationSent": delivery.sent,
        "emailNotificationMessage": delivery.message,
    }


@router.post("/users/{userId}/resend-approval-email", response_model=ApprovalNotificationResponse)
def resend_approval_email(
    userId: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, userId)
    if user.status != "Approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval email can only be sent to an approved account.",
        )
    if not user.role or user.role.roleName != "User":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval email is available only for approved operator accounts.",
        )

    delivery = send_user_approval_notification(user)
    if not delivery.sent:
        create_notification(
            db,
            recipient_role="Admin",
            type="APPROVAL_EMAIL_FAILED",
            severity="ACTION_REQUIRED",
            title="Approval email failed",
            message=f"The approval email for {user.fullName} could not be delivered.",
            action_url="/admin/users",
            commit=True,
        )
    return {
        "user": to_admin_user_item(user),
        "emailNotificationSent": delivery.sent,
        "emailNotificationMessage": delivery.message,
    }


@router.patch("/users/{userId}/reject", response_model=AdminUserListItem)
def reject_user(userId: int, current_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = get_user_or_404(db, userId)
    user.status = "Rejected"
    create_notification(
        db,
        recipient_role="Admin",
        type="OPERATOR_REJECTED",
        severity="INFO",
        title="Operator request rejected",
        message=f"{user.fullName}'s account request was rejected by {current_admin.fullName}.",
        action_url="/admin/requests",
    )
    db.commit()
    db.refresh(user)
    return to_admin_user_item(user)


@router.patch("/users/{userId}/disable", response_model=AdminUserListItem)
def disable_user(userId: int, current_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = get_user_or_404(db, userId)
    if user.userId == current_admin.userId:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot disable your own active administrator account.")
    user.status = "Disabled"
    create_notification(
        db,
        recipient_user_id=user.userId,
        type="ACCOUNT_DISABLED",
        severity="WARNING",
        title="Account disabled",
        message="Your FDAS account was disabled by an administrator. Contact an administrator if access is still required.",
        action_url="/account/profile",
    )
    db.commit()
    db.refresh(user)
    return to_admin_user_item(user)


@router.patch("/users/{userId}/enable", response_model=AdminUserListItem)
def enable_user(userId: int, current_admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = get_user_or_404(db, userId)
    user.status = "Approved"
    create_notification(
        db,
        recipient_user_id=user.userId,
        type="ACCOUNT_ENABLED",
        severity="SUCCESS",
        title="Account enabled",
        message=f"Your FDAS account was enabled by {current_admin.fullName}.",
        action_url="/account/profile",
    )
    db.commit()
    db.refresh(user)
    return to_admin_user_item(user)


@router.patch("/users/{userId}/access", response_model=AdminUserListItem)
def update_user_access(
    userId: int,
    payload: AccessUpdateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_access_update(payload, db)
    user = get_user_or_404(db, userId)
    apply_access_update(user, payload)
    scope_label = (
        "All Departments"
        if payload.accessScope == "AllDepartments"
        else db.get(Department, payload.assignedDepartmentId).departmentName
    )
    create_notification(
        db,
        recipient_user_id=user.userId,
        type="ACCESS_SCOPE_CHANGED",
        severity="ACTION_REQUIRED",
        title="Access scope changed",
        message=f"Your FDAS access scope was changed to {scope_label} by {current_admin.fullName}.",
        action_url="/account/profile",
    )
    db.commit()
    db.refresh(user)
    return to_admin_user_item(user)


@router.post("/users/{userId}/password-recovery-code", response_model=AdminRecoveryCodeResponse)
def generate_password_recovery_code(
    userId: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, userId)
    recovery_code, credential = issue_admin_code(db, user, current_admin)
    create_notification(
        db,
        recipient_user_id=user.userId,
        type="ADMIN_PASSWORD_RECOVERY_ISSUED",
        severity="ACTION_REQUIRED",
        title="Administrator-assisted password recovery initiated",
        message="An administrator generated a short-lived recovery code for your account. Contact administration if you did not request assistance.",
        action_url="/login",
    )
    db.commit()
    return {
        "recoveryCode": recovery_code,
        "expiresAt": credential.expiresAt,
        "message": "Recovery code generated. It will be shown only in this response and expires in 10 minutes.",
    }


@router.delete("/users/{userId}", response_model=DeleteUserResponse)
def delete_user(
    userId: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, userId)
    if user.userId == current_admin.userId:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot delete your own currently signed-in account.")
    if user.role and user.role.roleName == "Admin":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrator accounts are protected and cannot be permanently deleted.")
    has_sessions = db.query(AttendanceSession).filter(AttendanceSession.startedByUserId == userId).count() > 0
    has_templates = db.query(FaceTemplate).filter(FaceTemplate.createdByUserId == userId).count() > 0
    if has_sessions or has_templates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user has historical dependencies and cannot be permanently deleted. Disable the account instead.",
        )

    display_name = user.fullName
    db.query(Notification).filter(Notification.recipientUserId == userId).delete(synchronize_session=False)
    db.query(PasswordResetToken).filter(PasswordResetToken.userId == userId).delete(synchronize_session=False)
    db.delete(user)
    create_notification(
        db,
        recipient_role="Admin",
        type="USER_DELETED",
        severity="WARNING",
        title="User permanently deleted",
        message=f"{display_name} was permanently deleted by {current_admin.fullName}.",
        action_url="/admin/users",
    )
    db.commit()
    return DeleteUserResponse(deleted=True, message="User permanently deleted.")
