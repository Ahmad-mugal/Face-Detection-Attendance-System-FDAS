from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.department import Department
from app.models.user import User
from app.services.access_control import can_access_department


VALID_DEPARTMENT_STATUSES = {"Active", "Inactive"}


def get_department_or_404(db: Session, departmentId: int) -> Department:
    department = db.query(Department).filter(Department.departmentId == departmentId).one_or_none()
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


def ensure_department_access(user: User, departmentId: int) -> None:
    if not can_access_department(user, departmentId):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Department access denied")


def scoped_department_query(db: Session, user: User):
    query = db.query(Department)
    role_name = user.role.roleName if user.role else ""
    if role_name == "Admin" or user.accessScope == "AllDepartments":
        return query
    return query.filter(Department.departmentId == user.assignedDepartmentId)


def validate_department_status(status_value: str) -> None:
    if status_value not in VALID_DEPARTMENT_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid department status")


def ensure_unique_department_name(db: Session, department_name: str, exclude_department_id: int | None = None) -> None:
    query = db.query(Department).filter(Department.departmentName == department_name)
    if exclude_department_id is not None:
        query = query.filter(Department.departmentId != exclude_department_id)
    if query.one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department name already exists")
