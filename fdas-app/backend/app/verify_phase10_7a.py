from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
import onnxruntime

from app.config import (
    BASE_DIR,
    DEEP_FACE_EMBEDDING_DIMENSION,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_FACE_EXECUTION_PROVIDER,
    DEEP_FACE_MODEL_DIRECTORY,
    DEEP_FACE_MODEL_NAME,
    FACE_MATCH_THRESHOLD,
    IDENTITY_MATCHING_SAFETY_HOLD,
    MIN_IDENTITY_MARGIN,
)
from app.database import SessionLocal
from app.models.attendance_record import AttendanceRecord
from app.models.face_template import FaceTemplate
from app.models.user import User
from app.services.deep_face import (
    DeepFaceService,
    dry_run_template_encoding,
    resolve_template_image_path,
)
from app.services.face_processing import ENCODING_VERSION as LEGACY_ENCODING_VERSION
from app.services.face_processing import process_image_bytes


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"
SAMPLE_STUDENT_IDS = (22, 27, 28, 19, 26, 29)
REQUIRED_SUCCESS_STUDENT_IDS = (22, 27, 28, 19, 29)


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def login() -> str | None:
    code, body = request("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    return body.get("accessToken") if code == 200 else None


def blank_png() -> bytes:
    image = np.full((240, 320, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not create controlled blank image")
    return encoded.tobytes()


def template_state_digest(db) -> str:
    digest = hashlib.sha256()
    rows = db.query(FaceTemplate).order_by(FaceTemplate.templateId).all()
    for row in rows:
        digest.update(
            json.dumps(
                [
                    row.templateId,
                    row.studentId,
                    row.templatePath,
                    row.encodingVersion,
                    row.encodingData,
                    row.status,
                    row.isActive,
                ],
                separators=(",", ":"),
            ).encode("utf-8")
        )
    return digest.hexdigest()


def sample_dry_run(db, admin: User, student_id: int) -> tuple[dict | None, FaceTemplate | None, list[str]]:
    templates = (
        db.query(FaceTemplate)
        .filter(
            FaceTemplate.studentId == student_id,
            FaceTemplate.isActive.is_(True),
            FaceTemplate.templatePath.isnot(None),
        )
        .order_by(FaceTemplate.sampleIndex, FaceTemplate.templateId)
        .all()
    )
    statuses: list[str] = []
    for template in templates:
        image_path = resolve_template_image_path(template)
        if image_path is None or not image_path.is_file():
            statuses.append("ImageNotFound")
            continue
        result = dry_run_template_encoding(db, admin, template.templateId)
        statuses.append(result["status"])
        if result["success"]:
            return result, template, statuses
    return None, None, statuses


def main() -> None:
    import insightface

    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).one()
        attendance_before = db.query(AttendanceRecord).count()
        template_count_before = db.query(FaceTemplate).count()
        template_digest_before = template_state_digest(db)
        legacy_before = (
            db.query(FaceTemplate)
            .filter(
                FaceTemplate.isActive.is_(True),
                FaceTemplate.status == "Encoded",
                FaceTemplate.encodingVersion == LEGACY_ENCODING_VERSION,
                FaceTemplate.encodingData.isnot(None),
            )
            .count()
        )
        deep_before = (
            db.query(FaceTemplate)
            .filter(FaceTemplate.encodingVersion == DEEP_FACE_ENCODING_VERSION)
            .count()
        )

        service = DeepFaceService()
        with patch(
            "insightface.app.face_analysis.ensure_available",
            side_effect=AssertionError("runtime download attempted"),
        ) as downloader:
            first_application = service.initialize()
            second_application = service.initialize()

        import app.services.deep_face as deep_face_module

        sample_results: dict[int, dict] = {}
        sample_templates: dict[int, FaceTemplate] = {}
        sample_statuses: dict[int, list[str]] = {}
        with patch.object(deep_face_module, "_deep_face_service", service):
            for student_id in SAMPLE_STUDENT_IDS:
                result, template, statuses = sample_dry_run(db, admin, student_id)
                sample_statuses[student_id] = statuses
                if result is not None and template is not None:
                    sample_results[student_id] = result
                    sample_templates[student_id] = template

            deterministic_template = sample_templates.get(22) or next(iter(sample_templates.values()), None)
            if deterministic_template is not None:
                deterministic_path = resolve_template_image_path(deterministic_template)
                image_bytes = deterministic_path.read_bytes()
                repeat_one = service.encode_image_bytes(image_bytes)
                repeat_two = service.encode_image_bytes(image_bytes)
            else:
                repeat_one = None
                repeat_two = None

            no_face = service.encode_image_bytes(blank_png())
            with patch.object(
                deep_face_module,
                "detect_faces",
                return_value=[(10, 10, 80, 80), (140, 20, 75, 75)],
            ):
                multiple_faces = service.encode_image_bytes(blank_png())

            mismatch_service = DeepFaceService()
            mismatch_service._application = SimpleNamespace(get=lambda image, max_num=0: [])
            with patch.object(deep_face_module, "detect_faces", return_value=[(20, 20, 100, 100)]):
                mismatch = mismatch_service.encode_image_bytes(blank_png())

        template_digest_after_direct = template_state_digest(db)
        attendance_after_direct = db.query(AttendanceRecord).count()

    token = login()
    unauthenticated_info_code, _ = request("GET", "/api/deep-face/info")
    info_code, info_body = request("GET", "/api/deep-face/info", token=token)
    endpoint_template = sample_templates.get(22) or next(iter(sample_templates.values()), None)
    if endpoint_template is not None:
        dry_run_code, dry_run_body = request(
            "POST",
            f"/api/face-templates/{endpoint_template.templateId}/deep-encoding/dry-run",
            token=token,
        )
    else:
        dry_run_code, dry_run_body = 0, {}

    with SessionLocal() as db:
        attendance_after = db.query(AttendanceRecord).count()
        template_count_after = db.query(FaceTemplate).count()
        template_digest_after = template_state_digest(db)
        legacy_after = (
            db.query(FaceTemplate)
            .filter(
                FaceTemplate.isActive.is_(True),
                FaceTemplate.status == "Encoded",
                FaceTemplate.encodingVersion == LEGACY_ENCODING_VERSION,
                FaceTemplate.encodingData.isnot(None),
            )
            .count()
        )
        deep_after = (
            db.query(FaceTemplate)
            .filter(FaceTemplate.encodingVersion == DEEP_FACE_ENCODING_VERSION)
            .count()
        )

    recognition = first_application.models.get("recognition")
    recognition_session = getattr(recognition, "session", None)
    recognition_providers = recognition_session.get_providers() if recognition_session is not None else []
    recognition_output_shape = getattr(recognition, "output_shape", None)
    repeat_similarity = None
    if repeat_one is not None and repeat_two is not None and repeat_one.embedding is not None and repeat_two.embedding is not None:
        repeat_similarity = float(np.dot(repeat_one.embedding, repeat_two.embedding))

    for student_id in SAMPLE_STUDENT_IDS:
        print(
            f"student_{student_id}_dry_run="
            + json.dumps(sample_results.get(student_id) or {"success": False, "statuses": sample_statuses[student_id]})
        )

    results = {
        "insightface_import": insightface.__version__ == "2.0",
        "onnxruntime_import": onnxruntime.__version__ == "1.30.0",
        "cpu_provider_available": DEEP_FACE_EXECUTION_PROVIDER in onnxruntime.get_available_providers(),
        "local_model_files_present": all(
            (DEEP_FACE_MODEL_DIRECTORY / filename).is_file()
            for filename in ("det_10g.onnx", "w600k_r50.onnx")
        ),
        "automatic_download_not_used": downloader.call_count == 0,
        "model_initialized_once": first_application is second_application,
        "recognition_uses_cpu": recognition_providers and recognition_providers[0] == DEEP_FACE_EXECUTION_PROVIDER,
        "embedding_dimension_512": recognition_output_shape and int(recognition_output_shape[-1]) == 512,
        "all_required_student_samples_encoded": set(REQUIRED_SUCCESS_STUDENT_IDS).issubset(sample_results),
        "known_multiple_face_samples_rejected": (
            26 not in sample_results
            and bool(sample_statuses[26])
            and set(sample_statuses[26]) == {"MultipleFacesDetected"}
        ),
        "sample_metadata_safe": all(
            result.get("embeddingDimension") == 512
            and result.get("encodingVersion") == "arcface_v1"
            and abs(float(result.get("l2Norm")) - 1.0) <= 0.0001
            and result.get("attendanceCreated") is False
            and result.get("persistentWrite") is False
            and "embedding" not in result
            for result in sample_results.values()
        ),
        "repeat_encoding_deterministic": (
            repeat_one is not None
            and repeat_two is not None
            and repeat_one.success
            and repeat_two.success
            and repeat_similarity is not None
            and repeat_similarity >= 0.99999
        ),
        "no_face_rejected": no_face.status == "NoFaceDetected" and no_face.embedding is None,
        "multiple_faces_rejected": (
            multiple_faces.status == "MultipleFacesDetected" and multiple_faces.embedding is None
        ),
        "detector_mismatch_rejected": (
            mismatch.status == "FaceDetectionMismatch" and mismatch.embedding is None
        ),
        "encoding_version_separate": DEEP_FACE_ENCODING_VERSION == "arcface_v1" and LEGACY_ENCODING_VERSION == "opencv_basic_v1",
        "diagnostic_requires_auth": unauthenticated_info_code == 401,
        "capability_reports_available_not_active": (
            info_code == 200
            and info_body.get("deepRecognitionAvailable") is True
            and info_body.get("deepRecognitionReady") is True
            and info_body.get("activeForAttendance") is False
            and info_body.get("attendanceSafetyHold") is True
        ),
        "protected_dry_run_succeeds": (
            dry_run_code == 200
            and dry_run_body.get("success") is True
            and dry_run_body.get("embeddingDimension") == 512
            and "embedding" not in dry_run_body
        ),
        "direct_diagnostic_no_write": (
            template_digest_before == template_digest_after_direct
            and attendance_before == attendance_after_direct
        ),
        "endpoint_diagnostic_no_write": (
            template_count_before == template_count_after
            and template_digest_before == template_digest_after
            and attendance_before == attendance_after
        ),
        "legacy_templates_preserved": legacy_before == legacy_after and legacy_after > 0,
        "no_persistent_deep_templates": deep_before == 0 and deep_after == 0,
        "legacy_policy_unchanged": FACE_MATCH_THRESHOLD == 0.75 and MIN_IDENTITY_MARGIN == 0.05,
        "attendance_hold_active": IDENTITY_MATCHING_SAFETY_HOLD is True,
        "legacy_processing_still_operates": process_image_bytes(blank_png()).status == "NoFaceDetected",
    }
    results["phase10_7a_passed"] = all(bool(value) for value in results.values())
    print(f"model_initialization_milliseconds={service.initialization_milliseconds}")
    print(
        "repeat_processing_milliseconds="
        + json.dumps(
            [
                repeat_one.processingMilliseconds if repeat_one is not None else None,
                repeat_two.processingMilliseconds if repeat_two is not None else None,
            ]
        )
    )
    print(f"repeat_similarity={repeat_similarity}")
    for name, passed in results.items():
        print(f"{name}={bool(passed)}")
    if not results["phase10_7a_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
