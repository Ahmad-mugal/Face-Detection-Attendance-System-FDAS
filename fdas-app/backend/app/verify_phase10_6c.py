import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from fastapi import HTTPException

from app.config import FACE_CONTINUITY_MIN_SIMILARITY, FACE_MATCH_THRESHOLD, LIVENESS_FRAME_COUNT
from app.database import SessionLocal
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.face_template import FaceTemplate
from app.models.student import Student
from app.models.user import User
from app.routers.attendance_marking import mark_by_face_live
from app.services.face_enrollment import ensure_enrollment_face_continuity, ensure_exactly_one_face
from app.services.face_processing import process_image_bytes, validate_single_face_bytes
from app.services.liveness import LIVENESS_STATUS_FAILED, LivenessFrame, LivenessResult, evaluate_liveness_frames


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "admin@fdas.local"
ADMIN_PASSWORD = "Admin@12345"


class MemoryUpload:
    def __init__(self, content: bytes, index: int):
        self.filename = f"phase10_6c_{index}.png"
        self._content = content

    async def read(self) -> bytes:
        return self._content


def make_blank_png() -> bytes:
    image = np.full((160, 160, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not generate test PNG")
    return encoded.tobytes()


def request(method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def multipart_request(path: str, files: list[tuple[str, bytes]], token: str | None = None) -> tuple[int, dict]:
    boundary = "----FDASPhase106CSingleFaceBoundary"
    chunks: list[bytes] = []
    for field_name, (filename, content) in files:
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode()
        )
        chunks.append(b"Content-Type: image/png\r\n\r\n")
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=b"".join(chunks), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw) if raw else {}


def login() -> str | None:
    status_code, body = request("POST", "/api/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    return body.get("accessToken") if status_code == 200 else None


def controlled_frames() -> list[LivenessFrame]:
    boxes = (
        [(50, 50, 60, 60), (50, 50, 60, 60)]
        + [(54, 50, 60, 60), (60, 50, 60, 60), (68, 50, 60, 60), (72, 50, 60, 60), (70, 50, 60, 60), (68, 50, 60, 60), (66, 50, 60, 60)]
    )
    return [
        LivenessFrame(
            image_bytes=f"phase10-6c-{index}".encode(),
            width=200,
            height=200,
            face_count=1,
            face_box=box,
            face_descriptor=[1.0, 0.0, 0.0],
        )
        for index, box in enumerate(boxes)
    ]


def exception_code(callable_) -> str | None:
    try:
        callable_()
    except HTTPException as exc:
        return exc.detail.get("code") if isinstance(exc.detail, dict) else str(exc.detail)
    return None


def verify_router_short_circuit(blank_png: bytes) -> tuple[bool, bool]:
    with SessionLocal() as db:
        admin = db.query(User).filter(User.email == ADMIN_EMAIL).one()
        session = db.query(AttendanceSession).filter(AttendanceSession.status == "Active").first()
        if session is None:
            return False, False
        before = db.query(AttendanceRecord).count()
        failed = LivenessResult(
            passed=False,
            status="MultipleFacesDetected",
            message="Multiple faces detected.",
            livenessStatus=LIVENESS_STATUS_FAILED,
            diagnostics={"multipleFaceFrameCount": 1},
        )
        uploads = [MemoryUpload(blank_png, index) for index in range(LIVENESS_FRAME_COUNT)]
        with patch("app.routers.attendance_marking.verify_liveness", return_value=failed), patch(
            "app.routers.attendance_marking.match_face_bytes"
        ) as matcher:
            result = asyncio.run(
                mark_by_face_live(
                    sessionId=session.sessionId,
                    challengeType="MOVE_LEFT",
                    files=uploads,
                    current_user=admin,
                    db=db,
                )
            )
        after = db.query(AttendanceRecord).count()
        return matcher.call_count == 0, before == after and result.get("attendanceMarked") is False


def main() -> None:
    blank_png = make_blank_png()
    token = login()
    health_status, health_body = request("GET", "/health")

    unauthenticated_status, _ = multipart_request(
        "/api/face-processing/validate-single-face",
        [("file", ("blank.png", blank_png))],
    )
    no_face_status, no_face_body = multipart_request(
        "/api/face-processing/validate-single-face",
        [("file", ("blank.png", blank_png))],
        token,
    )

    with patch("app.services.face_processing.detect_faces", return_value=[]):
        zero_result = process_image_bytes(blank_png)
    with patch("app.services.face_processing.detect_faces", return_value=[(20, 20, 80, 80)]):
        single_result = process_image_bytes(blank_png)
        single_guard = validate_single_face_bytes(blank_png)
    with patch(
        "app.services.face_processing.detect_faces",
        return_value=[(5, 5, 60, 60), (90, 10, 55, 55)],
    ):
        multiple_result = process_image_bytes(blank_png)
        multiple_guard = validate_single_face_bytes(blank_png)

    no_face_code = exception_code(lambda: ensure_exactly_one_face(zero_result))
    multiple_face_code = exception_code(lambda: ensure_exactly_one_face(multiple_result))

    stable_results = [SimpleNamespace(encodingData=json.dumps([1.0, 0.0, 0.0])) for _ in range(25)]
    ensure_enrollment_face_continuity(stable_results)
    switched_results = stable_results[:12] + [
        SimpleNamespace(encodingData=json.dumps([0.0, 1.0, 0.0]))
    ] + stable_results[13:]
    continuity_code = exception_code(lambda: ensure_enrollment_face_continuity(switched_results))

    frames = controlled_frames()
    normal_liveness = evaluate_liveness_frames(frames, "MOVE_LEFT")
    multiple_frames = list(frames)
    multiple_frames[4] = replace(multiple_frames[4], face_count=2, face_box=None, face_descriptor=None)
    multiple_liveness = evaluate_liveness_frames(multiple_frames, "MOVE_LEFT")
    missing_frames = list(frames)
    missing_frames[4] = replace(missing_frames[4], face_count=0, face_box=None, face_descriptor=None)
    missing_liveness = evaluate_liveness_frames(missing_frames, "MOVE_LEFT")
    switched_frames = list(frames)
    switched_frames[5] = replace(switched_frames[5], face_descriptor=[0.0, 1.0, 0.0])
    switched_liveness = evaluate_liveness_frames(switched_frames, "MOVE_LEFT")

    with SessionLocal() as db:
        student = db.query(Student).filter(Student.departmentId == 1).order_by(Student.studentId).first()
        before_templates = db.query(FaceTemplate).filter(FaceTemplate.studentId == student.studentId).count()
    upload_files = [("files", (f"blank_{index}.png", blank_png)) for index in range(25)]
    rejected_status, rejected_body = multipart_request(
        f"/api/students/{student.studentId}/face-enrollment/upload",
        upload_files,
        token,
    )
    with SessionLocal() as db:
        after_templates = db.query(FaceTemplate).filter(FaceTemplate.studentId == student.studentId).count()

    matcher_skipped, attendance_unchanged = verify_router_short_circuit(blank_png)

    results = {
        "health": health_status == 200 and health_body.get("database") == "connected",
        "admin_login": bool(token),
        "face_threshold_unchanged": FACE_MATCH_THRESHOLD == 0.75,
        "single_face_endpoint_requires_auth": unauthenticated_status == 401,
        "no_face_endpoint_state": (
            no_face_status == 200
            and no_face_body.get("status") == "NoFaceDetected"
            and no_face_body.get("faceCount") == 0
            and no_face_body.get("ready") is False
        ),
        "zero_one_many_classification": (
            zero_result.faceCount == 0
            and single_result.faceCount == 1
            and single_result.status == "Encoded"
            and multiple_result.faceCount == 2
            and multiple_result.status == "MultipleFacesDetected"
        ),
        "single_face_ready_state": single_guard.get("status") == "SingleFaceDetected" and single_guard.get("ready") is True,
        "multiple_face_blocked_state": (
            multiple_guard.get("status") == "MultipleFacesDetected"
            and multiple_guard.get("ready") is False
        ),
        "enrollment_zero_face_rejected": no_face_code == "NoFaceDetected",
        "enrollment_multiple_faces_rejected": multiple_face_code == "MultipleFacesDetected",
        "enrollment_stable_subject_allowed": FACE_CONTINUITY_MIN_SIMILARITY == 0.10,
        "enrollment_subject_switch_rejected": continuity_code == "FaceContinuityLost",
        "enrollment_api_rejects_without_writes": (
            rejected_status == 422
            and rejected_body.get("detail", {}).get("code") == "NoFaceDetected"
            and before_templates == after_templates
        ),
        "single_face_liveness_still_operates": normal_liveness.passed is True,
        "liveness_multiple_faces_rejected": (
            multiple_liveness.passed is False and multiple_liveness.status == "MultipleFacesDetected"
        ),
        "liveness_missing_face_rejected": (
            missing_liveness.passed is False and missing_liveness.status == "NoFaceDetected"
        ),
        "liveness_subject_switch_rejected": (
            switched_liveness.passed is False and switched_liveness.status == "FaceContinuityLost"
        ),
        "multiple_faces_skip_matcher": matcher_skipped,
        "rejected_attempt_creates_no_attendance": attendance_unchanged,
    }
    results["phase10_6c_passed"] = all(results.values())
    for name, passed in results.items():
        print(f"{name}={passed}")
    if not results["phase10_6c_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
