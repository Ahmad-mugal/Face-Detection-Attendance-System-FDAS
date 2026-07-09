from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.user import User
from app.services.departments import ensure_department_access, get_department_or_404


VALID_CLASS_STATUSES = {"Active", "Inactive", "Archived"}


def get_class_or_404(db: Session, classId: int) -> ClassRoom:
    classroom = db.query(ClassRoom).filter(ClassRoom.classId == classId).one_or_none()
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    return classroom


def ensure_class_access(user: User, classroom: ClassRoom) -> None:
    ensure_department_access(user, classroom.departmentId)


def scoped_class_query(db: Session, user: User):
    query = db.query(ClassRoom)
    role_name = user.role.roleName if user.role else ""
    if role_name == "Admin" or user.accessScope == "AllDepartments":
        return query
    return query.filter(ClassRoom.departmentId == user.assignedDepartmentId)


def validate_class_status(status_value: str) -> None:
    if status_value not in VALID_CLASS_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid class status")


def validate_class_department(db: Session, departmentId: int) -> Department:
    return get_department_or_404(db, departmentId)
