from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin, require_operator_or_admin
from app.models.classroom import ClassRoom
from app.models.user import User
from app.schemas.academic import ClassRoomCreate, ClassRoomRead, ClassRoomUpdate
from app.services.classes import (
    ensure_class_access,
    get_class_or_404,
    scoped_class_query,
    validate_class_department,
    validate_class_status,
)


router = APIRouter(prefix="/api/classes", tags=["classes"])


def to_class_read(classroom: ClassRoom) -> ClassRoomRead:
    return ClassRoomRead(
        classId=classroom.classId,
        className=classroom.className,
        departmentId=classroom.departmentId,
        departmentName=classroom.department.departmentName if classroom.department else None,
        yearSemester=classroom.yearSemester,
        section=classroom.section,
        status=classroom.status,
        createdAt=classroom.createdAt,
        updatedAt=classroom.updatedAt,
    )


@router.get("", response_model=list[ClassRoomRead])
def list_classes(
    departmentId: int | None = None,
    status: str | None = None,
    search: str | None = Query(default=None),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    query = scoped_class_query(db, current_user)
    if departmentId is not None:
        query = query.filter(ClassRoom.departmentId == departmentId)
    if status is not None:
        query = query.filter(ClassRoom.status == status)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(ClassRoom.className.ilike(pattern), ClassRoom.yearSemester.ilike(pattern), ClassRoom.section.ilike(pattern)))
    classes = query.order_by(ClassRoom.className).all()
    return [to_class_read(classroom) for classroom in classes]


@router.get("/{classId}", response_model=ClassRoomRead)
def get_class(classId: int, current_user: User = Depends(require_operator_or_admin), db: Session = Depends(get_db)):
    classroom = get_class_or_404(db, classId)
    ensure_class_access(current_user, classroom)
    return to_class_read(classroom)


@router.post("", response_model=ClassRoomRead, status_code=201)
def create_class(payload: ClassRoomCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    validate_class_status(payload.status)
    validate_class_department(db, payload.departmentId)
    classroom = ClassRoom(
        className=payload.className,
        departmentId=payload.departmentId,
        yearSemester=payload.yearSemester,
        section=payload.section,
        status=payload.status,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return to_class_read(classroom)


@router.patch("/{classId}", response_model=ClassRoomRead)
def update_class(
    classId: int,
    payload: ClassRoomUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    classroom = get_class_or_404(db, classId)
    if payload.className is not None:
        classroom.className = payload.className
    if payload.departmentId is not None:
        validate_class_department(db, payload.departmentId)
        classroom.departmentId = payload.departmentId
    if payload.yearSemester is not None:
        classroom.yearSemester = payload.yearSemester
    if payload.section is not None:
        classroom.section = payload.section
    if payload.status is not None:
        validate_class_status(payload.status)
        classroom.status = payload.status
    db.commit()
    db.refresh(classroom)
    return to_class_read(classroom)


@router.patch("/{classId}/archive", response_model=ClassRoomRead)
def archive_class(classId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    classroom = get_class_or_404(db, classId)
    classroom.status = "Archived"
    db.commit()
    db.refresh(classroom)
    return to_class_read(classroom)


@router.patch("/{classId}/activate", response_model=ClassRoomRead)
def activate_class(classId: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    classroom = get_class_or_404(db, classId)
    classroom.status = "Active"
    db.commit()
    db.refresh(classroom)
    return to_class_read(classroom)
