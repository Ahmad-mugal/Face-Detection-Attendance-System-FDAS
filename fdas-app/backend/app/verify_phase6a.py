import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, time

from app.database import SessionLocal, init_db
from app.models.attendance_session import AttendanceSession
from app.models.attendance_time_window import AttendanceTimeWindow
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.seed import seed_database
from app.utils.security import hash_password


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"
OPERATOR_EMAIL = "operator.cs@fdas.local"
OPERATOR_PASSWORD = "Operator@12345"
ALL_DEPARTMENTS_EMAIL = "phase6a.all@fdas.local"
ALL_DEPARTMENTS_PASSWORD = "Phase6A@12345"


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


def seed_and_prepare() -> tuple[int, int, time, time]:
    init_db()
    seed_database()
    with SessionLocal() as db:
        cs = db.query(Department).filter(Department.departmentName == "Computer Science").one()
        it = db.query(Department).filter(Department.departmentName == "IT").one()
        user_role = db.query(Role).filter(Role.roleName == "User").one()

        for session in db.query(AttendanceSession).filter(AttendanceSession.status == "Active").all():
            session.status = "Cancelled"
            session.actualEndTime = datetime.utcnow()

        all_departments_user = db.query(User).filter(User.email == ALL_DEPARTMENTS_EMAIL).one_or_none()
        if all_departments_user is None:
            db.add(
                User(
                    fullName="Phase 6A All Departments Operator",
                    email=ALL_DEPARTMENTS_EMAIL,
                    passwordHash=hash_password(ALL_DEPARTMENTS_PASSWORD),
                    roleId=user_role.roleId,
                    status="Approved",
                    assignedDepartmentId=None,
                    accessScope="AllDepartments",
                )
            )
        else:
            all_departments_user.passwordHash = hash_password(ALL_DEPARTMENTS_PASSWORD)
            all_departments_user.status = "Approved"
            all_departments_user.assignedDepartmentId = None
            all_departments_user.accessScope = "AllDepartments"

        start_time = time(8, 45)
        end_time = time(9, 15)
        db.add(
            AttendanceTimeWindow(
                departmentId=cs.departmentId,
                startTime=start_time,
                endTime=end_time,
                graceMinutes=11,
                status="Active",
            )
        )
        db.commit()
        return cs.departmentId, it.departmentId, start_time, end_time


def iso_time(value: str | None) -> str | None:
    if not value:
        return None
    return datetime.fromisoformat(value).time().replace(microsecond=0).isoformat()


def main() -> None:
    cs_department_id, it_department_id, window_start, window_end = seed_and_prepare()

    health_status, health_body = request("GET", "/health")
    admin_login_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    operator_login_status, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)
    all_login_status, all_token = login(ALL_DEPARTMENTS_EMAIL, ALL_DEPARTMENTS_PASSWORD)

    start_status, started_session = request(
        "POST",
        "/api/attendance-sessions/start",
        {"departmentId": cs_department_id},
        token=admin_token,
    )
    first_session_id = started_session.get("sessionId") if isinstance(started_session, dict) else None
    scheduled_start_time = iso_time(started_session.get("scheduledStartTime")) if isinstance(started_session, dict) else None
    scheduled_end_time = iso_time(started_session.get("scheduledEndTime")) if isinstance(started_session, dict) else None

    duplicate_status, _ = request(
        "POST",
        "/api/attendance-sessions/start",
        {"departmentId": cs_department_id},
        token=admin_token,
    )
    active_status, active_sessions = request("GET", "/api/attendance-sessions/active", token=admin_token)
    stop_status, stopped_session = request("POST", f"/api/attendance-sessions/{first_session_id}/stop", token=admin_token)

    restart_status, restarted_session = request(
        "POST",
        "/api/attendance-sessions/start",
        {"departmentId": cs_department_id},
        token=admin_token,
    )
    second_session_id = restarted_session.get("sessionId") if isinstance(restarted_session, dict) else None
    cancel_status, cancelled_session = request("POST", f"/api/attendance-sessions/{second_session_id}/cancel", token=admin_token)

    operator_start_status, operator_session = request(
        "POST",
        "/api/attendance-sessions/start",
        {"departmentId": cs_department_id},
        token=operator_token,
    )
    operator_session_id = operator_session.get("sessionId") if isinstance(operator_session, dict) else None
    operator_cross_status, _ = request(
        "POST",
        "/api/attendance-sessions/start",
        {"departmentId": it_department_id},
        token=operator_token,
    )
    operator_active_status, operator_active_sessions = request(
        "GET",
        "/api/attendance-sessions/active",
        token=operator_token,
    )
    operator_other_active_status, _ = request(
        "GET",
        f"/api/attendance-sessions/active?{urllib.parse.urlencode({'departmentId': it_department_id})}",
        token=operator_token,
    )

    it_start_status, it_session = request(
        "POST",
        "/api/attendance-sessions/start",
        {"departmentId": it_department_id},
        token=all_token,
    )
    it_session_id = it_session.get("sessionId") if isinstance(it_session, dict) else None
    all_active_status, all_active_sessions = request("GET", "/api/attendance-sessions/active", token=all_token)

    if operator_session_id:
        request("POST", f"/api/attendance-sessions/{operator_session_id}/stop", token=admin_token)
    if it_session_id:
        request("POST", f"/api/attendance-sessions/{it_session_id}/stop", token=admin_token)

    operator_own_only = (
        operator_active_status == 200
        and isinstance(operator_active_sessions, list)
        and len(operator_active_sessions) >= 1
        and all(session["departmentId"] == cs_department_id for session in operator_active_sessions)
    )
    all_departments_scope = (
        all_active_status == 200
        and isinstance(all_active_sessions, list)
        and {session["departmentId"] for session in all_active_sessions}.issuperset({cs_department_id, it_department_id})
    )

    results = {
        "health": health_status == 200 and isinstance(health_body, dict) and health_body.get("database") == "connected",
        "admin_login": admin_login_status == 200 and bool(admin_token),
        "operator_login": operator_login_status == 200 and bool(operator_token),
        "all_departments_login": all_login_status == 200 and bool(all_token),
        "admin_start_session": start_status == 201 and isinstance(started_session, dict) and started_session.get("status") == "Active",
        "duplicate_active_session_blocked": duplicate_status == 409,
        "admin_get_active_sessions": active_status == 200 and isinstance(active_sessions, list) and len(active_sessions) >= 1,
        "admin_stop_session": stop_status == 200 and isinstance(stopped_session, dict),
        "session_closed": isinstance(stopped_session, dict) and stopped_session.get("status") == "Closed",
        "admin_restart_after_close": restart_status == 201 and isinstance(restarted_session, dict),
        "admin_cancel_session": cancel_status == 200 and isinstance(cancelled_session, dict) and cancelled_session.get("status") == "Cancelled",
        "operator_own_department_session": operator_start_status == 201 and isinstance(operator_session, dict),
        "operator_cross_department_blocked": operator_cross_status == 403,
        "active_session_scope": operator_own_only and operator_other_active_status == 403,
        "all_departments_access": it_start_status == 201 and all_departments_scope,
        "time_window_used": scheduled_start_time == window_start.isoformat() and scheduled_end_time == window_end.isoformat(),
    }
    results["phase6a_passed"] = all(results.values())

    for name, passed in results.items():
        print(f"{name}={passed}")

    if not results["phase6a_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
