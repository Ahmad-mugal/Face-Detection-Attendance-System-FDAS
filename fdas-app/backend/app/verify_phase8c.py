import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

import cv2
import numpy as np

from app.config import BASE_DIR, FACE_MATCH_THRESHOLD, LIVENESS_FRAME_COUNT
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
from app.services.liveness import LivenessFrame, evaluate_liveness_frames
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


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict | list | str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
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


def multipart_liveness_request(
    path: str,
    frames: list[bytes],
    token: str | None,
    session_id: int,
    challenge: str = "MOVE_RIGHT",
) -> tuple[int, dict | list | str]:
    boundary = "----FDASPhase8CVerifyBoundary"
    chunks: list[bytes] = []
    for name, value in {"sessionId": session_id, "challengeType": challenge}.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    for index, frame in enumerate(frames, start=1):
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="files"; filename="phase8c_frame_{index}.png"\r\n'.encode("utf-8")
        )
        chunks.append(b"Content-Type: image/png\r\n\r\n")
        chunks.append(frame)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))

    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=b"".join(chunks), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
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
        timeout=360,
    )
    if result.returncode != 0:
        return False
    output = f"{result.stdout}\n{result.stderr}"
    if success_marker is not None:
        return success_marker in output
    return all(line.endswith("=True") for line in result.stdout.splitlines() if "=" in line)


