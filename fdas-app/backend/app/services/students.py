import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.classroom import ClassRoom
from app.models.attendance_record import AttendanceRecord
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.models.user import User
from app.config import BASE_DIR
from app.services.classes import get_class_or_404
from app.services.departments import ensure_department_access, get_department_or_404


STUDENT_FACE_STORAGE_ROOT = BASE_DIR / "storage" / "face_enrollments"


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


def delete_student_safely(
    db: Session,
    current_user: User,
    studentId: int,
    *,
    storage_root: Path = STUDENT_FACE_STORAGE_ROOT,
) -> str:
    student = get_student_or_404(db, studentId)
    ensure_student_access(current_user, student)
    if db.query(AttendanceRecord).filter(AttendanceRecord.studentId == studentId).count():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student has historical records and cannot be permanently deleted. Deactivate the student instead.",
        )

    student_root = (storage_root / str(studentId)).resolve()
    resolved_storage = storage_root.resolve()
    if resolved_storage not in student_root.parents:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Student storage could not be verified safely.")

    templates = db.query(FaceTemplate).filter(FaceTemplate.studentId == studentId).all()
    for template in templates:
        if not template.templatePath:
            continue
        template_path = Path(template.templatePath)
        absolute_path = template_path if template_path.is_absolute() else storage_root.parent.parent / template_path
        resolved_path = absolute_path.resolve()
        if resolved_path != student_root and student_root not in resolved_path.parents:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Student face data has nonstandard storage dependencies and cannot be permanently deleted safely.",
            )

    quarantine = student_root.with_name(f".delete-student-{studentId}-{uuid4().hex}")
    moved_storage = False
    try:
        if student_root.is_dir():
            student_root.rename(quarantine)
            moved_storage = True
        db.query(FaceTemplateEmbedding).filter(FaceTemplateEmbedding.studentId == studentId).delete(synchronize_session=False)
        db.query(FaceTemplate).filter(FaceTemplate.studentId == studentId).delete(synchronize_session=False)
        db.delete(student)
        db.commit()
    except Exception:
        db.rollback()
        if moved_storage and quarantine.exists() and not student_root.exists():
            quarantine.rename(student_root)
        raise

    if moved_storage and quarantine.exists():
        shutil.rmtree(quarantine)
    return "Student permanently deleted."
