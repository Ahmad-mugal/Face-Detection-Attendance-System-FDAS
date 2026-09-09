import json
import subprocess
import sys
import urllib.error
import urllib.request

import cv2
import numpy as np
from fastapi import HTTPException

from app.config import BASE_DIR
from app.database import SessionLocal, init_db
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.seed import seed_database
from app.services.face_enrollment import FACE_ENROLLMENT_SAMPLE_COUNT
from app.services.face_processing import process_image_bytes


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


def make_sample_files(prefix: str, image_bytes: bytes) -> list[tuple[str, bytes, str]]:
    return [
        (f"{prefix}_{index:02d}.png", image_bytes, "image/png")
        for index in range(1, FACE_ENROLLMENT_SAMPLE_COUNT + 1)
    ]


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
    boundary = "----FDASPhase7AVerifyBoundary"
    chunks: list[bytes] = []
    for filename, content, content_type in files:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="files"; filename="{filename}"\r\n'.encode("utf-8"))
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
        timeout=180,
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


def template_has_encoding(template_id: int | None) -> bool:
    if template_id is None:
        return False
    with SessionLocal() as db:
        template = db.query(FaceTemplate).filter(FaceTemplate.templateId == template_id).one_or_none()
        return bool(template and template.encodingData and template.status == "Encoded")


def main() -> None:
    cs_student_id, second_cs_student_id, it_student_id = seed_and_prepare()
    test_png = make_test_png()
    processing_result = process_image_bytes(test_png)
    try:
        process_image_bytes(b"not an image")
        invalid_decode_rejected = False
    except HTTPException as exc:
        invalid_decode_rejected = exc.status_code == 422

    phase3_passed = run_prior_verifier("app.verify_phase3")
    phase4_passed = run_prior_verifier("app.verify_phase4", "phase4_passed=True")
    phase6a_passed = run_prior_verifier("app.verify_phase6a", "phase6a_passed=True")
    phase6b_passed = run_prior_verifier("app.verify_phase6b", "phase6b_passed=True")

    health_status, health_body = request("GET", "/health")
    admin_login_status, admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    operator_login_status, operator_token = login(OPERATOR_EMAIL, OPERATOR_PASSWORD)

    upload_status, upload_body = multipart_request(
        "POST",
        f"/api/students/{cs_student_id}/face-enrollment/upload",
        make_sample_files("phase7a_valid", test_png),
        token=admin_token,
    )
    uploaded_samples = upload_body.get("uploadedSamples", []) if isinstance(upload_body, dict) else []
    template_id = uploaded_samples[0].get("templateId") if uploaded_samples else None
    upload_template_status = uploaded_samples[0].get("status") if uploaded_samples else None

    unsupported_status, _ = multipart_request(
        "POST",
        f"/api/students/{cs_student_id}/face-enrollment/upload",
        [("phase7a_bad.txt", b"not an image", "text/plain")],
        token=admin_token,
    )
    empty_status, _ = multipart_request(
        "POST",
        f"/api/students/{cs_student_id}/face-enrollment/upload",
        [("phase7a_empty.png", b"", "image/png")],
        token=admin_token,
    )

    info_status, info_body = request("GET", "/api/face-processing/info", token=admin_token)
    process_status, process_body = request("POST", f"/api/face-templates/{template_id}/process", token=admin_token)
    process_all_status, process_all_body = request(
        "POST",
        f"/api/students/{cs_student_id}/face-enrollment/process-all",
        token=admin_token,
    )

    operator_upload_status, operator_upload_body = multipart_request(
        "POST",
        f"/api/students/{second_cs_student_id}/face-enrollment/upload",
        make_sample_files("phase7a_operator", test_png),
        token=operator_token,
    )
    operator_template_id = None
    if isinstance(operator_upload_body, dict) and operator_upload_body.get("uploadedSamples"):
        operator_template_id = operator_upload_body["uploadedSamples"][0].get("templateId")
    operator_process_status, _ = request("POST", f"/api/face-templates/{operator_template_id}/process", token=operator_token)

    it_upload_status, it_upload_body = multipart_request(
        "POST",
        f"/api/students/{it_student_id}/face-enrollment/upload",
        make_sample_files("phase7a_it", test_png),
        token=admin_token,
    )
    it_template_id = None
    if isinstance(it_upload_body, dict) and it_upload_body.get("uploadedSamples"):
        it_template_id = it_upload_body["uploadedSamples"][0].get("templateId")
    operator_cross_status, _ = request("POST", f"/api/face-templates/{it_template_id}/process", token=operator_token)

    deactivate_status, deactivate_body = request("PATCH", f"/api/face-templates/{template_id}/deactivate", token=admin_token)
    clear_status, clear_body = request(
        "PATCH",
        f"/api/students/{second_cs_student_id}/face-enrollment/clear",
        token=admin_token,
    )

    process_template = process_body.get("template", {}) if isinstance(process_body, dict) else {}
    detected_face_encoding = process_template.get("status") == "Encoded" and template_has_encoding(template_id)
    encoding_data_saved = detected_face_encoding
    manual_real_face_test_required = not detected_face_encoding

    no_face_statuses = {"NoFaceDetected", "StoredNeedsReview"}
    results = {
        "health": health_status == 200 and isinstance(health_body, dict) and health_body.get("database") == "connected",
        "phase3_still_passed": phase3_passed,
        "phase4_still_passed": phase4_passed,
        "phase6a_still_passed": phase6a_passed,
        "phase6b_still_passed": phase6b_passed,
        "admin_login": admin_login_status == 200 and bool(admin_token),
        "operator_login": operator_login_status == 200 and bool(operator_token),
        "valid_image_upload": upload_status == 201 and bool(template_id) and upload_template_status in {"Encoded", *no_face_statuses},
        "unsupported_file_rejected": unsupported_status == 422,
        "empty_file_rejected": empty_status == 422,
        "face_processing_info": (
            info_status == 200
            and isinstance(info_body, dict)
            and info_body.get("provider") == "OpenCV"
            and info_body.get("encodingVersion") == "opencv_basic_v1"
            and info_body.get("recognitionMatchingImplemented") is True
            and info_body.get("livenessImplemented") is True
        ),
        "template_process_endpoint": process_status == 200 and process_template.get("status") in {"Encoded", *no_face_statuses},
        "student_process_all_endpoint": (
            process_all_status == 200
            and isinstance(process_all_body, dict)
            and {"processed", "noFaceDetected", "failed"}.issubset(process_all_body)
        ),
        "no_face_handled_gracefully": (
            processing_result.status in no_face_statuses
            and process_status == 200
            and process_template.get("status") in {"Encoded", *no_face_statuses}
        ),
        "operator_own_template_process": operator_upload_status == 201 and operator_process_status == 200,
        "operator_cross_department_blocked": it_upload_status == 201 and operator_cross_status == 403,
    }
    internal_checks = (
        invalid_decode_rejected
        and
        deactivate_status == 200
        and isinstance(deactivate_body, dict)
        and deactivate_body.get("isActive") is False
        and clear_status == 200
        and isinstance(clear_body, dict)
        and clear_body.get("deactivatedCount", 0) >= 1
    )
    results["phase7a_passed"] = all(results.values()) and internal_checks

    for name, passed in results.items():
        print(f"{name}={passed}")
    print(f"detected_face_encoding={detected_face_encoding}")
    if detected_face_encoding:
        print(f"encoding_data_saved={encoding_data_saved}")
    else:
        print(f"manual_real_face_test_required={manual_real_face_test_required}")

    if not results["phase7a_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
