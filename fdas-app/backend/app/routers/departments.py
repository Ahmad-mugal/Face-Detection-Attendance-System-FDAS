from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_operator_or_admin
from app.models.department import Department
from app.models.user import User
from app.schemas.academic import DepartmentCreate, DepartmentRead, DepartmentUpdate
from app.services.departments import (
    ensure_department_access,
    ensure_unique_department_name,
    get_department_or_404,
    scoped_department_query,
    validate_department_status,
)


router = APIRouter(prefix="/api/departments", tags=["departments"])


def to_department_read(department: Department) -> DepartmentRead:
    return DepartmentRead(
        departmentId=department.departmentId,
        departmentName=department.departmentName,
        status=department.status,
        createdAt=department.createdAt,
        updatedAt=department.updatedAt,
    )


@router.get("", response_model=list[DepartmentRead])
def list_departments(current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    departments = scoped_department_query(db, current_user).order_by(Department.departmentName).all()
    return [to_department_read(department) for department in departments]


@router.get("/{departmentId}", response_model=DepartmentRead)
def get_department(departmentId: int, current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    department = get_department_or_404(db, departmentId)
    ensure_department_access(current_user, department.departmentId)
    return to_department_read(department)


@router.post("", response_model=DepartmentRead, status_code=201)
def create_department(payload: DepartmentCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    validate_department_status(payload.status)
    ensure_unique_department_name(db, payload.departmentName)
    department = Department(departmentName=payload.departmentName, status=payload.status)
    db.add(department)
    db.commit()
    db.refresh(department)
    return to_department_read(department)


@router.patch("/{departmentId}", response_model=DepartmentRead)
def update_department(
    departmentId: int,
    payload: DepartmentUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    department = get_department_or_404(db, departmentId)
    if payload.departmentName is not None:
        ensure_unique_department_name(db, payload.departmentName, departmentId)
        department.departmentName = payload.departmentName
    if payload.status is not None:
        validate_department_status(payload.status)
        department.status = payload.status
    db.commit()
    db.refresh(department)
    return to_department_read(department)


@router.patch("/{departmentId}/disable", response_model=DepartmentRead)
def disable_department(departmentId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    department = get_department_or_404(db, departmentId)
    department.status = "Inactive"
    db.commit()
    db.refresh(department)
    return to_department_read(department)


@router.patch("/{departmentId}/enable", response_model=DepartmentRead)
def enable_department(departmentId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    department = get_department_or_404(db, departmentId)
    department.status = "Active"
    db.commit()
    db.refresh(department)
    return to_department_read(department)
