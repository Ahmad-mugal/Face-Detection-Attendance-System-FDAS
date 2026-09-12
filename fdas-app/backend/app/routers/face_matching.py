from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.user import User
from app.schemas.face_matching import FaceMatchDiagnosticResult, FaceMatchingInfo, FaceMatchResult, SingleFaceCheckResult
from app.services.face_matching import (
    diagnose_face_bytes,
    match_face_bytes,
    matching_info,
    read_match_upload,
    test_student_face_bytes,
)
from app.services.face_processing import validate_single_face_bytes


router = APIRouter(tags=["face-matching"])


@router.post("/api/face-matching/match", response_model=FaceMatchResult)
async def match_face(
    departmentId: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    image_bytes = await read_match_upload(file)
    return match_face_bytes(db, current_user, departmentId, image_bytes)


@router.post("/api/face-matching/diagnose", response_model=FaceMatchDiagnosticResult)
async def diagnose_face_match(
    departmentId: int = Form(...),
    expectedStudentId: int | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    image_bytes = await read_match_upload(file)
    return diagnose_face_bytes(db, current_user, departmentId, expectedStudentId, image_bytes)


@router.post("/api/face-processing/validate-single-face", response_model=SingleFaceCheckResult)
async def validate_single_face_capture(
    file: UploadFile = File(...),
    referenceFile: UploadFile | None = File(default=None),
    _current_user: User = Depends(require_operator_or_admin),
):
    image_bytes = await read_match_upload(file)
    reference_bytes = await read_match_upload(referenceFile) if referenceFile is not None else None
    return validate_single_face_bytes(image_bytes, reference_bytes)


@router.get("/api/face-matching/info", response_model=FaceMatchingInfo)
def get_face_matching_info(current_user: User = Depends(require_operator_or_admin)):
    return matching_info()


@router.post("/api/students/{studentId}/face-matching/test", response_model=FaceMatchResult)
async def test_student_face_match(
    studentId: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    image_bytes = await read_match_upload(file)
    return test_student_face_bytes(db, current_user, studentId, image_bytes)
