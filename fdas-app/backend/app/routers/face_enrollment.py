from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.face_template import FaceTemplate
from app.models.user import User
from app.schemas.face_enrollment import (
    FaceEnrollmentClearResponse,
    FaceEnrollmentListResponse,
    FaceEnrollmentProcessAllResponse,
    FaceEnrollmentUploadResponse,
    FaceProcessingInfo,
    FaceTemplateRead,
    FaceTemplateProcessResponse,
)
from app.services.face_enrollment import (
    clear_student_face_enrollment,
    create_face_templates,
    deactivate_face_template,
    ensure_template_access,
    get_face_template_or_404,
    has_encoded_templates,
    list_active_templates,
    read_face_upload,
    reprocess_face_template,
    reprocess_student_face_templates,
    student_face_registered,
)
from app.services.face_processing import processing_info
from app.services.students import ensure_student_access, get_student_or_404


router = APIRouter(tags=["face-enrollment"])


def to_face_template_read(template: FaceTemplate) -> FaceTemplateRead:
    return FaceTemplateRead(
        templateId=template.templateId,
        studentId=template.studentId,
        templatePath=template.templatePath,
        encodingVersion=template.encodingVersion,
        faceBoxJson=template.faceBoxJson,
        hasEncodingData=bool(template.encodingData),
        sampleIndex=template.sampleIndex,
        status=template.status,
        isActive=template.isActive,
        processedAt=template.processedAt,
        createdAt=template.createdAt,
        updatedAt=template.updatedAt,
        createdByUserId=template.createdByUserId,
    )


@router.post(
    "/api/students/{studentId}/face-enrollment/upload",
    response_model=FaceEnrollmentUploadResponse,
    status_code=201,
)
async def upload_face_enrollment(
    studentId: int,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    uploads = [await read_face_upload(file) for file in files]
    templates = create_face_templates(db, current_user, studentId, uploads)
    student = get_student_or_404(db, studentId)
    return FaceEnrollmentUploadResponse(
        studentId=studentId,
        faceRegistered=student_face_registered(student),
        hasEncodedTemplates=has_encoded_templates(student),
        uploadedSamples=[to_face_template_read(template) for template in templates],
    )


@router.get("/api/students/{studentId}/face-enrollment", response_model=FaceEnrollmentListResponse)
def list_student_face_enrollment(
    studentId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    student = get_student_or_404(db, studentId)
    ensure_student_access(current_user, student)
    templates = list_active_templates(db, studentId)
    return FaceEnrollmentListResponse(
        studentId=studentId,
        faceRegistered=bool(templates),
        hasEncodedTemplates=any(template.status == "Encoded" and bool(template.encodingData) for template in templates),
        templates=[to_face_template_read(template) for template in templates],
    )


@router.patch("/api/face-templates/{templateId}/deactivate", response_model=FaceTemplateRead)
def deactivate_template(
    templateId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    template = deactivate_face_template(db, current_user, templateId)
    return to_face_template_read(template)


@router.patch("/api/students/{studentId}/face-enrollment/clear", response_model=FaceEnrollmentClearResponse)
def clear_face_enrollment(
    studentId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    deactivated_count = clear_student_face_enrollment(db, current_user, studentId)
    return FaceEnrollmentClearResponse(
        studentId=studentId,
        deactivatedCount=deactivated_count,
        faceRegistered=False,
        hasEncodedTemplates=False,
    )


@router.get("/api/face-templates/{templateId}", response_model=FaceTemplateRead)
def get_face_template(
    templateId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    template = get_face_template_or_404(db, templateId)
    ensure_template_access(current_user, template)
    return to_face_template_read(template)


@router.post("/api/face-templates/{templateId}/process", response_model=FaceTemplateProcessResponse)
def process_face_template(
    templateId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    template = reprocess_face_template(db, current_user, templateId)
    return FaceTemplateProcessResponse(
        template=to_face_template_read(template),
        processingSucceeded=template.status == "Encoded" and bool(template.encodingData),
        noFaceDetected=template.status == "NoFaceDetected",
    )


@router.post("/api/students/{studentId}/face-enrollment/process-all", response_model=FaceEnrollmentProcessAllResponse)
def process_student_face_enrollment(
    studentId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    counts = reprocess_student_face_templates(db, current_user, studentId)
    return FaceEnrollmentProcessAllResponse(studentId=studentId, **counts)


@router.get("/api/face-processing/info", response_model=FaceProcessingInfo)
def get_face_processing_info(current_user: User = Depends(require_operator_or_admin)):
    return processing_info()
