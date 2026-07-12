import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from types import SimpleNamespace

import cv2
import numpy as np

from app.config import BASE_DIR, FACE_MATCH_THRESHOLD
from app.database import SessionLocal, init_db
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.seed import seed_database
from app.services.face_enrollment import FACE_ENROLLMENT_SAMPLE_COUNT
from app.services.face_matching import MatchCandidate, compare_descriptors, find_best_match
from app.services.face_processing import ENCODING_VERSION


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
        with urllib.request.urlopen(req, timeout=10) as response:
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
    boundary = "----FDASPhase7BVerifyBoundary"
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


def run_prior_verifier(module_name: str, success_marker: str | None = None) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", module_name],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=240,
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

        student = db.query(Student).filter(Student.rollNo == "P7B-ENCODED-001").one_or_none()
        if student is None:
            student = Student(
                rollNo="P7B-ENCODED-001",
                fullName="Phase Seven B Encoded Student",
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
            student.status = "Active"

        db.query(FaceTemplate).filter(FaceTemplate.studentId == student.studentId).delete()
        descriptor = [1.0] + [0.0] * 255
        for sample_index in range(1, FACE_ENROLLMENT_SAMPLE_COUNT + 1):
            db.add(
                FaceTemplate(
                    studentId=student.studentId,
                    templatePath=f"storage/face_enrollments/{student.studentId}/phase7b_control_{sample_index:02d}.png",
                    encodingData=json.dumps(descriptor),
                    encodingVersion=ENCODING_VERSION,
                    sampleIndex=sample_index,
                    status="Encoded",
                    isActive=True,
                    createdByUserId=None,
                )
            )
        db.commit()
        return cs.departmentId, it.departmentId, student.studentId, cs_class.classId


def verify_descriptor_logic() -> bool:
    template_a = SimpleNamespace(templateId=101, studentId=1)
    template_b = SimpleNamespace(templateId=102, studentId=2)
    candidates = [
        MatchCandidate(template=template_a, descriptor=[1.0, 0.0, 0.0]),
        MatchCandidate(template=template_b, descriptor=[0.0, 1.0, 0.0]),
    ]
    best_candidate, best_score = find_best_match([1.0, 0.0, 0.0], candidates, threshold=0.75)
    weak_candidate, weak_score = find_best_match([0.2, 0.2, 0.959], candidates, threshold=0.75)
    return (
        compare_descriptors([1.0, 0.0], [1.0, 0.0]) == 1.0
        and best_candidate is not None
        and best_candidate.template.templateId == 101
        and best_score == 1.0
        and weak_score is not None
        and weak_score < 0.75
        and (weak_candidate is None or weak_candidate.template.templateId in {101, 102})
    )


def main() -> None:
    cs_department_id, it_department_id, encoded_student_id, _ = seed_and_prepare()
    test_png = make_test_png()

    phase3_passed = run_prior_verifier("app.verify_phase3")
    phase4_passed = run_prior_verifier("app.verify_phase4", "phase4_passed=True")
    phase6a_passed = run_prior_verifier("app.verify_phase6a", "phase6a_passed=True")
    phase6b_passed = run_prior_verifier("app.verify_phase6b", "phase6b_passed=True")
    phase7a_passed = run_prior_verifier("app.verify_phase7a", "phase7a_passed=True")

    health_status, health_body = request("GET", "/health")
    admin_login_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    operator_login_status, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)

    info_status, info_body = request("GET", "/api/face-matching/info", token=admin_token)
    no_face_status, no_face_body = multipart_request(
        "POST",
        "/api/face-matching/match",
        ("phase7b_no_face.png", test_png, "image/png"),
        token=admin_token,
        fields={"departmentId": cs_department_id},
    )
    invalid_file_status, _ = multipart_request(
        "POST",
        "/api/face-matching/match",
        ("phase7b_bad.txt", b"not an image", "text/plain"),
        token=admin_token,
        fields={"departmentId": cs_department_id},
    )
    empty_file_status, _ = multipart_request(
        "POST",
        "/api/face-matching/match",
        ("phase7b_empty.png", b"", "image/png"),
        token=admin_token,
        fields={"departmentId": cs_department_id},
    )
    operator_own_status, operator_own_body = multipart_request(
        "POST",
        "/api/face-matching/match",
        ("phase7b_operator_own.png", test_png, "image/png"),
        token=operator_token,
        fields={"departmentId": cs_department_id},
    )
    operator_cross_status, _ = multipart_request(
        "POST",
        "/api/face-matching/match",
        ("phase7b_operator_cross.png", test_png, "image/png"),
        token=operator_token,
        fields={"departmentId": it_department_id},
    )
    student_test_status, student_test_body = multipart_request(
        "POST",
        f"/api/students/{encoded_student_id}/face-matching/test",
        ("phase7b_student_test.png", test_png, "image/png"),
        token=admin_token,
    )

    detected_face_match_verified = False
    matched_student_correct = False
    manual_real_face_match_required = True

    results = {
        "health": health_status == 200 and isinstance(health_body, dict) and health_body.get("database") == "connected",
        "phase3_still_passed": phase3_passed,
        "phase4_still_passed": phase4_passed,
        "phase6a_still_passed": phase6a_passed,
        "phase6b_still_passed": phase6b_passed,
        "phase7a_still_passed": phase7a_passed,
        "admin_login": admin_login_status == 200 and bool(admin_token),
        "operator_login": operator_login_status == 200 and bool(operator_token),
        "face_matching_info": (
            info_status == 200
            and isinstance(info_body, dict)
            and info_body.get("provider") == "OpenCV"
            and info_body.get("encodingVersion") == ENCODING_VERSION
            and info_body.get("matchingImplemented") is True
            and info_body.get("attendanceMarkingImplemented") is False
            and info_body.get("livenessImplemented") is False
            and info_body.get("threshold") == FACE_MATCH_THRESHOLD
        ),
        "no_face_handled_gracefully": (
            no_face_status == 200
            and isinstance(no_face_body, dict)
            and no_face_body.get("matched") is False
            and no_face_body.get("status") == "NoFaceDetected"
        ),
        "invalid_file_rejected": invalid_file_status == 422,
        "empty_file_rejected": empty_file_status == 422,
        "operator_own_department_match": (
            operator_own_status == 200
            and isinstance(operator_own_body, dict)
            and operator_own_body.get("status") == "NoFaceDetected"
        ),
        "operator_cross_department_blocked": operator_cross_status == 403,
        "descriptor_comparison_logic": verify_descriptor_logic(),
        "student_test_match_endpoint": (
            student_test_status == 200
            and isinstance(student_test_body, dict)
            and student_test_body.get("status") == "NoFaceDetected"
        ),
    }
    results["phase7b_passed"] = all(results.values())

    for name, passed in results.items():
        print(f"{name}={passed}")
    print(f"detected_face_match_verified={detected_face_match_verified}")
    if detected_face_match_verified:
        print(f"matched_student_correct={matched_student_correct}")
    else:
        print(f"manual_real_face_match_required={manual_real_face_match_required}")

    if not results["phase7b_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
