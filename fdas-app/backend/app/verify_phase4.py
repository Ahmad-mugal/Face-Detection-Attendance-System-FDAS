import json
import urllib.error
import urllib.parse
import urllib.request

from app.database import SessionLocal, init_db
from app.models.attendance_time_window import AttendanceTimeWindow
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.student import Student
from app.seed import seed_database


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"
OPERATOR_EMAIL = "operator.cs@fdas.local"
OPERATOR_PASSWORD = "Operator@12345"


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | list]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def login(email: str, password: str) -> tuple[int, str | None]:
    status, body = request("POST", "/api/auth/login", {"email": email, "password": password})
    if isinstance(body, dict):
        return status, body.get("accessToken")
    return status, None


def seed_and_cleanup() -> tuple[int, int]:
    init_db()
    seed_database()
    with SessionLocal() as db:
        cs = db.query(Department).filter(Department.departmentName == "Computer Science").one()
        it = db.query(Department).filter(Department.departmentName == "IT").one()

        for roll_no in ["P4-ADMIN-001", "P4-OP-CS-001"]:
            student = db.query(Student).filter(Student.rollNo == roll_no).one_or_none()
            if student is not None:
                db.delete(student)

        for class_name in ["Phase 4 Test Class"]:
            classroom = db.query(ClassRoom).filter(ClassRoom.className == class_name).one_or_none()
            if classroom is not None:
                db.delete(classroom)

        department = db.query(Department).filter(Department.departmentName == "Phase 4 Test Department").one_or_none()
        if department is not None:
            db.delete(department)

        for window in db.query(AttendanceTimeWindow).filter(AttendanceTimeWindow.graceMinutes == 17).all():
            db.delete(window)

        db.commit()
        return cs.departmentId, it.departmentId


