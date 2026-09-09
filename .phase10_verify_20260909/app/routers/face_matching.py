from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.user import User
from app.schemas.face_matching import FaceMatchingInfo, FaceMatchResult
from app.services.face_matching import (
    match_face_bytes,
    matching_info,
    read_match_upload,
    test_student_face_bytes,
)


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
