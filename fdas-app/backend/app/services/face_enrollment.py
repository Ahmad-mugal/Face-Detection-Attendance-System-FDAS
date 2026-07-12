from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import BASE_DIR
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.models.user import User
from app.services.students import ensure_student_access, get_student_or_404


ALLOWED_FACE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_FACE_IMAGE_BYTES = 5 * 1024 * 1024
STORAGE_RELATIVE_ROOT = Path("storage") / "face_enrollments"
STORAGE_ABSOLUTE_ROOT = BASE_DIR / STORAGE_RELATIVE_ROOT


def get_face_template_or_404(db: Session, templateId: int) -> FaceTemplate:
    template = db.query(FaceTemplate).filter(FaceTemplate.templateId == templateId).one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Face template not found")
    return template


def ensure_template_access(user: User, template: FaceTemplate) -> None:
    ensure_student_access(user, template.student)


def student_face_registered(student: Student) -> bool:
    return any(template.isActive for template in student.faceTemplates)


def list_active_templates(db: Session, studentId: int) -> list[FaceTemplate]:
    return (
        db.query(FaceTemplate)
        .filter(FaceTemplate.studentId == studentId, FaceTemplate.isActive.is_(True))
        .order_by(FaceTemplate.sampleIndex, FaceTemplate.templateId)
        .all()
    )


def next_sample_index(db: Session, studentId: int) -> int:
    current_max = db.query(func.max(FaceTemplate.sampleIndex)).filter(FaceTemplate.studentId == studentId).scalar()
    return (current_max or 0) + 1


def validate_face_upload_file(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_FACE_IMAGE_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only .jpg, .jpeg, and .png image files are supported",
        )
    return suffix


async def read_face_upload(file: UploadFile) -> tuple[str, bytes]:
    suffix = validate_face_upload_file(file)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")
    if len(content) > MAX_FACE_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded image is larger than the 5 MB limit",
        )
    return suffix, content


def build_sample_path(studentId: int, sample_index: int, suffix: str) -> tuple[Path, Path]:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"sample_{timestamp}_{sample_index:03d}_{uuid4().hex[:8]}{suffix}"
    relative_path = STORAGE_RELATIVE_ROOT / str(studentId) / filename
    absolute_path = BASE_DIR / relative_path
    return relative_path, absolute_path


def create_face_templates(
    db: Session,
    user: User,
    studentId: int,
    uploads: list[tuple[str, bytes]],
) -> list[FaceTemplate]:
    if not uploads:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="At least one image file is required")

    student = get_student_or_404(db, studentId)
    ensure_student_access(user, student)

    sample_index = next_sample_index(db, studentId)
    created_templates: list[FaceTemplate] = []
    for suffix, content in uploads:
        relative_path, absolute_path = build_sample_path(studentId, sample_index, suffix)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content)

        template = FaceTemplate(
            studentId=studentId,
            templatePath=relative_path.as_posix(),
            encodingData=None,
            sampleIndex=sample_index,
            status="Stored",
            isActive=True,
            createdByUserId=user.userId,
        )
        db.add(template)
        created_templates.append(template)
        sample_index += 1

    db.commit()
    for template in created_templates:
        db.refresh(template)
    return created_templates


def deactivate_face_template(db: Session, user: User, templateId: int) -> FaceTemplate:
    template = get_face_template_or_404(db, templateId)
    ensure_template_access(user, template)
    template.isActive = False
    template.status = "Inactive"
    db.commit()
    db.refresh(template)
    return template


def clear_student_face_enrollment(db: Session, user: User, studentId: int) -> int:
    student = get_student_or_404(db, studentId)
    ensure_student_access(user, student)
    active_templates = list_active_templates(db, studentId)
    for template in active_templates:
        template.isActive = False
        template.status = "Inactive"
    db.commit()
    return len(active_templates)
