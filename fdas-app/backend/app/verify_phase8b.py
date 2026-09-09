import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from app.database import SessionLocal, init_db
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.student import Student
from app.seed import seed_database
from app.utils.time import utc_now_naive


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"
OPERATOR_EMAIL = "operator.cs@fdas.local"
OPERATOR_PASSWORD = "Operator@12345"


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | list | str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8")
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.status, json.loads(raw) if raw else {}
            return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw


def login(email: str, password: str) -> tuple[int, str | None]:
    status, body = request("POST", "/api/auth/login", {"email": email, "password": password})
    if isinstance(body, dict):
        return status, body.get("accessToken")
    return status, None


def seed_and_prepare() -> tuple[int, int, int, int, int, int, date]:
    init_db()
    seed_database()
    with SessionLocal() as db:
        cs = db.query(Department).filter(Department.departmentName == "Computer Science").one()
        it = db.query(Department).filter(Department.departmentName == "IT").one()
        cs_class = db.query(ClassRoom).filter(ClassRoom.departmentId == cs.departmentId).order_by(ClassRoom.classId).first()
        it_class = db.query(ClassRoom).filter(ClassRoom.departmentId == it.departmentId).order_by(ClassRoom.classId).first()

        cs_student = db.query(Student).filter(Student.rollNo == "P8B-CS-001").one_or_none()
        if cs_student is None:
            cs_student = Student(
                rollNo="P8B-CS-001",
                fullName="Phase Eight B CS Student",
                email=None,
                phone=None,
                departmentId=cs.departmentId,
                classId=cs_class.classId,
                yearSemester=cs_class.yearSemester,
                section=cs_class.section,
                status="Active",
            )
            db.add(cs_student)
            db.flush()
        else:
            cs_student.departmentId = cs.departmentId
            cs_student.classId = cs_class.classId
            cs_student.status = "Active"

        it_student = db.query(Student).filter(Student.rollNo == "P8B-IT-001").one_or_none()
        if it_student is None:
            it_student = Student(
                rollNo="P8B-IT-001",
                fullName="Phase Eight B IT Student",
                email=None,
                phone=None,
                departmentId=it.departmentId,
                classId=it_class.classId,
                yearSemester=it_class.yearSemester,
                section=it_class.section,
                status="Active",
            )
            db.add(it_student)
            db.flush()
        else:
            it_student.departmentId = it.departmentId
            it_student.classId = it_class.classId
            it_student.status = "Active"

        db.query(AttendanceRecord).filter(AttendanceRecord.studentId.in_([cs_student.studentId, it_student.studentId])).delete(
            synchronize_session=False
        )

        now = utc_now_naive()
        cs_session = AttendanceSession(
            departmentId=cs.departmentId,
            startedByUserId=1,
            scheduledStartTime=now,
            scheduledEndTime=now + timedelta(hours=1),
            actualStartTime=now,
            actualEndTime=now + timedelta(minutes=30),
            status="Closed",
            createdDate=date.today(),
        )
        it_session = AttendanceSession(
            departmentId=it.departmentId,
            startedByUserId=1,
            scheduledStartTime=now,
            scheduledEndTime=now + timedelta(hours=1),
            actualStartTime=now,
            actualEndTime=now + timedelta(minutes=30),
            status="Closed",
            createdDate=date.today(),
        )
        db.add_all([cs_session, it_session])
        db.flush()

        db.add(
            AttendanceRecord(
                sessionId=cs_session.sessionId,
                studentId=cs_student.studentId,
                departmentId=cs.departmentId,
                classId=cs_class.classId,
                markedAt=now,
                status="Present",
                recognitionConfidence=0.91,
                livenessStatus="NotChecked",
            )
        )
        db.add(
            AttendanceRecord(
                sessionId=it_session.sessionId,
                studentId=it_student.studentId,
                departmentId=it.departmentId,
                classId=it_class.classId,
                markedAt=now,
                status="Present",
                recognitionConfidence=0.82,
                livenessStatus="NotChecked",
            )
        )
        db.commit()
        return (
            cs.departmentId,
            it.departmentId,
            cs_class.classId,
            it_class.classId,
            cs_student.studentId,
            it_student.studentId,
            now.date(),
        )


def query_string(params: dict) -> str:
    return urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})


def main() -> None:
    cs_department_id, it_department_id, cs_class_id, _, cs_student_id, it_student_id, record_date = seed_and_prepare()

    health_status, health_body = request("GET", "/health")
    admin_login_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    operator_login_status, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)

    admin_list_status, admin_records = request("GET", "/api/attendance-records", token=admin_token)
    cs_filter_status, cs_records = request(
        "GET",
        f"/api/attendance-records?{query_string({'departmentId': cs_department_id})}",
        token=admin_token,
    )
    combined_filter_status, combined_records = request(
        "GET",
        f"/api/attendance-records?{query_string({'departmentId': cs_department_id, 'classId': cs_class_id, 'studentId': cs_student_id, 'dateFrom': record_date.isoformat(), 'dateTo': record_date.isoformat(), 'status': 'Present'})}",
        token=admin_token,
    )
    summary_status, summary = request(
        "GET",
        f"/api/attendance-records/summary?{query_string({'departmentId': cs_department_id})}",
        token=admin_token,
    )
    csv_status, csv_body = request(
        "GET",
        f"/api/attendance-records/export.csv?{query_string({'departmentId': cs_department_id})}",
        token=admin_token,
    )
    operator_list_status, operator_records = request("GET", "/api/attendance-records", token=operator_token)
    operator_cross_status, _ = request(
        "GET",
        f"/api/attendance-records?{query_string({'departmentId': it_department_id})}",
        token=operator_token,
    )

    admin_record_student_ids = {record.get("studentId") for record in admin_records} if isinstance(admin_records, list) else set()
    operator_department_ids = {record.get("departmentId") for record in operator_records} if isinstance(operator_records, list) else set()

    results = {
        "health": health_status == 200 and isinstance(health_body, dict) and health_body.get("database") == "connected",
        "admin_login": admin_login_status == 200 and bool(admin_token),
        "operator_login": operator_login_status == 200 and bool(operator_token),
        "admin_list_attendance_records": (
            admin_list_status == 200
            and isinstance(admin_records, list)
            and {cs_student_id, it_student_id}.issubset(admin_record_student_ids)
        ),
        "department_filter": (
            cs_filter_status == 200
            and isinstance(cs_records, list)
            and any(record.get("studentId") == cs_student_id for record in cs_records)
            and all(record.get("departmentId") == cs_department_id for record in cs_records)
        ),
        "combined_filters": (
            combined_filter_status == 200
            and isinstance(combined_records, list)
            and len(combined_records) == 1
            and combined_records[0].get("studentId") == cs_student_id
        ),
        "summary_endpoint": (
            summary_status == 200
            and isinstance(summary, dict)
            and summary.get("totalRecords", 0) >= 1
            and summary.get("presentCount", 0) >= 1
            and summary.get("uniqueStudentsMarked", 0) >= 1
            and summary.get("averageRecognitionConfidence") is not None
        ),
        "csv_export": (
            csv_status == 200
            and isinstance(csv_body, str)
            and "attendanceRecordId" in csv_body
            and "Phase Eight B CS Student" in csv_body
        ),
        "operator_department_scope": (
            operator_list_status == 200
            and isinstance(operator_records, list)
            and operator_department_ids
            and operator_department_ids == {cs_department_id}
        ),
        "operator_cross_department_blocked": operator_cross_status == 403,
    }
    results["phase8b_passed"] = all(results.values())

    for name, passed in results.items():
        print(f"{name}={passed}")

    if not results["phase8b_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
