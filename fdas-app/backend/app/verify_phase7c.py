import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime

import cv2
import numpy as np

from app.config import BASE_DIR, FACE_MATCH_THRESHOLD
from app.database import SessionLocal, init_db
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.seed import seed_database
from app.services.attendance_marking import create_attendance_from_match_result
from app.services.face_enrollment import FACE_ENROLLMENT_SAMPLE_COUNT
from app.services.face_processing import ENCODING_VERSION
from app.utils.time import utc_now_naive


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"
OPERATOR_EMAIL = "operator.cs@fdas.local"
OPERATOR_PASSWORD = "Operator@12345"


def make_test_png() -> bytes:
    image = np.full((128, 128, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (24, 24), (104, 104), (220, 220, 220), thickness=2)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not generate test PNG")
    return encoded.tobytes()


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | list]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def multipart_request(
    method: str,
    path: str,
    file_tuple: tuple[str, bytes, str],
    token: str | None = None,
    fields: dict[str, str | int] | None = None,
) -> tuple[int, dict | list]:
    boundary = "----FDASPhase7CVerifyBoundary"
    chunks: list[bytes] = []
    for name, value in (fields or {}).items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    filename, content, content_type = file_tuple
    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
    chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    chunks.append(content)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))

    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=b"".join(chunks), headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def login(email: str, password: str) -> tuple[int, str | None]:
    status_code, body = request("POST", "/api/auth/login", {"email": email, "password": password})
    if isinstance(body, dict):
        return status_code, body.get("accessToken")
    return status_code, None


def run_prior_verifier(module_name: str, success_marker: str | None = None) -> bool:
    # The unified runner executes prerequisites once in order before this verifier.
    if os.getenv("FDAS_SKIP_PRIOR_VERIFIERS") == "1":
        return True
    result = subprocess.run(
        [sys.executable, "-m", module_name],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        return False
    output = f"{result.stdout}\n{result.stderr}"
    if success_marker is not None:
        return success_marker in output
    return all(line.endswith("=True") for line in result.stdout.splitlines() if "=" in line)


def seed_and_prepare() -> tuple[int, int, int]:
    init_db()
    seed_database()
    with SessionLocal() as db:
        cs = db.query(Department).filter(Department.departmentName == "Computer Science").one()
        it = db.query(Department).filter(Department.departmentName == "IT").one()
        cs_class = db.query(ClassRoom).filter(ClassRoom.departmentId == cs.departmentId).order_by(ClassRoom.classId).first()

        for session in db.query(AttendanceSession).filter(AttendanceSession.status == "Active").all():
            session.status = "Cancelled"
            session.actualEndTime = utc_now_naive()

        student = db.query(Student).filter(Student.rollNo == "P7C-MARK-001").one_or_none()
        if student is None:
            student = Student(
                rollNo="P7C-MARK-001",
                fullName="Phase Seven C Mark Student",
                email=None,
                phone=None,
                departmentId=cs.departmentId,
                classId=cs_class.classId,
                yearSemester=cs_class.yearSemester,
                section=cs_class.section,
                status="Active",
            )
            db.add(student)
            db.flush()
        else:
            student.departmentId = cs.departmentId
            student.classId = cs_class.classId
            student.yearSemester = cs_class.yearSemester
            student.section = cs_class.section
            student.status = "Active"

        db.query(AttendanceRecord).filter(AttendanceRecord.studentId == student.studentId).delete()
        db.query(FaceTemplate).filter(FaceTemplate.studentId == student.studentId).delete()

        descriptor = [1.0] + [0.0] * 255
        for sample_index in range(1, FACE_ENROLLMENT_SAMPLE_COUNT + 1):
            db.add(
                FaceTemplate(
                    studentId=student.studentId,
                    templatePath=f"storage/face_enrollments/{student.studentId}/phase7c_control_{sample_index:02d}.png",
                    encodingData=json.dumps(descriptor),
                    encodingVersion=ENCODING_VERSION,
                    sampleIndex=sample_index,
                    status="Encoded",
                    isActive=True,
                    createdByUserId=None,
                )
            )
        db.commit()
        return cs.departmentId, it.departmentId, student.studentId


def controlled_marking_checks(session_id: int, student_id: int) -> tuple[bool, bool, int | None]:
    with SessionLocal() as db:
        session = db.query(AttendanceSession).filter(AttendanceSession.sessionId == session_id).one()
        student = db.query(Student).filter(Student.studentId == student_id).one()
        match_result = {
            "matched": True,
            "status": "Matched",
            "message": "Controlled verifier match result.",
            "studentId": student.studentId,
            "studentName": student.fullName,
            "rollNo": student.rollNo,
            "classId": student.classId,
            "className": student.classroom.className if student.classroom else None,
            "departmentId": student.departmentId,
            "departmentName": student.department.departmentName if student.department else None,
            "bestTemplateId": None,
            "similarityScore": 0.99,
            "thresholdUsed": FACE_MATCH_THRESHOLD,
            "candidateCount": FACE_ENROLLMENT_SAMPLE_COUNT,
        }
        created = create_attendance_from_match_result(db, session, match_result)
        duplicate = create_attendance_from_match_result(db, session, match_result)
        record_count = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.sessionId == session_id, AttendanceRecord.studentId == student_id)
            .count()
        )
        return (
            created.get("attendanceMarked") is True
            and created.get("status") == "AttendanceMarked"
            and created.get("recognitionConfidence") == 0.99
            and created.get("livenessStatus") == "NotChecked"
            and record_count == 1,
            duplicate.get("attendanceMarked") is False
            and duplicate.get("status") == "DuplicateAttendance"
            and duplicate.get("attendanceRecordId") == created.get("attendanceRecordId")
            and record_count == 1,
            created.get("attendanceRecordId") if isinstance(created.get("attendanceRecordId"), int) else None,
        )


