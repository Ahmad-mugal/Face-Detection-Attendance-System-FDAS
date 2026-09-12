import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException, status

from app.utils.time import utc_now_naive


PROCESSING_PROVIDER = "OpenCV"
ENCODING_VERSION = "opencv_basic_v1"
DESCRIPTOR_SIZE = (16, 16)


@dataclass
class FaceProcessingResult:
    status: str
    faceCount: int = 0
    encodingData: str | None = None
    encodingVersion: str | None = None
    faceBoxJson: str | None = None
    processedAt: datetime | None = None
    error: str | None = None


def decode_image_bytes(image_bytes: bytes):
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded file is empty")

    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid image file")
    return image


def load_image_bytes_from_path(image_path: Path) -> bytes:
    if not image_path.exists() or not image_path.is_file():
        raise FileNotFoundError("Stored image file not found")
    return image_path.read_bytes()


def get_face_detector():
    cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        raise RuntimeError("OpenCV Haar cascade could not be loaded")
    return detector


def detect_faces(image) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    detector = get_face_detector()
    faces = detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(24, 24),
    )
    normalized = [tuple(int(value) for value in face) for face in faces]
    return sorted(normalized, key=lambda face: face[2] * face[3], reverse=True)


def detect_largest_face(image) -> tuple[int, int, int, int] | None:
    faces = detect_faces(image)
    return faces[0] if faces else None


def crop_face(image, face_box: tuple[int, int, int, int]):
    x, y, w, h = face_box
    height, width = image.shape[:2]
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + w)
    y2 = min(height, y + h)
    return image[y1:y2, x1:x2]


def generate_basic_descriptor(face_crop) -> list[float]:
    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
    equalized = cv2.equalizeHist(gray)
    resized = cv2.resize(equalized, DESCRIPTOR_SIZE, interpolation=cv2.INTER_AREA)
    vector = resized.astype(np.float32).flatten()
    vector = vector - float(vector.mean())
    norm = float(np.linalg.norm(vector))
    if norm > 0:
        vector = vector / norm
    return [round(float(value), 6) for value in vector.tolist()]


def descriptor_similarity(leftVector: list[float], rightVector: list[float]) -> float:
    if len(leftVector) != len(rightVector) or not leftVector:
        return -1.0
    left = np.array(leftVector, dtype=np.float32)
    right = np.array(rightVector, dtype=np.float32)
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0 or right_norm == 0:
        return -1.0
    return round(float(np.dot(left, right) / (left_norm * right_norm)), 6)


def single_face_descriptor(image_bytes: bytes) -> tuple[int, list[float] | None, tuple[int, int, int, int] | None]:
    image = decode_image_bytes(image_bytes)
    faces = detect_faces(image)
    if len(faces) != 1:
        return len(faces), None, None
    face_box = faces[0]
    return 1, generate_basic_descriptor(crop_face(image, face_box)), face_box


def validate_single_face_bytes(image_bytes: bytes, reference_bytes: bytes | None = None) -> dict:
    from app.config import FACE_CONTINUITY_MIN_SIMILARITY

    face_count, descriptor, _ = single_face_descriptor(image_bytes)
    if face_count == 0:
        return {
            "status": "NoFaceDetected",
            "message": "No face detected. Please face the camera.",
            "faceCount": 0,
            "ready": False,
            "continuityPassed": None,
            "continuitySimilarity": None,
            "continuityThreshold": FACE_CONTINUITY_MIN_SIMILARITY,
        }
    if face_count > 1:
        return {
            "status": "MultipleFacesDetected",
            "message": "Multiple faces detected. Only one person should be in front of the camera.",
            "faceCount": face_count,
            "ready": False,
            "continuityPassed": None,
            "continuitySimilarity": None,
            "continuityThreshold": FACE_CONTINUITY_MIN_SIMILARITY,
        }

    similarity = None
    continuity_passed = None
    if reference_bytes is not None:
        reference_count, reference_descriptor, _ = single_face_descriptor(reference_bytes)
        if reference_count != 1 or reference_descriptor is None:
            return {
                "status": "FaceContinuityLost",
                "message": "The locked enrollment face is no longer available. Restart this enrollment attempt.",
                "faceCount": 1,
                "ready": False,
                "continuityPassed": False,
                "continuitySimilarity": None,
                "continuityThreshold": FACE_CONTINUITY_MIN_SIMILARITY,
            }
        similarity = descriptor_similarity(reference_descriptor, descriptor)
        continuity_passed = similarity >= FACE_CONTINUITY_MIN_SIMILARITY
        if not continuity_passed:
            return {
                "status": "FaceContinuityLost",
                "message": "The detected subject changed unexpectedly. Return the original person to the camera.",
                "faceCount": 1,
                "ready": False,
                "continuityPassed": False,
                "continuitySimilarity": similarity,
                "continuityThreshold": FACE_CONTINUITY_MIN_SIMILARITY,
            }

    return {
        "status": "SingleFaceDetected",
        "message": "Face detected — ready.",
        "faceCount": 1,
        "ready": True,
        "continuityPassed": continuity_passed,
        "continuitySimilarity": similarity,
        "continuityThreshold": FACE_CONTINUITY_MIN_SIMILARITY,
    }


def process_image_bytes(image_bytes: bytes) -> FaceProcessingResult:
    image = decode_image_bytes(image_bytes)
    faces = detect_faces(image)
    processed_at = utc_now_naive()
    if not faces:
        return FaceProcessingResult(status="NoFaceDetected", faceCount=0, processedAt=processed_at)
    if len(faces) > 1:
        return FaceProcessingResult(status="MultipleFacesDetected", faceCount=len(faces), processedAt=processed_at)

    face_box = faces[0]
    descriptor = generate_basic_descriptor(crop_face(image, face_box))
    x, y, w, h = face_box
    return FaceProcessingResult(
        status="Encoded",
        faceCount=1,
        encodingData=json.dumps(descriptor, separators=(",", ":")),
        encodingVersion=ENCODING_VERSION,
        faceBoxJson=json.dumps({"x": x, "y": y, "width": w, "height": h}, separators=(",", ":")),
        processedAt=processed_at,
    )


def processing_info() -> dict:
    return {
        "provider": PROCESSING_PROVIDER,
        "encodingVersion": ENCODING_VERSION,
        "recognitionMatchingImplemented": True,
        "livenessImplemented": True,
    }
