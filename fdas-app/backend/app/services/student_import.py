from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.student import Student
from app.models.user import User
from app.services.access_control import can_access_department
from app.services.notifications import create_notification


STUDENT_IMPORT_HEADERS = ["Name", "Email", "Roll Number", "Department", "Class"]
STUDENT_IMPORT_FILENAME = "FDAS_Student_Import_Template.csv"
MAX_IMPORT_BYTES = 1_000_000
MAX_IMPORT_ROWS = 500
UNSAFE_FORMULA_PREFIXES = ("=", "+", "-", "@")


@dataclass
class ValidatedImportRow:
    row_number: int
    name: str
    email: str
    roll_no: str
    department_name: str
    class_name: str
    status: str
    issues: list[str]
    department_id: int | None = None
    class_id: int | None = None
    year_semester: str | None = None
    section: str | None = None

    def public(self) -> dict:
        return {
            "rowNumber": self.row_number,
            "name": self.name,
            "email": self.email,
            "rollNo": self.roll_no,
            "department": self.department_name,
            "className": self.class_name,
            "status": self.status,
            "issues": self.issues,
        }


def template_csv() -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(STUDENT_IMPORT_HEADERS)
    return buffer.getvalue()


def validate_upload_metadata(filename: str | None, content_type: str | None, content: bytes) -> None:
    if not filename or not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Upload a .csv file.")
    allowed_types = {"text/csv", "application/csv", "application/vnd.ms-excel", "application/octet-stream", "text/plain", ""}
    if (content_type or "").split(";", 1)[0].lower() not in allowed_types:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported CSV content type.")
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="CSV file is empty.")
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="CSV file exceeds the 1 MB limit.")


def _decode_csv(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CSV must be saved as UTF-8 or UTF-8 with BOM.",
        ) from exc


def _unsafe_formula(value: str) -> bool:
    return value.lstrip().startswith(UNSAFE_FORMULA_PREFIXES)


def _valid_email(value: str) -> bool:
    if len(value) > 180 or "@" not in value:
        return False
    local, _, domain = value.partition("@")
    return bool(local and "." in domain and not any(character.isspace() for character in value))


def validate_student_csv(content: bytes, current_user: User, db: Session) -> tuple[dict, list[ValidatedImportRow]]:
    decoded = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(decoded, newline=""))
    actual_headers = [header.strip() for header in (reader.fieldnames or [])]
    if actual_headers != STUDENT_IMPORT_HEADERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"CSV headers must be exactly: {', '.join(STUDENT_IMPORT_HEADERS)}",
        )

    raw_rows = list(reader)
    if len(raw_rows) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"CSV contains more than the {MAX_IMPORT_ROWS}-row limit.",
        )

    departments = db.query(Department).all()
    departments_by_name = {item.departmentName.casefold(): item for item in departments}
    classes = db.query(ClassRoom).all()
    classes_by_scope: dict[tuple[int, str], list[ClassRoom]] = {}
    for classroom in classes:
        classes_by_scope.setdefault((classroom.departmentId, classroom.className.casefold()), []).append(classroom)

    existing_emails = {
        value.casefold()
        for (value,) in db.query(Student.email).filter(Student.email.is_not(None)).all()
        if value
    }
    existing_rolls = {value.casefold() for (value,) in db.query(Student.rollNo).all()}
    seen_emails: set[str] = set()
    seen_rolls: set[str] = set()
    validated: list[ValidatedImportRow] = []

    for row_number, raw in enumerate(raw_rows, start=2):
        values = {header: (raw.get(header) or "").strip() for header in STUDENT_IMPORT_HEADERS}
        name = values["Name"]
        email = values["Email"].lower()
        roll_no = values["Roll Number"]
        department_name = values["Department"]
        class_name = values["Class"]
        issues: list[str] = []
        row_status = "Ready"

        if not any(values.values()):
            issues.append("Blank row")
        if not 2 <= len(name) <= 150:
            issues.append("Name must contain 2 to 150 characters")
        if not _valid_email(email):
            issues.append("Invalid email address")
        if not 1 <= len(roll_no) <= 80:
            issues.append("Roll Number is required and must not exceed 80 characters")
        if any(_unsafe_formula(value) for value in values.values() if value):
            issues.append("Unsafe spreadsheet formula value")

        department = departments_by_name.get(department_name.casefold())
        classroom = None
        if department is None:
            issues.append("Unknown Department")
        else:
            if not can_access_department(current_user, department.departmentId):
                issues.append("Unauthorized Department")
            class_matches = classes_by_scope.get((department.departmentId, class_name.casefold()), [])
            if not class_matches:
                same_name_elsewhere = any(item.className.casefold() == class_name.casefold() for item in classes)
                issues.append("Class does not belong to Department" if same_name_elsewhere else "Unknown Class")
            elif len(class_matches) > 1:
                issues.append("Class name is ambiguous within Department")
            else:
                classroom = class_matches[0]

        email_key = email.casefold()
        roll_key = roll_no.casefold()
        if not issues and (email_key in seen_emails or roll_key in seen_rolls):
            row_status = "Duplicate"
            if email_key in seen_emails:
                issues.append("Duplicate Email within CSV")
            if roll_key in seen_rolls:
                issues.append("Duplicate Roll Number within CSV")
        elif not issues and (email_key in existing_emails or roll_key in existing_rolls):
            row_status = "Existing"
            if email_key in existing_emails:
                issues.append("Email already exists")
            if roll_key in existing_rolls:
                issues.append("Roll Number already exists")
        elif issues:
            row_status = "Invalid"

        if email:
            seen_emails.add(email_key)
        if roll_no:
            seen_rolls.add(roll_key)

        validated.append(ValidatedImportRow(
            row_number=row_number,
            name=name,
            email=email,
            roll_no=roll_no,
            department_name=department_name,
            class_name=class_name,
            status=row_status,
            issues=issues,
            department_id=department.departmentId if department else None,
            class_id=classroom.classId if classroom else None,
            year_semester=classroom.yearSemester if classroom else None,
            section=classroom.section if classroom else None,
        ))

    preview = {
        "headers": STUDENT_IMPORT_HEADERS,
        "totalRows": len(validated),
        "validRows": sum(row.status == "Ready" for row in validated),
        "invalidRows": sum(row.status == "Invalid" for row in validated),
        "duplicateRows": sum(row.status == "Duplicate" for row in validated),
        "existingRows": sum(row.status == "Existing" for row in validated),
        "rows": [row.public() for row in validated],
    }
    return preview, validated


