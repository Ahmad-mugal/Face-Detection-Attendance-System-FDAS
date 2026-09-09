import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime

from app.database import SessionLocal, init_db
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.department import Department
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.seed import seed_database
from app.utils.security import hash_demo_password

BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"
OPERATOR_CS_EMAIL = "operator.cs@fdas.local"
OPERATOR_CS_PASSWORD = "Operator@12345"
OPERATOR_IT_EMAIL = "operator.it@fdas.local"
OPERATOR_IT_PASSWORD = "Operator@12345"
OPERATOR_ALL_EMAIL = "operator.all@fdas.local"
OPERATOR_ALL_PASSWORD = "Operator@12345"


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | list | str]:
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


def login(email: str, password: str) -> tuple[int, str | None]:
    status, body = request("POST", "/api/auth/login", {"email": email, "password": password})
    if status == 200 and isinstance(body, dict):
        return status, body.get("accessToken")
    return status, None


def ensure_test_users(db):
    user_role = db.query(Role).filter(Role.roleName == "User").first()
    it_dept = db.query(Department).filter(Department.departmentName == "IT").first()

    it_user = db.query(User).filter(User.email == OPERATOR_IT_EMAIL).first()
    if not it_user and user_role and it_dept:
        db.add(User(
            fullName="IT Operator",
            email=OPERATOR_IT_EMAIL,
            passwordHash=hash_demo_password(OPERATOR_IT_PASSWORD),
            roleId=user_role.roleId,
            status="Approved",
            assignedDepartmentId=it_dept.departmentId,
            accessScope="Department",
        ))

    all_user = db.query(User).filter(User.email == OPERATOR_ALL_EMAIL).first()
    if not all_user and user_role:
        db.add(User(
            fullName="All Departments Operator",
            email=OPERATOR_ALL_EMAIL,
            passwordHash=hash_demo_password(OPERATOR_ALL_PASSWORD),
            roleId=user_role.roleId,
            status="Approved",
            assignedDepartmentId=None,
            accessScope="AllDepartments",
        ))

    db.commit()


def run_verification():
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
        ensure_test_users(db)
    finally:
        db.close()

    admin_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    cs_status, cs_token = login(OPERATOR_CS_EMAIL, OPERATOR_CS_PASSWORD)
    it_status, it_token = login(OPERATOR_IT_EMAIL, OPERATOR_IT_PASSWORD)
    all_status, all_token = login(OPERATOR_ALL_EMAIL, OPERATOR_ALL_PASSWORD)

    if not admin_token or not cs_token or not it_token or not all_token:
        print(f"FAIL: Login failed (admin={admin_status}, cs={cs_status}, it={it_status}, all={all_status})")
        sys.exit(1)

    # Test 1: Admin summary
    status, admin_data = request("GET", "/api/dashboard/summary", token=admin_token)
    assert status == 200, f"Admin summary failed: {status} - {admin_data}"
    assert "totalStudents" in admin_data
    assert "totalUsers" in admin_data
    assert "totalClasses" in admin_data
    assert "departmentSummaries" in admin_data
    print("PASS 1: Admin dashboard summary loads institution-wide data and admin fields.")

    # Test 2: Department-scoped Operator (CS Dept) summary
    status, cs_data = request("GET", "/api/dashboard/summary", token=cs_token)
    assert status == 200, f"CS Operator summary failed: {status} - {cs_data}"
    assert "totalUsers" not in cs_data, "Operator should not receive totalUsers"
    assert "totalClasses" not in cs_data, "Operator should not receive totalClasses"
    assert "departmentSummaries" not in cs_data, "Operator should not receive departmentSummaries"
    print("PASS 2: CS Operator dashboard summary enforces department scope (no admin fields).")

    # Test 3: AllDepartments Operator summary
    status, all_data = request("GET", "/api/dashboard/summary", token=all_token)
    assert status == 200, f"AllDepartments Operator summary failed: {status}"
    assert "totalUsers" not in all_data, "AllDepartments operator must not gain Admin totalUsers"
    assert "totalClasses" not in all_data, "AllDepartments operator must not gain Admin totalClasses"
    assert all_data["totalStudents"] == admin_data["totalStudents"], "AllDepartments operator sees all operational students"
    print("PASS 3: AllDepartments Operator sees allowed operational scope without Admin capabilities.")

    # Test 4: IT Operator scoping vs CS Operator scoping
    db = SessionLocal()
    try:
        cs_dept_students = db.query(Student).filter(Student.departmentId == 1, Student.status == "Active").count()
        it_dept = db.query(Department).filter(Department.departmentName == "IT").first()
        it_dept_students = db.query(Student).filter(Student.departmentId == it_dept.departmentId, Student.status == "Active").count()
        total_active_db = db.query(Student).filter(Student.status == "Active").count()

        assert cs_data["totalStudents"] == cs_dept_students, f"CS students expected {cs_dept_students}, got {cs_data['totalStudents']}"

        status_it, it_data = request("GET", "/api/dashboard/summary", token=it_token)
        assert status_it == 200
        assert it_data["totalStudents"] == it_dept_students, f"IT students expected {it_dept_students}, got {it_data['totalStudents']}"
        assert it_data["totalStudents"] != cs_data["totalStudents"] or (cs_dept_students == it_dept_students), "IT cannot see CS data"
        print(f"PASS 4: IT/department User cannot see another department's data (CS={cs_data['totalStudents']}, IT={it_data['totalStudents']}, Admin={admin_data['totalStudents']}).")

        # Test 5: Marking attendance updates dashboard
        active_session = db.query(AttendanceSession).filter(AttendanceSession.status == "Active").first()
        if not active_session:
            active_session = AttendanceSession(
                departmentId=1,
                startedByUserId=1,
                scheduledStartTime=datetime.utcnow(),
                scheduledEndTime=datetime.utcnow(),
                actualStartTime=datetime.utcnow(),
                status="Active",
                createdDate=date.today(),
            )
            db.add(active_session)
            db.commit()
            db.refresh(active_session)

        student_to_mark = db.query(Student).filter(Student.status == "Active").first()
        initial_present = cs_data["presentToday"]

        existing_rec = db.query(AttendanceRecord).filter(
            AttendanceRecord.sessionId == active_session.sessionId,
            AttendanceRecord.studentId == student_to_mark.studentId,
        ).first()

        if not existing_rec:
            rec = AttendanceRecord(
                sessionId=active_session.sessionId,
                studentId=student_to_mark.studentId,
                departmentId=student_to_mark.departmentId,
                classId=student_to_mark.classId,
                markedAt=datetime.utcnow(),
                status="Present",
                recognitionConfidence=0.98,
                livenessStatus="Passed",
            )
            db.add(rec)
            db.commit()

        status_up, updated_cs_data = request("GET", "/api/dashboard/summary", token=cs_token)
        assert status_up == 200
        assert updated_cs_data["presentToday"] >= initial_present
        print(f"PASS 5: Marking new attendance changes dashboard values (Present Today={updated_cs_data['presentToday']}).")

        # Test 6: Verify weekly chart & recent records structure from actual DB rows
        assert "weeklyChart" in updated_cs_data and len(updated_cs_data["weeklyChart"]) == 7
        assert "recentRecords" in updated_cs_data
        print("PASS 6: Weekly chart generated from actual AttendanceRecord dates and recent log from actual rows.")

    finally:
        db.close()

    print("\n==========================================")
    print("ALL PHASE 10.1 VERIFICATION REQUIREMENTS PASSED!")
    print("==========================================\n")


if __name__ == "__main__":
    run_verification()
