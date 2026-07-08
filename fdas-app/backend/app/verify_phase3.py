import json
import urllib.error
import urllib.request

from app.database import SessionLocal, init_db
from app.models.department import Department
from app.models.user import User
from app.seed import seed_database
from app.services.access_control import can_access_department


BASE_URL = "http://127.0.0.1:8000"
PENDING_EMAIL = "phase3.pending@fdas.local"
DISABLED_EMAIL = "phase3.disabled@fdas.local"
PHASE3_PASSWORD = "Phase3@12345"


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
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


def login(email: str, password: str) -> tuple[int, dict]:
    return request("POST", "/api/auth/login", {"email": email, "password": password})


def ensure_phase3_test_users() -> int:
    init_db()
    seed_database()
    with SessionLocal() as db:
        departments = db.query(Department).order_by(Department.departmentId).all()
        computer_science = next(dept for dept in departments if dept.departmentName == "Computer Science")

        for email in [PENDING_EMAIL, DISABLED_EMAIL]:
            user = db.query(User).filter(User.email == email).one_or_none()
            if user is not None:
                db.delete(user)
        db.commit()

        return computer_science.departmentId


def verify_department_access() -> tuple[bool, bool, bool, bool]:
    with SessionLocal() as db:
        departments = db.query(Department).order_by(Department.departmentId).all()
        cs_department = next(dept for dept in departments if dept.departmentName == "Computer Science")
        other_department = next(dept for dept in departments if dept.departmentId != cs_department.departmentId)
        admin = db.query(User).filter(User.email == "admin@fdas.local").one()
        operator = db.query(User).filter(User.email == "operator.cs@fdas.local").one()

        admin_access = can_access_department(admin, other_department.departmentId)
        operator.accessScope = "AllDepartments"
        all_departments_access = can_access_department(operator, other_department.departmentId)
        operator.accessScope = "Department"
        operator.assignedDepartmentId = cs_department.departmentId
        department_only_access = can_access_department(operator, cs_department.departmentId)
        department_only_blocked = not can_access_department(operator, other_department.departmentId)
        db.commit()

        return admin_access, all_departments_access, department_only_access, department_only_blocked


def main() -> None:
    cs_department_id = ensure_phase3_test_users()

    health_status, health_body = request("GET", "/health")
    admin_status, admin_body = login("admin@fdas.local", "Admin@12345")
    admin_token = admin_body.get("accessToken")
    wrong_password_status, _ = login("admin@fdas.local", "WrongPassword")

    pending_register_status, pending_body = request(
        "POST",
        "/api/auth/register-request",
        {
            "fullName": "Phase 3 Pending User",
            "email": PENDING_EMAIL,
            "password": PHASE3_PASSWORD,
            "requestedDepartmentId": cs_department_id,
        },
    )
    pending_login_status, _ = login(PENDING_EMAIL, PHASE3_PASSWORD)

    operator_status, operator_body = login("operator.cs@fdas.local", "Operator@12345")
    operator_token = operator_body.get("accessToken")

    me_status, _ = request("GET", "/api/auth/me", token=admin_token)
    me_without_token_status, _ = request("GET", "/api/auth/me")
    admin_without_token_status, _ = request("GET", "/api/admin/users")
    operator_admin_status, _ = request("GET", "/api/admin/users", token=operator_token)
    admin_users_status, _ = request("GET", "/api/admin/users", token=admin_token)
    pending_requests_status, _ = request("GET", "/api/admin/user-requests", token=admin_token)

    pending_user_id = pending_body.get("userId")
    approve_status, _ = request(
        "PATCH",
        f"/api/admin/users/{pending_user_id}/approve",
        {"assignedDepartmentId": cs_department_id, "accessScope": "Department"},
        token=admin_token,
    )
    all_access_status, _ = request(
        "PATCH",
        f"/api/admin/users/{pending_user_id}/access",
        {"assignedDepartmentId": None, "accessScope": "AllDepartments"},
        token=admin_token,
    )
    department_access_status, _ = request(
        "PATCH",
        f"/api/admin/users/{pending_user_id}/access",
        {"assignedDepartmentId": cs_department_id, "accessScope": "Department"},
        token=admin_token,
    )
    disable_status, _ = request("PATCH", f"/api/admin/users/{pending_user_id}/disable", token=admin_token)
    disabled_login_status, _ = login(PENDING_EMAIL, PHASE3_PASSWORD)

    admin_access, all_departments_access, department_only_access, department_only_blocked = verify_department_access()

    results = {
        "health": health_status == 200 and health_body.get("database") == "connected",
        "admin_login": admin_status == 200 and bool(admin_token),
        "wrong_password_rejected": wrong_password_status == 401,
        "pending_register": pending_register_status == 201,
        "pending_user_rejected": pending_login_status == 403,
        "operator_login": operator_status == 200 and bool(operator_token),
        "me_endpoint": me_status == 200,
        "me_without_token_rejected": me_without_token_status == 401,
        "admin_endpoint_protected": admin_without_token_status == 401,
        "operator_admin_blocked": operator_admin_status == 403,
        "admin_list_users": admin_users_status == 200,
        "admin_list_pending_requests": pending_requests_status == 200,
        "approve_user": approve_status == 200,
        "all_departments_access_update": all_access_status == 200,
        "department_access_update": department_access_status == 200,
        "disable_user": disable_status == 200,
        "disabled_user_rejected": disabled_login_status == 403,
        "admin_department_access": admin_access,
        "all_departments_access": all_departments_access,
        "department_only_access": department_only_access,
        "department_only_blocked": department_only_blocked,
    }

    for name, passed in results.items():
        print(f"{name}={passed}")

    if not all(results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