def main() -> None:
    cs_department_id, it_department_id = seed_and_cleanup()

    health_status, health_body = request("GET", "/health")
    admin_login_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    operator_login_status, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)

    admin_departments_status, admin_departments = request("GET", "/api/departments", token=admin_token)
    operator_departments_status, operator_departments = request("GET", "/api/departments", token=operator_token)
    operator_department_scope = (
        operator_departments_status == 200
        and isinstance(operator_departments, list)
        and len(operator_departments) == 1
        and operator_departments[0]["departmentId"] == cs_department_id
    )

    create_department_status, created_department = request(
        "POST",
        "/api/departments",
        {"departmentName": "Phase 4 Test Department", "status": "Active"},
        token=admin_token,
    )
    created_department_id = created_department.get("departmentId") if isinstance(created_department, dict) else None
    operator_department_create_status, _ = request(
        "POST",
        "/api/departments",
        {"departmentName": "Phase 4 Operator Department", "status": "Active"},
        token=operator_token,
    )

    create_class_status, created_class = request(
        "POST",
        "/api/classes",
        {
            "className": "Phase 4 Test Class",
            "departmentId": cs_department_id,
            "yearSemester": "Semester 6",
            "section": "B",
            "status": "Active",
        },
        token=admin_token,
    )
    created_class_id = created_class.get("classId") if isinstance(created_class, dict) else None
    archive_class_status, archived_class = request("PATCH", f"/api/classes/{created_class_id}/archive", token=admin_token)
    archived_class_still_exists_status, _ = request("GET", f"/api/classes/{created_class_id}", token=admin_token)
    operator_class_archive_status, _ = request("PATCH", f"/api/classes/{created_class_id}/archive", token=operator_token)

    create_student_status, created_student = request(
        "POST",
        "/api/students",
        {
            "rollNo": "P4-ADMIN-001",
            "fullName": "Phase Four Admin Student",
            "email": "p4.admin@example.local",
            "phone": None,
            "departmentId": cs_department_id,
            "classId": created_class_id,
            "status": "Active",
        },
        token=admin_token,
    )
    created_student_id = created_student.get("studentId") if isinstance(created_student, dict) else None

    operator_create_student_status, _ = request(
        "POST",
        "/api/students",
        {
            "rollNo": "P4-OP-CS-001",
            "fullName": "Phase Four Operator Student",
            "departmentId": cs_department_id,
            "classId": created_class_id,
            "status": "Active",
        },
        token=operator_token,
    )
    operator_cross_department_status, _ = request(
        "POST",
        "/api/students",
        {
            "rollNo": "P4-OP-IT-001",
            "fullName": "Phase Four Blocked Student",
            "departmentId": it_department_id,
            "classId": created_class_id,
            "status": "Active",
        },
        token=operator_token,
    )
    duplicate_roll_status, _ = request(
        "POST",
        "/api/students",
        {
            "rollNo": "P4-ADMIN-001",
            "fullName": "Phase Four Duplicate Student",
            "departmentId": cs_department_id,
            "classId": created_class_id,
            "status": "Active",
        },
        token=admin_token,
    )
    update_student_status, updated_student = request(
        "PATCH",
        f"/api/students/{created_student_id}",
        {"fullName": "Phase Four Updated Student"},
        token=admin_token,
    )
    disable_student_status, disabled_student = request("PATCH", f"/api/students/{created_student_id}/disable", token=admin_token)
    enable_student_status, enabled_student = request("PATCH", f"/api/students/{created_student_id}/enable", token=admin_token)

    create_window_status, created_window = request(
        "POST",
        "/api/attendance-time-windows",
        {
            "departmentId": cs_department_id,
            "startTime": "08:30:00",
            "endTime": "09:00:00",
            "graceMinutes": 17,
            "status": "Active",
        },
        token=admin_token,
    )
    operator_window_create_status, _ = request(
        "POST",
        "/api/attendance-time-windows",
        {
            "departmentId": cs_department_id,
            "startTime": "10:30:00",
            "endTime": "11:00:00",
            "graceMinutes": 17,
            "status": "Active",
        },
        token=operator_token,
    )
    operator_windows_status, operator_windows = request("GET", "/api/attendance-time-windows", token=operator_token)
    operator_own_windows_only = (
        operator_windows_status == 200
        and isinstance(operator_windows, list)
        and all(window["departmentId"] == cs_department_id for window in operator_windows)
    )

    class_query = urllib.parse.urlencode({"departmentId": cs_department_id, "search": "Phase 4"})
    student_query = urllib.parse.urlencode({"departmentId": cs_department_id, "search": "Phase Four"})
    filtered_classes_status, filtered_classes = request("GET", f"/api/classes?{class_query}", token=admin_token)
    filtered_students_status, filtered_students = request("GET", f"/api/students?{student_query}", token=admin_token)

    results = {
        "health": health_status == 200 and isinstance(health_body, dict) and health_body.get("database") == "connected",
        "admin_login": admin_login_status == 200 and bool(admin_token),
        "operator_login": operator_login_status == 200 and bool(operator_token),
        "admin_list_departments": admin_departments_status == 200 and isinstance(admin_departments, list) and len(admin_departments) >= 4,
        "operator_department_scope": operator_department_scope,
        "create_department": create_department_status == 201 and bool(created_department_id),
        "operator_department_create_blocked": operator_department_create_status == 403,
        "create_class": create_class_status == 201 and bool(created_class_id),
        "archive_class": archive_class_status == 200 and isinstance(archived_class, dict) and archived_class.get("status") == "Archived",
        "archive_class_not_deleted": archived_class_still_exists_status == 200,
        "operator_class_archive_blocked": operator_class_archive_status == 403,
        "create_student": create_student_status == 201 and bool(created_student_id),
        "operator_create_own_department_student": operator_create_student_status == 201,
        "operator_cross_department_blocked": operator_cross_department_status == 403,
        "roll_no_unique": duplicate_roll_status == 409,
        "update_student": update_student_status == 200 and isinstance(updated_student, dict) and updated_student.get("fullName") == "Phase Four Updated Student",
        "disable_student": disable_student_status == 200 and isinstance(disabled_student, dict) and disabled_student.get("status") == "Disabled",
        "enable_student": enable_student_status == 200 and isinstance(enabled_student, dict) and enabled_student.get("status") == "Active",
        "create_time_window": create_window_status == 201 and isinstance(created_window, dict),
        "operator_own_time_windows_only": operator_own_windows_only,
        "operator_time_window_create_blocked": operator_window_create_status == 403,
        "class_filters": filtered_classes_status == 200 and isinstance(filtered_classes, list) and len(filtered_classes) >= 1,
        "student_filters": filtered_students_status == 200 and isinstance(filtered_students, list) and len(filtered_students) >= 1,
    }
    results["phase4_passed"] = all(results.values())

    for name, passed in results.items():
        print(f"{name}={passed}")

    if not results["phase4_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
