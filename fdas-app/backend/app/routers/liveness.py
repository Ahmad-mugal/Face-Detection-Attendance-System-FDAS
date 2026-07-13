from fastapi import APIRouter, Depends

from app.dependencies import require_operator_or_admin
from app.schemas.liveness import LivenessInfo
from app.services.liveness import liveness_info


router = APIRouter(prefix="/api/liveness", tags=["liveness"])


@router.get("/info", response_model=LivenessInfo)
def get_liveness_info(_=Depends(require_operator_or_admin)):
    return liveness_info()