def import_valid_students(content: bytes, current_user: User, db: Session) -> dict:
    preview, rows = validate_student_csv(content, current_user, db)
    ready = [row for row in rows if row.status == "Ready"]
    students: list[Student] = []
    try:
        for row in ready:
            student = Student(
                rollNo=row.roll_no,
                fullName=row.name,
                email=row.email,
                phone=None,
                departmentId=row.department_id,
                classId=row.class_id,
                yearSemester=row.year_semester or "",
                section=row.section or "",
                status="Active",
            )
            db.add(student)
            students.append(student)
        db.flush()
        create_notification(
            db,
            recipient_user_id=current_user.userId,
            type="STUDENT_IMPORT_COMPLETED",
            severity="WARNING" if preview["invalidRows"] or preview["duplicateRows"] or preview["existingRows"] else "SUCCESS",
            title="Student import completed",
            message=(
                f"Student import completed: {len(students)} imported, "
                f"{preview['invalidRows'] + preview['duplicateRows'] + preview['existingRows']} skipped."
            ),
            action_url="/admin/students" if current_user.role and current_user.role.roleName == "Admin" else "/user/students",
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Import changed during confirmation. Review the CSV again; no students were imported.",
        ) from exc
    except Exception:
        db.rollback()
        raise

    for student in students:
        db.refresh(student)
    return {
        "imported": len(students),
        "skippedInvalid": preview["invalidRows"],
        "skippedDuplicates": preview["duplicateRows"],
        "skippedExisting": preview["existingRows"],
        "students": [
            {
                "studentId": student.studentId,
                "fullName": student.fullName,
                "email": student.email,
                "rollNo": student.rollNo,
                "departmentName": row.department_name,
                "className": row.class_name,
                "faceStatus": "Pending Face Registration",
            }
            for student, row in zip(students, ready, strict=True)
        ],
        "message": "Students imported successfully.",
    }


def safe_csv_cell(value: str) -> str:
    return f"'{value}" if value.lstrip().startswith(UNSAFE_FORMULA_PREFIXES) else value


def error_report_csv(preview: dict) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["Row", *STUDENT_IMPORT_HEADERS, "Status", "Issue"])
    for row in preview["rows"]:
        if row["status"] == "Ready":
            continue
        writer.writerow([
            row["rowNumber"],
            safe_csv_cell(row["name"]),
            safe_csv_cell(row["email"]),
            safe_csv_cell(row["rollNo"]),
            safe_csv_cell(row["department"]),
            safe_csv_cell(row["className"]),
            row["status"],
            "; ".join(row["issues"]),
        ])
    return buffer.getvalue()
