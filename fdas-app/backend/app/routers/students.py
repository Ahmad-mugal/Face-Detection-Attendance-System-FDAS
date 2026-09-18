from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.student import Student
from app.models.user import User
from app.schemas.academic import StudentCreate, StudentRead, StudentUpdate
from app.schemas.student_import import DeleteRecordResponse, StudentImportPreview, StudentImportResult
from app.services.face_enrollment import has_encoded_templates, student_face_registered
from app.services.departments import ensure_department_access
from app.services.students import (
    ensure_student_access,
    ensure_unique_roll_no,
    get_student_or_404,
    scoped_student_query,
    validate_student_department_and_class,
    validate_student_status,
    delete_student_safely,
)
from app.services.student_import import (
    MAX_IMPORT_BYTES,
    STUDENT_IMPORT_FILENAME,
    error_report_csv,
    import_valid_students,
    template_csv,
    validate_student_csv,
    validate_upload_metadata,
)


router = APIRouter(prefix="/api/students", tags=["students"])


async def read_import_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_IMPORT_BYTES + 1)
    validate_upload_metadata(file.filename, file.content_type, content)
    return content


def to_student_read(student: Student) -> StudentRead:
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
        faceRegistered=student_face_registered(student),
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
        normalized_status = status.strip().lower()
        if normalized_status == "active":
            query = query.filter(Student.status == "Active")
        elif normalized_status == "inactive":
            query = query.filter(Student.status.in_(("Inactive", "Disabled")))
        else:
            query = query.filter(Student.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Student.rollNo.ilike(pattern), Student.fullName.ilike(pattern), Student.email.ilike(pattern)))
    students = query.order_by(Student.rollNo).all()
    return [to_student_read(student) for student in students]


@router.get("/import/template")
def download_import_template(_: User = Depends(require_operator_or_admin)):
    return Response(
        content=template_csv().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{STUDENT_IMPORT_FILENAME}"'},
    )


@router.post("/import/validate", response_model=StudentImportPreview)
async def validate_import(
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    content = await read_import_upload(file)
    preview, _ = validate_student_csv(content, current_user, db)
    return preview


@router.post("/import/confirm", response_model=StudentImportResult)
async def confirm_import(
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    content = await read_import_upload(file)
    return import_valid_students(content, current_user, db)


@router.post("/import/error-report")
async def download_import_error_report(
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    content = await read_import_upload(file)
    preview, _ = validate_student_csv(content, current_user, db)
    return Response(
        content=error_report_csv(preview).encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="FDAS_Student_Import_Errors.csv"'},
    )


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


@router.delete("/{studentId}", response_model=DeleteRecordResponse)
def delete_student(
    studentId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    return DeleteRecordResponse(
        deleted=True,
        message=delete_student_safely(db, current_user, studentId),
    )
