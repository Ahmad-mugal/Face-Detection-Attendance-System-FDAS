from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.classroom import ClassRoom
from app.models.student import Student
from app.models.user import User
from app.services.classes import get_class_or_404
from app.services.departments import ensure_department_access, get_department_or_404


VALID_STUDENT_STATUSES = {"Active", "Inactive", "Disabled"}


def get_student_or_404(db: Session, studentId: int) -> Student:
    student = db.query(Student).filter(Student.studentId == studentId).one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


def ensure_student_access(user: User, student: Student) -> None:
    ensure_department_access(user, student.departmentId)


def scoped_student_query(db: Session, user: User):
    query = db.query(Student)
    role_name = user.role.roleName if user.role else ""
    if role_name == "Admin" or user.accessScope == "AllDepartments":
        return query
    return query.filter(Student.departmentId == user.assignedDepartmentId)


def validate_student_status(status_value: str) -> None:
    if status_value not in VALID_STUDENT_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid student status")


def ensure_unique_roll_no(db: Session, roll_no: str, exclude_student_id: int | None = None) -> None:
    query = db.query(Student).filter(Student.rollNo == roll_no)
    if exclude_student_id is not None:
        query = query.filter(Student.studentId != exclude_student_id)
    if query.one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="rollNo already exists")


def validate_student_department_and_class(db: Session, departmentId: int, classId: int) -> ClassRoom:
    get_department_or_404(db, departmentId)
    classroom = get_class_or_404(db, classId)
    if classroom.departmentId != departmentId:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Class does not belong to department")
    return classroom
