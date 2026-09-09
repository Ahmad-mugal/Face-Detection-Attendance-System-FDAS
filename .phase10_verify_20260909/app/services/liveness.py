from dataclasses import dataclass

from fastapi import HTTPException, UploadFile, status

from app.config import (
    LIVENESS_ALLOWED_CHALLENGES,
    LIVENESS_FRAME_COUNT,
    LIVENESS_MIN_AREA_CHANGE_RATIO,
    LIVENESS_MIN_CENTER_SHIFT_RATIO,
    LIVENESS_MODE,
)
from app.services.face_matching import MAX_FACE_IMAGE_BYTES, validate_match_upload_file
from app.services.face_processing import decode_image_bytes, detect_largest_face


LIVENESS_STATUS_PASSED = "Passed"
LIVENESS_STATUS_FAILED = "Failed"


@dataclass
class LivenessFrame:
    image_bytes: bytes
    width: int
    height: int
    face_box: tuple[int, int, int, int] | None


@dataclass
class LivenessResult:
    passed: bool
    status: str
    message: str
    livenessStatus: str
    bestFrameBytes: bytes | None = None


def validate_challenge(challengeType: str) -> str:
    challenge = (challengeType or "").strip().upper()
    if challenge not in LIVENESS_ALLOWED_CHALLENGES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid liveness challenge")
    return challenge


async def read_liveness_uploads(files: list[UploadFile]) -> list[bytes]:
    if len(files) < LIVENESS_FRAME_COUNT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"At least {LIVENESS_FRAME_COUNT} liveness frames are required",
        )

    frame_bytes: list[bytes] = []
    for file in files[:LIVENESS_FRAME_COUNT]:
        validate_match_upload_file(file)
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded liveness frame is empty")
        if len(content) > MAX_FACE_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded liveness frame is larger than the 5 MB limit",
            )
        frame_bytes.append(content)
    return frame_bytes


def analyze_liveness_frames(frame_bytes: list[bytes]) -> list[LivenessFrame]:
    frames: list[LivenessFrame] = []
    for content in frame_bytes:
        image = decode_image_bytes(content)
        height, width = image.shape[:2]
        frames.append(
            LivenessFrame(
                image_bytes=content,
                width=width,
                height=height,
                face_box=detect_largest_face(image),
            )
        )
    return frames


def face_center_x(face_box: tuple[int, int, int, int]) -> float:
    x, _, width, _ = face_box
    return float(x) + (float(width) / 2.0)


def face_area(face_box: tuple[int, int, int, int]) -> float:
    _, _, width, height = face_box
    return float(width) * float(height)


def evaluate_liveness_frames(frames: list[LivenessFrame], challengeType: str) -> LivenessResult:
    challenge = validate_challenge(challengeType)
    detected_frames = [frame for frame in frames if frame.face_box is not None]
    if len(detected_frames) < 2:
        return LivenessResult(
            passed=False,
            status="NoFaceDetected",
            message="No face was detected clearly enough for liveness checking.",
            livenessStatus=LIVENESS_STATUS_FAILED,
        )

    first = detected_frames[0]
    last = detected_frames[-1]
    assert first.face_box is not None
    assert last.face_box is not None

    if challenge == "MOVE_LEFT":
        shift_ratio = (face_center_x(last.face_box) - face_center_x(first.face_box)) / max(float(first.width), 1.0)
        passed = shift_ratio <= -LIVENESS_MIN_CENTER_SHIFT_RATIO
        detail = "Move face slightly left"
    elif challenge == "MOVE_RIGHT":
        shift_ratio = (face_center_x(last.face_box) - face_center_x(first.face_box)) / max(float(first.width), 1.0)
        passed = shift_ratio >= LIVENESS_MIN_CENTER_SHIFT_RATIO
        detail = "Move face slightly right"
    else:
        first_area = max(face_area(first.face_box), 1.0)
        area_change_ratio = (face_area(last.face_box) - first_area) / first_area
        passed = area_change_ratio >= LIVENESS_MIN_AREA_CHANGE_RATIO
        detail = "Move closer to camera"

    if not passed:
        return LivenessResult(
            passed=False,
            status="LivenessFailed",
            message=f"Liveness challenge failed. Please retry: {detail}.",
            livenessStatus=LIVENESS_STATUS_FAILED,
        )

    return LivenessResult(
        passed=True,
        status="LivenessPassed",
        message="Liveness challenge passed.",
        livenessStatus=LIVENESS_STATUS_PASSED,
        bestFrameBytes=last.image_bytes,
    )


def verify_liveness(frame_bytes: list[bytes], challengeType: str) -> LivenessResult:
    return evaluate_liveness_frames(analyze_liveness_frames(frame_bytes), challengeType)


def liveness_info() -> dict:
    return {
        "mode": LIVENESS_MODE,
        "frameCount": LIVENESS_FRAME_COUNT,
        "allowedChallenges": LIVENESS_ALLOWED_CHALLENGES,
        "minCenterShiftRatio": LIVENESS_MIN_CENTER_SHIFT_RATIO,
        "minAreaChangeRatio": LIVENESS_MIN_AREA_CHANGE_RATIO,
        "productionGradePad": False,
        "notes": "Basic movement challenge-response liveness foundation only; not certified production-grade presentation attack detection.",
    }
