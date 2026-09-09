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


def detect_largest_face(image) -> tuple[int, int, int, int] | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    detector = get_face_detector()
    faces = detector.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(24, 24),
    )
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda face: int(face[2]) * int(face[3]))
    return int(x), int(y), int(w), int(h)


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


def process_image_bytes(image_bytes: bytes) -> FaceProcessingResult:
    image = decode_image_bytes(image_bytes)
    face_box = detect_largest_face(image)
    processed_at = utc_now_naive()
    if face_box is None:
        return FaceProcessingResult(status="NoFaceDetected", processedAt=processed_at)

    descriptor = generate_basic_descriptor(crop_face(image, face_box))
    x, y, w, h = face_box
    return FaceProcessingResult(
        status="Encoded",
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
