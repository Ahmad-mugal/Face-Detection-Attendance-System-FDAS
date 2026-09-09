import json
import urllib.error
import urllib.request

from app.database import SessionLocal, init_db
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.seed import seed_database
from app.utils.security import hash_password, verify_password


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"
OPERATOR_EMAIL = "operator.cs@fdas.local"
OPERATOR_PASSWORD = "Operator@12345"
VALID_EMAIL = "phase10.4.valid@fdas.local"
DISABLED_EMAIL = "phase10.4.disabled@fdas.local"
VALID_PASSWORD = "Valid@12345"
DUPLICATE_MESSAGE = "An account with this email already exists."


def request(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
) -> tuple[int, dict | list | str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            raw = response.read().decode("utf-8")
            if "application/json" in response.headers.get("Content-Type", ""):
                return response.status, json.loads(raw) if raw else {}
            return response.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw


def login(email: str, password: str) -> tuple[int, dict | list | str, str | None]:
    status_code, body = request("POST", "/api/auth/login", {"email": email, "password": password})
    token = body.get("accessToken") if status_code == 200 and isinstance(body, dict) else None
    return status_code, body, token


def remove_test_users() -> None:
    db = SessionLocal()
    try:
        db.query(User).filter(User.email.in_([VALID_EMAIL, DISABLED_EMAIL])).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def create_disabled_user(department_id: int) -> None:
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.roleName == "User").one()
        db.add(
            User(
                fullName="Phase Ten Four Disabled",
                email=DISABLED_EMAIL,
                passwordHash=hash_password(VALID_PASSWORD),
                roleId=role.roleId,
                status="Disabled",
                assignedDepartmentId=department_id,
                accessScope="Department",
            )
        )
        db.commit()
    finally:
        db.close()


def validation_rejected(body: dict | list | str, field_name: str) -> bool:
    if not isinstance(body, dict) or not isinstance(body.get("detail"), list):
        return False
    return any(item.get("loc", [])[-1:] == [field_name] for item in body["detail"] if isinstance(item, dict))