def seed_and_prepare() -> tuple[int, int, int, int]:
    init_db()
    seed_database()
    with SessionLocal() as db:
        cs = db.query(Department).filter(Department.departmentName == "Computer Science").one()
        it = db.query(Department).filter(Department.departmentName == "IT").one()
        cs_class = db.query(ClassRoom).filter(ClassRoom.departmentId == cs.departmentId).order_by(ClassRoom.classId).first()

        for session in db.query(AttendanceSession).filter(AttendanceSession.status == "Active").all():
            session.status = "Cancelled"
            session.actualEndTime = utc_now_naive()

        student = db.query(Student).filter(Student.rollNo == "P8C-LIVE-001").one_or_none()
        if student is None:
            student = Student(
                rollNo="P8C-LIVE-001",
                fullName="Phase Eight C Live Student",
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
            student.status = "Active"

        db.query(AttendanceRecord).filter(AttendanceRecord.studentId == student.studentId).delete()
        db.query(FaceTemplate).filter(FaceTemplate.studentId == student.studentId).delete()
        descriptor = [1.0] + [0.0] * 255
        for sample_index in range(1, FACE_ENROLLMENT_SAMPLE_COUNT + 1):
            db.add(
                FaceTemplate(
                    studentId=student.studentId,
                    templatePath=f"storage/face_enrollments/{student.studentId}/phase8c_control_{sample_index:02d}.png",
                    encodingData=json.dumps(descriptor),
                    encodingVersion=ENCODING_VERSION,
                    sampleIndex=sample_index,
                    status="Encoded",
                    isActive=True,
                    createdByUserId=None,
                )
            )

        now = utc_now_naive()
        session = AttendanceSession(
            departmentId=cs.departmentId,
            startedByUserId=1,
            scheduledStartTime=now,
            scheduledEndTime=now + timedelta(hours=1),
            actualStartTime=now,
            actualEndTime=None,
            status="Active",
            createdDate=date.today(),
        )
        closed_session = AttendanceSession(
            departmentId=cs.departmentId,
            startedByUserId=1,
            scheduledStartTime=now,
            scheduledEndTime=now + timedelta(hours=1),
            actualStartTime=now,
            actualEndTime=now,
            status="Closed",
            createdDate=date.today(),
        )
        db.add_all([session, closed_session])
        db.commit()
        return cs.departmentId, it.departmentId, session.sessionId, closed_session.sessionId


def controlled_liveness_checks() -> tuple[bool, bool, bool, bool]:
    def frames_from_boxes(boxes: list[tuple[int, int, int, int]]) -> list[LivenessFrame]:
        return [
            LivenessFrame(
                image_bytes=f"frame-{index}".encode("ascii"),
                width=200,
                height=200,
                face_count=1,
                face_box=box,
                face_descriptor=[1.0, 0.0, 0.0],
            )
            for index, box in enumerate(boxes)
        ]

    baseline = [(50, 50, 60, 60), (50, 50, 60, 60)]
    preview_left_frames = frames_from_boxes(
        baseline + [(54, 50, 60, 60), (60, 50, 60, 60), (68, 50, 60, 60), (72, 50, 60, 60), (70, 50, 60, 60), (68, 50, 60, 60), (66, 50, 60, 60)]
    )
    preview_right_frames = frames_from_boxes(
        baseline + [(46, 50, 60, 60), (40, 50, 60, 60), (32, 50, 60, 60), (28, 50, 60, 60), (30, 50, 60, 60), (32, 50, 60, 60), (34, 50, 60, 60)]
    )
    static_frames = frames_from_boxes(baseline + [(50, 50, 60, 60)] * 7)
    closer_frames = frames_from_boxes(
        [(60, 60, 50, 50), (60, 60, 50, 50)]
        + [(59, 59, 52, 52), (57, 57, 55, 55), (55, 55, 58, 58), (54, 54, 60, 60), (54, 54, 60, 60), (55, 55, 58, 58), (57, 57, 55, 55)]
    )
    one_spike_frames = frames_from_boxes(
        baseline + [(50, 50, 60, 60), (50, 50, 60, 60), (70, 50, 60, 60), (50, 50, 60, 60), (50, 50, 60, 60), (50, 50, 60, 60), (50, 50, 60, 60)]
    )
    return (
        evaluate_liveness_frames(preview_left_frames, "MOVE_LEFT").passed
        and evaluate_liveness_frames(preview_right_frames, "MOVE_RIGHT").passed
        and evaluate_liveness_frames(closer_frames, "MOVE_CLOSER").passed,
        not evaluate_liveness_frames(static_frames, "MOVE_LEFT").passed
        and not evaluate_liveness_frames(static_frames, "MOVE_RIGHT").passed
        and not evaluate_liveness_frames(static_frames, "MOVE_CLOSER").passed,
        not evaluate_liveness_frames(preview_right_frames, "MOVE_LEFT").passed
        and not evaluate_liveness_frames(preview_left_frames, "MOVE_RIGHT").passed,
        not evaluate_liveness_frames(one_spike_frames, "MOVE_LEFT").passed,
    )


def controlled_attendance_creation(session_id: int) -> tuple[bool, bool]:
    with SessionLocal() as db:
        session = db.query(AttendanceSession).filter(AttendanceSession.sessionId == session_id).one()
        student = db.query(Student).filter(Student.rollNo == "P8C-LIVE-001").one()
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
            "similarityScore": 0.98,
            "thresholdUsed": FACE_MATCH_THRESHOLD,
            "candidateCount": FACE_ENROLLMENT_SAMPLE_COUNT,
        }
        created = create_attendance_from_match_result(db, session, match_result, liveness_status="Passed")
        duplicate = create_attendance_from_match_result(db, session, match_result, liveness_status="Passed")
        record_count = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.sessionId == session.sessionId, AttendanceRecord.studentId == student.studentId)
            .count()
        )
        return (
            created.get("attendanceMarked") is True
            and created.get("status") == "AttendanceMarked"
            and created.get("livenessStatus") == "Passed"
            and record_count == 1,
            duplicate.get("attendanceMarked") is False
            and duplicate.get("status") == "DuplicateAttendance"
            and duplicate.get("attendanceRecordId") == created.get("attendanceRecordId")
            and record_count == 1,
        )


def record_count_for_session(session_id: int) -> int:
    with SessionLocal() as db:
        return db.query(AttendanceRecord).filter(AttendanceRecord.sessionId == session_id).count()