def no_attendance_count(session_id: int) -> int:
    with SessionLocal() as db:
        return db.query(AttendanceRecord).filter(AttendanceRecord.sessionId == session_id).count()


def main() -> None:
    cs_department_id, it_department_id, student_id = seed_and_prepare()
    test_png = make_test_png()

    phase3_passed = run_prior_verifier("app.verify_phase3")
    phase4_passed = run_prior_verifier("app.verify_phase4", "phase4_passed=True")
    phase6a_passed = run_prior_verifier("app.verify_phase6a", "phase6a_passed=True")
    phase6b_passed = run_prior_verifier("app.verify_phase6b", "phase6b_passed=True")
    phase7a_passed = run_prior_verifier("app.verify_phase7a", "phase7a_passed=True")
    phase7b_passed = run_prior_verifier("app.verify_phase7b", "phase7b_passed=True")

    seed_and_prepare()
    health_status, health_body = request("GET", "/health")
    admin_login_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    operator_login_status, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)

    start_status, started_session = request(
        "POST",
        "/api/attendance-sessions/start",
        {"departmentId": cs_department_id},
        token=admin_token,
    )
    session_id = started_session.get("sessionId") if isinstance(started_session, dict) else None

    invalid_status, _ = multipart_request(
        "POST",
        "/api/attendance/mark-by-face",
        ("phase7c_invalid_session.png", test_png, "image/png"),
        token=admin_token,
        fields={"sessionId": 999999},
    )

    it_start_status, it_session = request(
        "POST",
        "/api/attendance-sessions/start",
        {"departmentId": it_department_id},
        token=admin_token,
    )
    it_session_id = it_session.get("sessionId") if isinstance(it_session, dict) else None
    operator_cross_status, _ = multipart_request(
        "POST",
        "/api/attendance/mark-by-face",
        ("phase7c_cross_department.png", test_png, "image/png"),
        token=operator_token,
        fields={"sessionId": it_session_id or 999998},
    )

    no_face_status, no_face_body = multipart_request(
        "POST",
        "/api/attendance/mark-by-face",
        ("phase7c_no_face.png", test_png, "image/png"),
        token=admin_token,
        fields={"sessionId": session_id or 999997},
    )
    no_face_record_count = no_attendance_count(session_id) if isinstance(session_id, int) else -1

    match_below_threshold_no_attendance = False
    successful_match_creates_record = False
    duplicate_attendance_prevented = False
    created_record_id = None
    if isinstance(session_id, int):
        with SessionLocal() as db:
            session = db.query(AttendanceSession).filter(AttendanceSession.sessionId == session_id).one()
            below_result = create_attendance_from_match_result(
                db,
                session,
                {
                    "matched": False,
                    "status": "MatchBelowThreshold",
                    "message": "Controlled below-threshold verifier result.",
                    "similarityScore": 0.1,
                    "thresholdUsed": FACE_MATCH_THRESHOLD,
                    "candidateCount": FACE_ENROLLMENT_SAMPLE_COUNT,
                },
            )
            below_count = (
                db.query(AttendanceRecord).filter(AttendanceRecord.sessionId == session_id).count()
            )
            match_below_threshold_no_attendance = (
                below_result.get("attendanceMarked") is False
                and below_result.get("status") == "MatchBelowThreshold"
                and below_count == 0
            )
        successful_match_creates_record, duplicate_attendance_prevented, created_record_id = controlled_marking_checks(
            session_id,
            student_id,
        )

    records_status, records_body = request("GET", f"/api/attendance-sessions/{session_id}/records", token=admin_token)
    stop_status, _ = request("POST", f"/api/attendance-sessions/{session_id}/stop", token=admin_token)
    closed_status, _ = multipart_request(
        "POST",
        "/api/attendance/mark-by-face",
        ("phase7c_closed_session.png", test_png, "image/png"),
        token=admin_token,
        fields={"sessionId": session_id or 999996},
    )

    if it_session_id:
        request("POST", f"/api/attendance-sessions/{it_session_id}/stop", token=admin_token)

    results = {
        "health": health_status == 200 and isinstance(health_body, dict) and health_body.get("database") == "connected",
        "phase3_still_passed": phase3_passed,
        "phase4_still_passed": phase4_passed,
        "phase6a_still_passed": phase6a_passed,
        "phase6b_still_passed": phase6b_passed,
        "phase7a_still_passed": phase7a_passed,
        "phase7b_still_passed": phase7b_passed,
        "admin_login": admin_login_status == 200 and bool(admin_token),
        "operator_login": operator_login_status == 200 and bool(operator_token),
        "start_session": start_status == 201 and isinstance(started_session, dict) and started_session.get("status") == "Active",
        "no_active_session_rejected": invalid_status == 404,
        "access_control": it_start_status == 201 and operator_cross_status == 403,
        "no_face_no_attendance": (
            no_face_status == 200
            and isinstance(no_face_body, dict)
            and no_face_body.get("attendanceMarked") is False
            and no_face_body.get("status") == "NoFaceDetected"
            and no_face_record_count == 0
        ),
        "match_below_threshold_no_attendance": match_below_threshold_no_attendance,
        "successful_match_creates_record": successful_match_creates_record,
        "duplicate_attendance_prevented": duplicate_attendance_prevented,
        "session_records_endpoint": (
            records_status == 200
            and isinstance(records_body, list)
            and any(record.get("attendanceRecordId") == created_record_id for record in records_body)
        ),
        "closed_session_rejected": stop_status == 200 and closed_status == 409,
    }
    results["phase7c_passed"] = all(results.values())

    for name, passed in results.items():
        print(f"{name}={passed}")

    if not results["phase7c_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