def main() -> None:
    init_db()
    seed_database()
    remove_test_users()

    options_status, options_body = request("GET", "/api/auth/registration-departments")
    if options_status != 200 or not isinstance(options_body, list) or not options_body:
        raise SystemExit("registration_departments=False")
    department_id = options_body[0]["departmentId"]

    valid_status, valid_body = request(
        "POST",
        "/api/auth/register-request",
        {
            "fullName": "  Phase Ten Four User  ",
            "email": "  Phase10.4.Valid@FDAS.local  ",
            "password": VALID_PASSWORD,
            "requestedDepartmentId": department_id,
        },
    )
    whitespace_name_status, whitespace_name_body = request(
        "POST",
        "/api/auth/register-request",
        {
            "fullName": "   ",
            "email": "phase10.4.name@fdas.local",
            "password": VALID_PASSWORD,
            "requestedDepartmentId": department_id,
        },
    )
    malformed_status, malformed_body = request(
        "POST",
        "/api/auth/register-request",
        {
            "fullName": "Malformed Email User",
            "email": "not-an-email",
            "password": VALID_PASSWORD,
            "requestedDepartmentId": department_id,
        },
    )
    empty_password_status, empty_password_body = request(
        "POST",
        "/api/auth/register-request",
        {
            "fullName": "Empty Password User",
            "email": "phase10.4.empty@fdas.local",
            "password": "",
            "requestedDepartmentId": department_id,
        },
    )
    whitespace_password_status, whitespace_password_body = request(
        "POST",
        "/api/auth/register-request",
        {
            "fullName": "Whitespace Password User",
            "email": "phase10.4.whitespace@fdas.local",
            "password": "        ",
            "requestedDepartmentId": department_id,
        },
    )
    short_password_status, short_password_body = request(
        "POST",
        "/api/auth/register-request",
        {
            "fullName": "Short Password User",
            "email": "phase10.4.short@fdas.local",
            "password": "Short1@",
            "requestedDepartmentId": department_id,
        },
    )
    duplicate_status, duplicate_body = request(
        "POST",
        "/api/auth/register-request",
        {
            "fullName": "Duplicate User",
            "email": "PHASE10.4.VALID@FDAS.LOCAL",
            "password": VALID_PASSWORD,
            "requestedDepartmentId": department_id,
        },
    )

    db = SessionLocal()
    try:
        created_user = db.query(User).filter(User.email == VALID_EMAIL).one_or_none()
        stored_name = created_user.fullName if created_user else None
        stored_email = created_user.email if created_user else None
        stored_hash = created_user.passwordHash if created_user else ""
        create_disabled_user(department_id)
    finally:
        db.close()

    admin_status, _, admin_token = login("  ADMIN@FDAS.LOCAL  ", ADMIN_PASSWORD)
    operator_status, _, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)
    invalid_status, invalid_body, _ = login(ADMIN_EMAIL, "WrongPassword")
    unknown_status, unknown_body, _ = login("unknown@fdas.local", "WrongPassword")
    pending_status, pending_body, _ = login(VALID_EMAIL, VALID_PASSWORD)
    disabled_status, disabled_body, _ = login(DISABLED_EMAIL, VALID_PASSWORD)
    admin_users_status, _ = request("GET", "/api/admin/users", token=admin_token)
    operator_admin_status, _ = request("GET", "/api/admin/users", token=operator_token)
    operator_dashboard_status, _ = request("GET", "/api/dashboard/summary", token=operator_token)

    results = {
        "registration_departments_available": options_status == 200 and bool(options_body),
        "valid_registration": valid_status == 201 and isinstance(valid_body, dict),
        "name_trimming": stored_name == "Phase Ten Four User" and valid_body.get("fullName") == stored_name,
        "whitespace_only_name_rejected": whitespace_name_status == 422 and validation_rejected(whitespace_name_body, "fullName"),
        "local_email_accepted": stored_email == VALID_EMAIL,
        "malformed_email_rejected": malformed_status == 422 and validation_rejected(malformed_body, "email"),
        "email_whitespace_and_case_normalized": valid_body.get("email") == VALID_EMAIL,
        "empty_password_rejected": empty_password_status == 422 and validation_rejected(empty_password_body, "password"),
        "whitespace_only_password_rejected": whitespace_password_status == 422 and validation_rejected(whitespace_password_body, "password"),
        "short_password_rejected": short_password_status == 422 and validation_rejected(short_password_body, "password"),
        "existing_style_password_accepted": bool(stored_hash) and verify_password(VALID_PASSWORD, stored_hash),
        "duplicate_email_clean_conflict": duplicate_status == 409
        and isinstance(duplicate_body, dict)
        and duplicate_body.get("detail") == DUPLICATE_MESSAGE,
        "password_stored_hashed": bool(stored_hash)
        and stored_hash != VALID_PASSWORD
        and stored_hash.startswith("pbkdf2_sha256$120000$"),
        "admin_login": admin_status == 200 and bool(admin_token),
        "operator_login": operator_status == 200 and bool(operator_token),
        "invalid_credentials_rejected": invalid_status == 401
        and unknown_status == 401
        and invalid_body == unknown_body,
        "pending_account_blocked": pending_status == 403
        and isinstance(pending_body, dict)
        and pending_body.get("detail") == "User status is Pending",
        "disabled_account_blocked": disabled_status == 403
        and isinstance(disabled_body, dict)
        and disabled_body.get("detail") == "User status is Disabled",
        "admin_user_authorization_unchanged": admin_users_status == 200,
        "operator_authorization_unchanged": operator_admin_status == 403 and operator_dashboard_status == 200,
        "validation_errors_hide_internal_details": all(
            "passwordHash" not in json.dumps(body) and "traceback" not in json.dumps(body).lower()
            for body in [
                whitespace_name_body,
                malformed_body,
                empty_password_body,
                whitespace_password_body,
                short_password_body,
                duplicate_body,
            ]
        ),
    }

    try:
        for name, passed in results.items():
            print(f"{name}={passed}")
        if not all(results.values()):
            raise SystemExit(1)
    finally:
        remove_test_users()


if __name__ == "__main__":
    main()