def main() -> None:
    _, _, session_id, closed_session_id = seed_and_prepare()
    test_png = make_test_png()
    frames = [test_png for _ in range(LIVENESS_FRAME_COUNT)]

    phase3_passed = run_prior_verifier("app.verify_phase3")
    phase4_passed = run_prior_verifier("app.verify_phase4", "phase4_passed=True")
    phase6a_passed = run_prior_verifier("app.verify_phase6a", "phase6a_passed=True")
    phase6b_passed = run_prior_verifier("app.verify_phase6b", "phase6b_passed=True")
    phase7a_passed = run_prior_verifier("app.verify_phase7a", "phase7a_passed=True")
    phase7b_passed = run_prior_verifier("app.verify_phase7b", "phase7b_passed=True")
    phase7c_passed = run_prior_verifier("app.verify_phase7c", "phase7c_passed=True")
    phase8b_passed = run_prior_verifier("app.verify_phase8b", "phase8b_passed=True")

    _, _, session_id, closed_session_id = seed_and_prepare()
    health_status, health_body = request("GET", "/health")
    admin_login_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    operator_login_status, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)
    info_status, info_body = request("GET", "/api/liveness/info", token=admin_token)

    missing_status, _ = multipart_liveness_request(
        "/api/attendance/mark-by-face-live",
        frames[:2],
        admin_token,
        session_id,
    )
    invalid_status, _ = multipart_liveness_request(
        "/api/attendance/mark-by-face-live",
        frames,
        admin_token,
        session_id,
        challenge="BLINK",
    )
    no_face_before = record_count_for_session(session_id)
    no_face_status, no_face_body = multipart_liveness_request(
        "/api/attendance/mark-by-face-live",
        frames,
        admin_token,
        session_id,
        challenge="MOVE_RIGHT",
    )
    no_face_after = record_count_for_session(session_id)
    no_face_diagnostics = no_face_body.get("livenessDiagnostics") if isinstance(no_face_body, dict) else None

    (
        controlled_liveness_pass,
        static_repeated_frame_fails,
        wrong_direction_fails,
        single_frame_jitter_fails,
    ) = controlled_liveness_checks()
    liveness_failed_no_record = no_face_after == no_face_before
    successful_match_creates_record, duplicate_prevented = controlled_attendance_creation(session_id)

    closed_status, _ = multipart_liveness_request(
        "/api/attendance/mark-by-face-live",
        frames,
        admin_token,
        closed_session_id,
        challenge="MOVE_RIGHT",
    )

    results = {
        "health": health_status == 200 and isinstance(health_body, dict) and health_body.get("database") == "connected",
        "phase3_still_passed": phase3_passed,
        "phase4_still_passed": phase4_passed,
        "phase6a_still_passed": phase6a_passed,
        "phase6b_still_passed": phase6b_passed,
        "phase7a_still_passed": phase7a_passed,
        "phase7b_still_passed": phase7b_passed,
        "phase7c_still_passed": phase7c_passed,
        "phase8b_still_passed": phase8b_passed,
        "admin_login": admin_login_status == 200 and bool(admin_token),
        "operator_login": operator_login_status == 200 and bool(operator_token),
        "mark_by_face_live_endpoint": (
            info_status == 200
            and isinstance(info_body, dict)
            and info_body.get("mode") == "basic"
            and info_body.get("frameCount") == LIVENESS_FRAME_COUNT
            and info_body.get("baselineFrameCount") == 2
            and info_body.get("movementFrameCount") == 7
            and info_body.get("diagnosticsExposed") is True
            and info_body.get("previewMirrored") is True
        ),
        "missing_frames_rejected": missing_status == 422,
        "invalid_challenge_rejected": invalid_status == 422,
        "no_face_frames_handled_safely": (
            no_face_status == 200
            and isinstance(no_face_body, dict)
            and no_face_body.get("attendanceMarked") is False
            and no_face_body.get("status") in {"NoFaceDetected", "LivenessFailed"}
            and no_face_body.get("livenessStatus") == "Failed"
        ),
        "controlled_movement_liveness_passes": controlled_liveness_pass,
        "static_repeated_frame_fails": static_repeated_frame_fails,
        "wrong_direction_movement_fails": wrong_direction_fails,
        "single_frame_detector_jitter_fails": single_frame_jitter_fails,
        "liveness_diagnostics_exposed_safely": (
            isinstance(no_face_diagnostics, dict)
            and no_face_diagnostics.get("challenge") == "MOVE_RIGHT"
            and no_face_diagnostics.get("submittedFrameCount") == LIVENESS_FRAME_COUNT
            and isinstance(no_face_diagnostics.get("detectedFaceFrameCount"), int)
            and "displacementRatio" in no_face_diagnostics
            and "areaGrowthRatio" in no_face_diagnostics
            and bool(no_face_diagnostics.get("reason"))
            and "image" not in " ".join(no_face_diagnostics.keys()).lower()
        ),
        "liveness_failed_no_attendance": liveness_failed_no_record,
        "liveness_passed_successful_match_creates_record": successful_match_creates_record,
        "duplicate_attendance_prevented": duplicate_prevented,
        "closed_session_rejected": closed_status == 409,
    }
    results["phase8c_passed"] = all(results.values())

    for name, passed in results.items():
        print(f"{name}={passed}")
    print("real_camera_liveness_verified=False")
    print("manual_real_camera_liveness_test_required=True")

    if not results["phase8c_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
