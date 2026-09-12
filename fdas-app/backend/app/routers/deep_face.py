from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.user import User
from app.schemas.deep_face import DeepEncodingDryRunResponse, DeepFaceInfo
from app.services.deep_face import deep_face_capability, dry_run_template_encoding


router = APIRouter(tags=["deep-face-diagnostics"])


@router.get("/api/deep-face/info", response_model=DeepFaceInfo)
def get_deep_face_info(
    _current_user: User = Depends(require_operator_or_admin),
):
    return deep_face_capability(initialize=True)


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
