from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.user import User
from app.schemas.deep_face import (
    DeepDiagnosticMatchResponse,
    DeepEncodingDryRunResponse,
    DeepFaceInfo,
    DeepRecoverySampleValidation,
)
from app.services.deep_face import deep_face_capability, dry_run_template_encoding, get_deep_face_service
from app.services.deep_face_matching import deep_matching_policy, diagnose_deep_face_bytes
from app.services.face_matching import read_match_upload


router = APIRouter(tags=["deep-face-diagnostics"])


@router.get("/api/deep-face/info", response_model=DeepFaceInfo)
def get_deep_face_info(
    _current_user: User = Depends(require_operator_or_admin),
):
    return {
        **deep_face_capability(initialize=True),
        **deep_matching_policy(),
    }


@router.post(
    "/api/face-templates/{templateId}/deep-encoding/dry-run",
    response_model=DeepEncodingDryRunResponse,
)
def dry_run_deep_encoding(
    templateId: int,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    return dry_run_template_encoding(db, current_user, templateId)


@router.post(
    "/api/deep-face/validate-recovery-sample",
    response_model=DeepRecoverySampleValidation,
)
async def validate_deep_recovery_sample(
    file: UploadFile = File(...),
    _current_user: User = Depends(require_operator_or_admin),
):
    content = await read_match_upload(file)
    result = get_deep_face_service().encode_image_bytes(content)
    return {
        "success": result.success,
        "status": result.status,
        "message": result.message,
        "haarFaceCount": result.haarFaceCount,
        "deepFaceCount": result.deepFaceCount,
        "embeddingDimension": result.embeddingDimension,
        "encodingVersion": "arcface_v1",
        "l2Norm": result.l2Norm,
        "processingMilliseconds": result.processingMilliseconds,
        "persistentWrite": False,
    }


@router.post(
    "/api/deep-face/match/diagnostic",
    response_model=DeepDiagnosticMatchResponse,
)
async def diagnose_deep_match(
    departmentId: int,
    expectedStudentId: int | None = None,
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    content = await read_match_upload(file)
    return diagnose_deep_face_bytes(
        db,
        current_user,
        departmentId,
        expectedStudentId,
        content,
    )
