import json
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import BASE_DIR, FACE_CONTINUITY_MIN_SIMILARITY
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.models.user import User
from app.services.face_processing import descriptor_similarity, load_image_bytes_from_path, process_image_bytes
from app.services.students import ensure_student_access, get_student_or_404
from app.utils.time import utc_now_naive


ALLOWED_FACE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_FACE_IMAGE_BYTES = 5 * 1024 * 1024
FACE_ENROLLMENT_SAMPLE_COUNT = 25
DEEP_RECOVERY_TEMPLATE_STATUS = "DeepRecovery"
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
    active_template_count = sum(
        1
        for template in student.faceTemplates
        if template.isActive and template.status != DEEP_RECOVERY_TEMPLATE_STATUS
    )
    return active_template_count >= FACE_ENROLLMENT_SAMPLE_COUNT


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
    processing_result = process_image_bytes(content)
    ensure_exactly_one_face(processing_result)
    return suffix, content


def ensure_exactly_one_face(processing_result) -> None:
    if processing_result.status == "NoFaceDetected":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "NoFaceDetected",
                "message": "No face detected. Please face the camera.",
            },
        )
    if processing_result.status == "MultipleFacesDetected":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "MultipleFacesDetected",
                "message": "Multiple faces detected. Only one person should be in front of the camera.",
            },
        )
    if processing_result.status != "Encoded" or not processing_result.encodingData:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "InvalidFaceCapture",
                "message": "The face capture could not be processed.",
            },
        )


def ensure_enrollment_face_continuity(processing_results: list) -> None:
    if not processing_results:
        return
    descriptors = [json.loads(result.encodingData) for result in processing_results]
    anchor = descriptors[0]
    previous = descriptors[0]
    for descriptor in descriptors[1:]:
        anchor_similarity = descriptor_similarity(anchor, descriptor)
        adjacent_similarity = descriptor_similarity(previous, descriptor)
        if (
            anchor_similarity < FACE_CONTINUITY_MIN_SIMILARITY
            or adjacent_similarity < FACE_CONTINUITY_MIN_SIMILARITY
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "FaceContinuityLost",
                    "message": "The detected subject changed during enrollment. No samples were stored.",
                },
            )
        previous = descriptor


def build_sample_path(studentId: int, sample_index: int, suffix: str) -> tuple[Path, Path]:
    timestamp = utc_now_naive().strftime("%Y%m%d_%H%M%S_%f")
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
    if len(uploads) != FACE_ENROLLMENT_SAMPLE_COUNT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Exactly {FACE_ENROLLMENT_SAMPLE_COUNT} face samples are required",
        )

    processed_uploads = []
    for suffix, content in uploads:
        processing_result = process_image_bytes(content)
        ensure_exactly_one_face(processing_result)
        processed_uploads.append((suffix, content, processing_result))
    ensure_enrollment_face_continuity([item[2] for item in processed_uploads])

    student = get_student_or_404(db, studentId)
    ensure_student_access(user, student)

    sample_index = next_sample_index(db, studentId)
    created_templates: list[FaceTemplate] = []
    for suffix, content, processing_result in processed_uploads:
        relative_path, absolute_path = build_sample_path(studentId, sample_index, suffix)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content)

        template = FaceTemplate(
            studentId=studentId,
            templatePath=relative_path.as_posix(),
            encodingData=processing_result.encodingData,
            encodingVersion=processing_result.encodingVersion,
            faceBoxJson=processing_result.faceBoxJson,
            sampleIndex=sample_index,
            status=processing_result.status,
            isActive=True,
            createdByUserId=user.userId,
            processedAt=processing_result.processedAt,
        )
        db.add(template)
        created_templates.append(template)
        sample_index += 1

    db.commit()
    for template in created_templates:
        db.refresh(template)
    return created_templates


def has_encoded_templates(student: Student) -> bool:
    return any(template.isActive and template.status == "Encoded" and bool(template.encodingData) for template in student.faceTemplates)


def apply_processing_result(template: FaceTemplate, image_bytes: bytes) -> FaceTemplate:
    processing_result = process_image_bytes(image_bytes)
    template.encodingData = processing_result.encodingData
    template.encodingVersion = processing_result.encodingVersion
    template.faceBoxJson = processing_result.faceBoxJson
    template.status = processing_result.status
    template.processedAt = processing_result.processedAt
    return template


def reprocess_face_template(db: Session, user: User, templateId: int) -> FaceTemplate:
    template = get_face_template_or_404(db, templateId)
    ensure_template_access(user, template)
    if not template.templatePath:
        template.status = "ProcessingFailed"
        db.commit()
        db.refresh(template)
        return template

    image_path = BASE_DIR / Path(template.templatePath)
    try:
        image_bytes = load_image_bytes_from_path(image_path)
        apply_processing_result(template, image_bytes)
    except Exception:
        template.status = "ProcessingFailed"
        template.encodingData = None
        template.encodingVersion = None
        template.faceBoxJson = None
        template.processedAt = utc_now_naive()

    db.commit()
    db.refresh(template)
    return template


def reprocess_student_face_templates(db: Session, user: User, studentId: int) -> dict[str, int]:
    student = get_student_or_404(db, studentId)
    ensure_student_access(user, student)
    templates = list_active_templates(db, studentId)
    counts = {"processed": 0, "noFaceDetected": 0, "failed": 0}
    for template in templates:
        if not template.templatePath:
            template.status = "ProcessingFailed"
            counts["failed"] += 1
            continue
        try:
            image_bytes = load_image_bytes_from_path(BASE_DIR / Path(template.templatePath))
            apply_processing_result(template, image_bytes)
            if template.status == "Encoded":
                counts["processed"] += 1
            elif template.status == "NoFaceDetected":
                counts["noFaceDetected"] += 1
            else:
                counts["failed"] += 1
        except Exception:
            template.status = "ProcessingFailed"
            template.encodingData = None
            template.encodingVersion = None
            template.faceBoxJson = None
            template.processedAt = utc_now_naive()
            counts["failed"] += 1
    db.commit()
    return counts


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
