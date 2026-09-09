from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_operator_or_admin
from app.models.user import User
from app.schemas.attendance_records import AttendanceRecordRead, AttendanceRecordsSummary
from app.services.attendance_records import (
    attendance_record_to_dict,
    list_attendance_records,
    records_to_csv,
    summarize_attendance_records,
)


router = APIRouter(prefix="/api/attendance-records", tags=["attendance-records"])


def filter_params(
    departmentId: int | None = Query(default=None),
    classId: int | None = Query(default=None),
    studentId: int | None = Query(default=None),
    dateFrom: date | None = Query(default=None),
    dateTo: date | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    return {
        "departmentId": departmentId,
        "classId": classId,
        "studentId": studentId,
        "dateFrom": dateFrom,
        "dateTo": dateTo,
        "statusValue": status,
    }


@router.get("", response_model=list[AttendanceRecordRead])
def get_attendance_records(
    filters: dict = Depends(filter_params),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    records = list_attendance_records(db, current_user, **filters)
    return [AttendanceRecordRead(**attendance_record_to_dict(record)) for record in records]


@router.get("/summary", response_model=AttendanceRecordsSummary)
def get_attendance_records_summary(
    filters: dict = Depends(filter_params),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    return summarize_attendance_records(db, current_user, **filters)


@router.get("/export.csv")
def export_attendance_records_csv(
    filters: dict = Depends(filter_params),
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db),
):
    records = list_attendance_records(db, current_user, **filters)
    return Response(
        content=records_to_csv(records),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="fdas_attendance_records.csv"'},
    )
