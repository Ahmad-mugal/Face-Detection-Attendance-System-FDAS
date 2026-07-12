import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from app.config import BASE_DIR
from app.database import SessionLocal, init_db
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.seed import seed_database


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"
OPERATOR_EMAIL = "operator.cs@fdas.local"
OPERATOR_PASSWORD = "Operator@12345"

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02"
    b"\xfeA\xe2!\xbc\x00\x00\x00\x00IEND\xaeB`\x82"
)


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
    files: list[tuple[str, bytes, str]],
    token: str | None = None,
) -> tuple[int, dict | list]:
    boundary = "----FDASPhase6BVerifyBoundary"
    chunks: list[bytes] = []
    for filename, content, content_type in files:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode("utf-8")
        )
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
        timeout=120,
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
        cs_students = (
            db.query(Student)
            .filter(Student.rollNo.in_(["CS-2026-001", "CS-2026-002"]))
            .order_by(Student.rollNo)
            .all()
        )
        it_student = db.query(Student).filter(Student.rollNo == "IT-2026-001").one()
        student_ids = [student.studentId for student in cs_students] + [it_student.studentId]
        templates = db.query(FaceTemplate).filter(FaceTemplate.studentId.in_(student_ids)).all()
        for template in templates:
            template.isActive = False
            template.status = "Inactive"
        db.commit()
        return cs_students[0].studentId, cs_students[1].studentId, it_student.studentId


def storage_path_saved(template_path: str | None, student_id: int) -> bool:
    if not template_path:
        return False
    relative_path = Path(template_path)
    absolute_path = BASE_DIR / relative_path
    expected_parent = BASE_DIR / "storage" / "face_enrollments" / str(student_id)
    try:
        return absolute_path.exists() and absolute_path.parent.resolve() == expected_parent.resolve()
    except OSError:
        return False


def storage_gitignored() -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", "fdas-app/backend/storage/face_enrollments/test.png"],
        cwd=BASE_DIR.parent.parent,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def main() -> None:
    cs_student_id, second_cs_student_id, it_student_id = seed_and_prepare()

    phase3_passed = run_prior_verifier("app.verify_phase3")
    phase4_passed = run_prior_verifier("app.verify_phase4", "phase4_passed=True")
    phase6a_passed = run_prior_verifier("app.verify_phase6a", "phase6a_passed=True")

    health_status, health_body = request("GET", "/health")
    admin_login_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    operator_login_status, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)

    admin_upload_status, admin_upload_body = multipart_request(
        "POST",
        f"/api/students/{cs_student_id}/face-enrollment/upload",
        [("phase6b_admin.png", TINY_PNG, "image/png")],
        token=admin_token,
    )
    uploaded_samples = admin_upload_body.get("uploadedSamples", []) if isinstance(admin_upload_body, dict) else []
    template_id = uploaded_samples[0].get("templateId") if uploaded_samples else None
    template_path = uploaded_samples[0].get("templatePath") if uploaded_samples else None

    with SessionLocal() as db:
        template_created = template_id is not None and db.query(FaceTemplate).filter(FaceTemplate.templateId == template_id).one_or_none() is not None

    student_status, student_body = request("GET", f"/api/students/{cs_student_id}", token=admin_token)
    list_status, list_body = request("GET", f"/api/students/{cs_student_id}/face-enrollment", token=admin_token)

    unsupported_status, _ = multipart_request(
        "POST",
        f"/api/students/{cs_student_id}/face-enrollment/upload",
        [("phase6b_bad.txt", b"not an image", "text/plain")],
        token=admin_token,
    )
    empty_file_status, _ = multipart_request(
        "POST",
        f"/api/students/{cs_student_id}/face-enrollment/upload",
        [("phase6b_empty.png", b"", "image/png")],
        token=admin_token,
    )

    operator_upload_status, operator_upload_body = multipart_request(
        "POST",
        f"/api/students/{second_cs_student_id}/face-enrollment/upload",
        [("phase6b_operator.jpg", TINY_PNG, "image/jpeg")],
        token=operator_token,
    )
    operator_cross_status, _ = multipart_request(
        "POST",
        f"/api/students/{it_student_id}/face-enrollment/upload",
        [("phase6b_cross.png", TINY_PNG, "image/png")],
        token=operator_token,
    )

    deactivate_status, deactivate_body = request("PATCH", f"/api/face-templates/{template_id}/deactivate", token=admin_token)
    after_deactivate_status, after_deactivate_body = request(
        "GET",
        f"/api/students/{cs_student_id}/face-enrollment",
        token=admin_token,
    )

    clear_status, clear_body = request(
        "PATCH",
        f"/api/students/{second_cs_student_id}/face-enrollment/clear",
        token=admin_token,
    )

    active_after_deactivate = after_deactivate_body.get("templates", []) if isinstance(after_deactivate_body, dict) else []
    operator_uploaded_samples = (
        operator_upload_body.get("uploadedSamples", []) if isinstance(operator_upload_body, dict) else []
    )

    internal_checks_passed = phase3_passed and phase4_passed and phase6a_passed and empty_file_status == 422
    results = {
        "health": health_status == 200 and isinstance(health_body, dict) and health_body.get("database") == "connected",
        "admin_login": admin_login_status == 200 and bool(admin_token),
        "operator_login": operator_login_status == 200 and bool(operator_token),
        "admin_upload_face_sample": admin_upload_status == 201 and len(uploaded_samples) == 1,
        "face_file_saved": storage_path_saved(template_path, cs_student_id),
        "face_template_created": template_created,
        "student_face_registered": student_status == 200 and isinstance(student_body, dict) and student_body.get("faceRegistered") is True,
        "list_face_templates": list_status == 200 and isinstance(list_body, dict) and len(list_body.get("templates", [])) == 1,
        "unsupported_file_rejected": unsupported_status == 422,
        "operator_own_student_upload": operator_upload_status == 201 and len(operator_uploaded_samples) == 1,
        "operator_cross_department_blocked": operator_cross_status == 403,
        "deactivate_template": (
            deactivate_status == 200
            and isinstance(deactivate_body, dict)
            and deactivate_body.get("isActive") is False
            and after_deactivate_status == 200
            and len(active_after_deactivate) == 0
        ),
        "clear_student_enrollment": (
            clear_status == 200
            and isinstance(clear_body, dict)
            and clear_body.get("deactivatedCount", 0) >= 1
            and clear_body.get("faceRegistered") is False
        ),
        "storage_gitignored": storage_gitignored(),
    }
    results["phase6b_passed"] = internal_checks_passed and all(results.values())

    for name, passed in results.items():
        print(f"{name}={passed}")

    if not results["phase6b_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
