from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.department import Department
from app.models.user import User
from app.schemas.auth import AccessUpdateRequest, AdminUserListItem, ApprovalNotificationResponse
from app.services.email_service import send_approval_email


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
    _: User = Depends(require_admin),
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
    db.commit()
    db.refresh(user)
    delivery = send_user_approval_notification(user)
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
    return {
        "user": to_admin_user_item(user),
        "emailNotificationSent": delivery.sent,
        "emailNotificationMessage": delivery.message,
    }


@router.patch("/users/{userId}/reject", response_model=AdminUserListItem)
def reject_user(userId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = get_user_or_404(db, userId)
    user.status = "Rejected"
    db.commit()
    db.refresh(user)
    return to_admin_user_item(user)


@router.patch("/users/{userId}/disable", response_model=AdminUserListItem)
def disable_user(userId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = get_user_or_404(db, userId)
    user.status = "Disabled"
    db.commit()
    db.refresh(user)
    return to_admin_user_item(user)


@router.patch("/users/{userId}/enable", response_model=AdminUserListItem)
def enable_user(userId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = get_user_or_404(db, userId)
    user.status = "Approved"
    db.commit()
    db.refresh(user)
    return to_admin_user_item(user)


@router.patch("/users/{userId}/access", response_model=AdminUserListItem)
def update_user_access(
    userId: int,
    payload: AccessUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_access_update(payload, db)
    user = get_user_or_404(db, userId)
    apply_access_update(user, payload)
    db.commit()
    db.refresh(user)
    return to_admin_user_item(user)
