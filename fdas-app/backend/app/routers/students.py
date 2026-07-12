from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.student import Student
from app.models.user import User
from app.schemas.academic import StudentCreate, StudentRead, StudentUpdate
from app.services.face_enrollment import FACE_ENROLLMENT_SAMPLE_COUNT, has_encoded_templates
from app.services.departments import ensure_department_access
from app.services.students import (
    ensure_student_access,
    ensure_unique_roll_no,
    get_student_or_404,
    scoped_student_query,
    validate_student_department_and_class,
    validate_student_status,
)


router = APIRouter(prefix="/api/students", tags=["students"])


def to_student_read(student: Student) -> StudentRead:
    active_template_count = sum(1 for template in student.faceTemplates if getattr(template, "isActive", True))
    return StudentRead(
        studentId=student.studentId,
        rollNo=student.rollNo,
        fullName=student.fullName,
        email=student.email,
        phone=student.phone,
        departmentId=student.departmentId,
        departmentName=student.department.departmentName if student.department else None,
        classId=student.classId,
        className=student.classroom.className if student.classroom else None,
        yearSemester=student.yearSemester,
        section=student.section,
        status=student.status,
        faceRegistered=active_template_count >= FACE_ENROLLMENT_SAMPLE_COUNT,
        hasEncodedFaceTemplates=has_encoded_templates(student),
        createdAt=student.createdAt,
        updatedAt=student.updatedAt,
    )


@router.get("", response_model=list[StudentRead])
def list_students(
    departmentId: int | None = None,
    classId: int | None = None,
    status: str | None = None,
    search: str | None = Query(default=None),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    query = scoped_student_query(db, current_user)
    if departmentId is not None:
        query = query.filter(Student.departmentId == departmentId)
    if classId is not None:
        query = query.filter(Student.classId == classId)
    if status is not None:
        query = query.filter(Student.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Student.rollNo.ilike(pattern), Student.fullName.ilike(pattern), Student.email.ilike(pattern)))
    students = query.order_by(Student.rollNo).all()
    return [to_student_read(student) for student in students]


@router.get("/{studentId}", response_model=StudentRead)
def get_student(studentId: int, current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    student = get_student_or_404(db, studentId)
    ensure_student_access(current_user, student)
    return to_student_read(student)


@router.post("", response_model=StudentRead, status_code=201)
def create_student(payload: StudentCreate, current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    ensure_department_access(current_user, payload.departmentId)
    validate_student_status(payload.status)
    ensure_unique_roll_no(db, payload.rollNo)
    classroom = validate_student_department_and_class(db, payload.departmentId, payload.classId)
    student = Student(
        rollNo=payload.rollNo,
        fullName=payload.fullName,
        email=payload.email,
        phone=payload.phone,
        departmentId=payload.departmentId,
        classId=payload.classId,
        yearSemester=payload.yearSemester or classroom.yearSemester,
        section=payload.section or classroom.section,
        status=payload.status,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return to_student_read(student)


@router.patch("/{studentId}", response_model=StudentRead)
def update_student(
    studentId: int,
    payload: StudentUpdate,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    student = get_student_or_404(db, studentId)
    ensure_student_access(current_user, student)

    target_department_id = payload.departmentId if payload.departmentId is not None else student.departmentId
    target_class_id = payload.classId if payload.classId is not None else student.classId
    ensure_department_access(current_user, target_department_id)
    classroom = validate_student_department_and_class(db, target_department_id, target_class_id)

    if payload.rollNo is not None:
        ensure_unique_roll_no(db, payload.rollNo, studentId)
        student.rollNo = payload.rollNo
    if payload.fullName is not None:
        student.fullName = payload.fullName
    if "email" in payload.model_fields_set:
        student.email = payload.email
    if "phone" in payload.model_fields_set:
        student.phone = payload.phone
    student.departmentId = target_department_id
    student.classId = target_class_id
    if payload.yearSemester is not None:
        student.yearSemester = payload.yearSemester
    elif payload.classId is not None:
        student.yearSemester = classroom.yearSemester
    if payload.section is not None:
        student.section = payload.section
    elif payload.classId is not None:
        student.section = classroom.section
    if payload.status is not None:
        validate_student_status(payload.status)
        student.status = payload.status

    db.commit()
    db.refresh(student)
    return to_student_read(student)


@router.patch("/{studentId}/disable", response_model=StudentRead)
def disable_student(studentId: int, current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    student = get_student_or_404(db, studentId)
    ensure_student_access(current_user, student)
    student.status = "Disabled"
    db.commit()
    db.refresh(student)
    return to_student_read(student)


@router.patch("/{studentId}/enable", response_model=StudentRead)
def enable_student(studentId: int, current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    student = get_student_or_404(db, studentId)
    ensure_student_access(current_user, student)
    student.status = "Active"
    db.commit()
    db.refresh(student)
    return to_student_read(student)
