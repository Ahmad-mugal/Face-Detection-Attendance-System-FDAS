from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import (
    BASE_DIR,
    DEEP_FACE_EMBEDDING_DIMENSION,
    DEEP_FACE_ENCODING_VERSION,
    DEEP_FACE_EXECUTION_PROVIDER,
    DEEP_FACE_MODEL_DIRECTORY,
    DEEP_FACE_MODEL_NAME,
    DEEP_FAST_QUERY_MIN_FACE_AREA_RATIO,
    DEEP_QUERY_MAX_BRIGHTNESS,
    DEEP_QUERY_MIN_BLUR_VARIANCE,
    DEEP_QUERY_MIN_BRIGHTNESS,
    DEEP_QUERY_MIN_EDGE_CLEARANCE_RATIO,
    DEEP_QUERY_MIN_FACE_AREA_RATIO,
    DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID,
    DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED,
    DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
    DEEP_RECOGNITION_INTEGRATED_FOR_ATTENDANCE,
    IDENTITY_MATCHING_SAFETY_HOLD,
)
from app.models.face_template import FaceTemplate
from app.models.user import User
from app.services.face_enrollment import STORAGE_ABSOLUTE_ROOT, ensure_template_access, get_face_template_or_404
from app.services.face_processing import decode_image_bytes, detect_faces, load_image_bytes_from_path


DEEP_FACE_PROVIDER = "InsightFace"
REQUIRED_MODEL_FILES = ("det_10g.onnx", "w600k_r50.onnx")


class DeepFaceInitializationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeepEncodingResult:
    success: bool
    status: str
    message: str
    haarFaceCount: int
    deepFaceCount: int | None
    embeddingDimension: int | None
    l2Norm: float | None
    processingMilliseconds: float
    embedding: np.ndarray | None = field(default=None, repr=False)
    faceBox: tuple[int, int, int, int] | None = None
    quality: dict[str, bool | float | str] | None = None
    haarBackgroundFalsePositiveReconciled: bool = False


@dataclass(frozen=True)
class FastFaceEncoding:
    faceIndex: int
    faceBox: tuple[int, int, int, int]
    detectionScore: float
    status: str
    message: str
    quality: dict[str, bool | float | str]
    embedding: np.ndarray | None = field(default=None, repr=False)


@dataclass(frozen=True)
class FastFrameEncoding:
    sourceWidth: int
    sourceHeight: int
    faces: tuple[FastFaceEncoding, ...]
    rawDetectionCount: int
    duplicateDetectionCount: int
    invalidDetectionCount: int
    decodeMilliseconds: float
    detectorMilliseconds: float
    alignmentMilliseconds: float
    embeddingMilliseconds: float
    totalMilliseconds: float


class DeepFaceService:
    def __init__(self, model_directory: Path = DEEP_FACE_MODEL_DIRECTORY):
        self.model_directory = Path(model_directory).resolve()
        self._application = None
        self._initialization_error: str | None = None
        self._initialization_milliseconds: float | None = None
        self._initialization_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._application is not None

    @property
    def initialization_milliseconds(self) -> float | None:
        return self._initialization_milliseconds

    @property
    def initialization_error(self) -> str | None:
        return self._initialization_error

    def model_files_available(self) -> bool:
        return self.model_directory.is_dir() and all(
            (self.model_directory / filename).is_file()
            for filename in REQUIRED_MODEL_FILES
        )

    def initialize(self):
        if self._application is not None:
            return self._application

        with self._initialization_lock:
            if self._application is not None:
                return self._application
            if not self.model_files_available():
                missing = [
                    filename
                    for filename in REQUIRED_MODEL_FILES
                    if not (self.model_directory / filename).is_file()
                ]
                self._initialization_error = (
                    "Required local InsightFace model files are missing: "
                    + ", ".join(missing)
                )
                raise DeepFaceInitializationError(self._initialization_error)

            started = time.perf_counter()
            try:
                from insightface.app import FaceAnalysis

                application = FaceAnalysis(
                    name=str(self.model_directory),
                    allowed_modules=["detection", "recognition"],
                    providers=[DEEP_FACE_EXECUTION_PROVIDER],
                )
                application.prepare(ctx_id=-1, det_size=(640, 640))

                recognition_model = application.models.get("recognition")
                detection_model = application.models.get("detection")
                if recognition_model is None or detection_model is None:
                    raise DeepFaceInitializationError(
                        "The local model directory did not provide detection and recognition models."
                    )
                output_shape = getattr(recognition_model, "output_shape", None)
                if not output_shape or int(output_shape[-1]) != DEEP_FACE_EMBEDDING_DIMENSION:
                    raise DeepFaceInitializationError(
                        f"Expected {DEEP_FACE_EMBEDDING_DIMENSION}-dimensional embeddings; found {output_shape}."
                    )
                for task_name in ("detection", "recognition"):
                    model = application.models[task_name]
                    session = getattr(model, "session", None)
                    providers = session.get_providers() if session is not None else []
                    if not providers or providers[0] != DEEP_FACE_EXECUTION_PROVIDER:
                        raise DeepFaceInitializationError(
                            f"{task_name} model did not initialize with {DEEP_FACE_EXECUTION_PROVIDER}."
                        )

                self._application = application
                self._initialization_error = None
                self._initialization_milliseconds = round(
                    (time.perf_counter() - started) * 1000.0,
                    3,
                )
                return application
            except Exception as exc:
                self._initialization_error = str(exc)
                if isinstance(exc, DeepFaceInitializationError):
                    raise
                raise DeepFaceInitializationError(
                    f"Deep recognition initialization failed: {exc}"
                ) from exc

    def get_deep_faces(self, image: np.ndarray):
        application = self.initialize()
        with self._inference_lock:
            return application.get(image, max_num=0)

    def detect_face_boxes(self, image: np.ndarray) -> list[tuple[int, int, int, int]]:
        height, width = image.shape[:2]
        boxes: list[tuple[int, int, int, int]] = []
        for face in self.get_deep_faces(image):
            left, top, right, bottom = [float(value) for value in face.bbox[:4]]
            x1 = max(0, min(width - 1, int(round(left))))
            y1 = max(0, min(height - 1, int(round(top))))
            x2 = max(x1 + 1, min(width, int(round(right))))
            y2 = max(y1 + 1, min(height, int(round(bottom))))
            boxes.append((x1, y1, x2 - x1, y2 - y1))
        return boxes

    @staticmethod
    def _clamp_face_box(
        raw_box,
        frame_width: int,
        frame_height: int,
    ) -> tuple[int, int, int, int] | None:
        if raw_box is None or len(raw_box) < 4:
            return None
        values = np.asarray(raw_box[:4], dtype=np.float64)
        if values.size != 4 or not np.all(np.isfinite(values)):
            return None
        left, top, right, bottom = [float(value) for value in values]
        if right <= left or bottom <= top:
            return None
        x1 = max(0, min(frame_width - 1, int(round(left))))
        y1 = max(0, min(frame_height - 1, int(round(top))))
        x2 = max(x1 + 1, min(frame_width, int(round(right))))
        y2 = max(y1 + 1, min(frame_height, int(round(bottom))))
        if x2 <= x1 or y2 <= y1:
            return None
        return x1, y1, x2 - x1, y2 - y1

    @staticmethod
    def _box_iou(
        left_box: tuple[int, int, int, int],
        right_box: tuple[int, int, int, int],
    ) -> float:
        left_x, left_y, left_width, left_height = left_box
        right_x, right_y, right_width, right_height = right_box
        intersection_left = max(left_x, right_x)
        intersection_top = max(left_y, right_y)
        intersection_right = min(left_x + left_width, right_x + right_width)
        intersection_bottom = min(left_y + left_height, right_y + right_height)
        intersection_width = max(0, intersection_right - intersection_left)
        intersection_height = max(0, intersection_bottom - intersection_top)
        intersection_area = float(intersection_width * intersection_height)
        union_area = float(
            (left_width * left_height)
            + (right_width * right_height)
            - intersection_area
        )
        return intersection_area / union_area if union_area > 0 else 0.0

    def encode_fast_attendance_frame_bytes(self, image_bytes: bytes) -> FastFrameEncoding:
        """Detect once and batch-encode every quality-eligible face in a frame."""
        started = time.perf_counter()
        decode_started = time.perf_counter()
        image = decode_image_bytes(image_bytes)
        decode_milliseconds = (time.perf_counter() - decode_started) * 1000.0
        frame_height, frame_width = image.shape[:2]
        application = self.initialize()

        with self._inference_lock:
            detector_started = time.perf_counter()
            raw_boxes, raw_landmarks = application.det_model.detect(image, max_num=0)
            detector_milliseconds = (time.perf_counter() - detector_started) * 1000.0

            raw_detection_count = int(raw_boxes.shape[0]) if raw_boxes is not None else 0
            detections: list[dict] = []
            invalid_detection_count = 0
            for index in range(raw_detection_count):
                face_box = self._clamp_face_box(raw_boxes[index, :4], frame_width, frame_height)
                landmarks = raw_landmarks[index] if raw_landmarks is not None else None
                if face_box is None or landmarks is None or not np.all(np.isfinite(landmarks)):
                    invalid_detection_count += 1
                    continue
                raw_score = float(raw_boxes[index, 4]) if raw_boxes.shape[1] > 4 else 0.0
                detection_score = raw_score if np.isfinite(raw_score) else 0.0
                detections.append(
                    {
                        "faceBox": face_box,
                        "landmarks": landmarks,
                        "detectionScore": detection_score,
                    }
                )

            detections.sort(key=lambda item: -item["detectionScore"])
            unique_detections: list[dict] = []
            duplicate_detection_count = 0
            for detection in detections:
                if any(
                    self._box_iou(detection["faceBox"], existing["faceBox"]) >= 0.85
                    for existing in unique_detections
                ):
                    duplicate_detection_count += 1
                    continue
                unique_detections.append(detection)
            unique_detections.sort(
                key=lambda item: (
                    item["faceBox"][0],
                    item["faceBox"][1],
                    -item["faceBox"][2] * item["faceBox"][3],
                )
            )

            face_rows: list[dict] = []
            eligible_rows: list[tuple[int, dict]] = []
            for face_index, detection in enumerate(unique_detections, start=1):
                quality = self._query_quality(
                    image,
                    detection["faceBox"],
                    minimum_face_area_ratio=DEEP_FAST_QUERY_MIN_FACE_AREA_RATIO,
                )
                row = {
                    **detection,
                    "faceIndex": face_index,
                    "quality": quality,
                    "status": "Ready" if quality["passed"] else "PoorFaceQuality",
                    "message": (
                        "Face is ready for ArcFace matching."
                        if quality["passed"]
                        else f"Face quality needs a fresh capture: {quality['reason']}."
                    ),
                    "embedding": None,
                }
                face_rows.append(row)
                if quality["passed"]:
                    eligible_rows.append((len(face_rows) - 1, row))

            alignment_milliseconds = 0.0
            embedding_milliseconds = 0.0
            if eligible_rows:
                from insightface.utils import face_align

                recognition_model = application.models["recognition"]
                alignment_started = time.perf_counter()
                aligned_faces = [
                    face_align.norm_crop(
                        image,
                        landmark=row["landmarks"],
                        image_size=recognition_model.input_size[0],
                    )
                    for _row_index, row in eligible_rows
                ]
                alignment_milliseconds = (time.perf_counter() - alignment_started) * 1000.0
                embedding_started = time.perf_counter()
                raw_embeddings = recognition_model.get_feat(aligned_faces)
                embedding_milliseconds = (time.perf_counter() - embedding_started) * 1000.0

                for embedding_index, (row_index, row) in enumerate(eligible_rows):
                    raw_embedding = np.asarray(raw_embeddings[embedding_index], dtype=np.float32).reshape(-1)
                    norm = float(np.linalg.norm(raw_embedding))
                    if (
                        raw_embedding.size != DEEP_FACE_EMBEDDING_DIMENSION
                        or not np.all(np.isfinite(raw_embedding))
                        or norm <= 0.0
                        or not np.isfinite(norm)
                    ):
                        face_rows[row_index] = {
                            **row,
                            "status": "InvalidEmbedding",
                            "message": "The deep model returned an invalid embedding for this face.",
                        }
                        continue
                    face_rows[row_index]["embedding"] = raw_embedding / norm

        faces = tuple(
            FastFaceEncoding(
                faceIndex=row["faceIndex"],
                faceBox=row["faceBox"],
                detectionScore=round(float(row["detectionScore"]), 6),
                status=row["status"],
                message=row["message"],
                quality=row["quality"],
                embedding=row["embedding"],
            )
            for row in face_rows
        )
        return FastFrameEncoding(
            sourceWidth=frame_width,
            sourceHeight=frame_height,
            faces=faces,
            rawDetectionCount=raw_detection_count,
            duplicateDetectionCount=duplicate_detection_count,
            invalidDetectionCount=invalid_detection_count,
            decodeMilliseconds=round(decode_milliseconds, 3),
            detectorMilliseconds=round(detector_milliseconds, 3),
            alignmentMilliseconds=round(alignment_milliseconds, 3),
            embeddingMilliseconds=round(embedding_milliseconds, 3),
            totalMilliseconds=round((time.perf_counter() - started) * 1000.0, 3),
        )

    @staticmethod
    def _query_quality(
        image: np.ndarray,
        face_box: tuple[int, int, int, int],
        *,
        minimum_face_area_ratio: float = DEEP_QUERY_MIN_FACE_AREA_RATIO,
    ) -> dict[str, bool | float | str]:
        frame_height, frame_width = image.shape[:2]
        x, y, width, height = face_box
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        crop = gray[y:y + height, x:x + width]
        frame_area = max(float(frame_width * frame_height), 1.0)
        shortest_side = max(float(min(frame_width, frame_height)), 1.0)
        area_ratio = float(width * height) / frame_area
        blur_variance = float(cv2.Laplacian(crop, cv2.CV_64F).var()) if crop.size else 0.0
        brightness = float(crop.mean()) if crop.size else 0.0
        edge_clearance = float(min(x, y, frame_width - (x + width), frame_height - (y + height))) / shortest_side
        failures: list[str] = []
        if area_ratio < minimum_face_area_ratio:
            failures.append("face_too_small")
        if blur_variance < DEEP_QUERY_MIN_BLUR_VARIANCE:
            failures.append("blurred")
        if brightness < DEEP_QUERY_MIN_BRIGHTNESS:
            failures.append("too_dark")
        if brightness > DEEP_QUERY_MAX_BRIGHTNESS:
            failures.append("too_bright")
        if edge_clearance < DEEP_QUERY_MIN_EDGE_CLEARANCE_RATIO:
            failures.append("face_near_edge")
        return {
            "passed": not failures,
            "reason": ",".join(failures) if failures else "quality_checks_passed",
            "faceAreaRatio": round(area_ratio, 6),
            "minimumFaceAreaRatio": minimum_face_area_ratio,
            "blurVariance": round(blur_variance, 3),
            "minimumBlurVariance": DEEP_QUERY_MIN_BLUR_VARIANCE,
            "brightness": round(brightness, 3),
            "minimumBrightness": DEEP_QUERY_MIN_BRIGHTNESS,
            "maximumBrightness": DEEP_QUERY_MAX_BRIGHTNESS,
            "edgeClearanceRatio": round(edge_clearance, 6),
            "minimumEdgeClearanceRatio": DEEP_QUERY_MIN_EDGE_CLEARANCE_RATIO,
        }

    def encode_image_bytes(self, image_bytes: bytes) -> DeepEncodingResult:
        started = time.perf_counter()
        image = decode_image_bytes(image_bytes)
        haar_faces = detect_faces(image)
        haar_count = len(haar_faces)
        if haar_count == 0:
            return self._failure(
                "NoFaceDetected",
                "No face detected.",
                haar_count,
                None,
                started,
            )
        if haar_count > 1:
            return self._failure(
                "MultipleFacesDetected",
                "Multiple faces detected. Exactly one face is required.",
                haar_count,
                None,
                started,
            )

        deep_faces = self.get_deep_faces(image)
        deep_count = len(deep_faces)
        if deep_count != haar_count:
            return self._failure(
                "FaceDetectionMismatch",
                "Haar and deep face detectors disagree. Processing stopped safely.",
                haar_count,
                deep_count,
                started,
            )
        if deep_count != 1:
            return self._failure(
                "FaceDetectionMismatch",
                "Deep face count is uncertain. Processing stopped safely.",
                haar_count,
                deep_count,
                started,
            )

        raw_embedding = np.asarray(deep_faces[0].embedding, dtype=np.float32).reshape(-1)
        if raw_embedding.size != DEEP_FACE_EMBEDDING_DIMENSION or not np.all(np.isfinite(raw_embedding)):
            return self._failure(
                "InvalidEmbedding",
                "The deep model returned an invalid embedding.",
                haar_count,
                deep_count,
                started,
            )
        norm = float(np.linalg.norm(raw_embedding))
        if norm <= 0.0 or not np.isfinite(norm):
            return self._failure(
                "InvalidEmbedding",
                "The deep model returned a zero or non-finite embedding.",
                haar_count,
                deep_count,
                started,
            )
        embedding = raw_embedding / norm
        normalized_norm = float(np.linalg.norm(embedding))
        return DeepEncodingResult(
            success=True,
            status="Encoded",
            message="Deep embedding generated in dry-run mode without persistence.",
            haarFaceCount=haar_count,
            deepFaceCount=deep_count,
            embeddingDimension=int(embedding.size),
            l2Norm=round(normalized_norm, 6),
            processingMilliseconds=round((time.perf_counter() - started) * 1000.0, 3),
            embedding=embedding,
        )

    def encode_attendance_query_bytes(self, image_bytes: bytes) -> DeepEncodingResult:
        """Encode one quality-gated query using SCRFD as the final face-count authority."""
        started = time.perf_counter()
        image = decode_image_bytes(image_bytes)
        haar_faces = detect_faces(image)
        haar_count = len(haar_faces)
        if haar_count == 0:
            return self._failure("NoFaceDetected", "No face detected.", 0, None, started)

        deep_faces = self.get_deep_faces(image)
        deep_count = len(deep_faces)
        if deep_count > 1:
            return self._failure(
                "MultipleFacesDetected",
                "Multiple genuine faces detected. Exactly one person is required.",
                haar_count,
                deep_count,
                started,
            )
        if deep_count != 1:
            return self._failure(
                "FaceDetectionMismatch",
                "The deep detector could not confirm exactly one face.",
                haar_count,
                deep_count,
                started,
            )

        height, width = image.shape[:2]
        left, top, right, bottom = [float(value) for value in deep_faces[0].bbox[:4]]
        x1 = max(0, min(width - 1, int(round(left))))
        y1 = max(0, min(height - 1, int(round(top))))
        x2 = max(x1 + 1, min(width, int(round(right))))
        y2 = max(y1 + 1, min(height, int(round(bottom))))
        face_box = (x1, y1, x2 - x1, y2 - y1)
        quality = self._query_quality(image, face_box)
        reconciled = haar_count > 1
        if not quality["passed"]:
            return DeepEncodingResult(
                success=False,
                status="PoorFaceQuality",
                message=f"Face quality needs a fresh capture: {quality['reason']}.",
                haarFaceCount=haar_count,
                deepFaceCount=deep_count,
                embeddingDimension=None,
                l2Norm=None,
                processingMilliseconds=round((time.perf_counter() - started) * 1000.0, 3),
                faceBox=face_box,
                quality=quality,
                haarBackgroundFalsePositiveReconciled=reconciled,
            )

        raw_embedding = np.asarray(deep_faces[0].embedding, dtype=np.float32).reshape(-1)
        if raw_embedding.size != DEEP_FACE_EMBEDDING_DIMENSION or not np.all(np.isfinite(raw_embedding)):
            return self._failure("InvalidEmbedding", "The deep model returned an invalid embedding.", haar_count, deep_count, started)
        norm = float(np.linalg.norm(raw_embedding))
        if norm <= 0.0 or not np.isfinite(norm):
            return self._failure("InvalidEmbedding", "The deep model returned a zero or non-finite embedding.", haar_count, deep_count, started)
        embedding = raw_embedding / norm
        return DeepEncodingResult(
            success=True,
            status="Encoded",
            message="Quality-gated ArcFace attendance query generated.",
            haarFaceCount=haar_count,
            deepFaceCount=deep_count,
            embeddingDimension=int(embedding.size),
            l2Norm=round(float(np.linalg.norm(embedding)), 6),
            processingMilliseconds=round((time.perf_counter() - started) * 1000.0, 3),
            embedding=embedding,
            faceBox=face_box,
            quality=quality,
            haarBackgroundFalsePositiveReconciled=reconciled,
        )

    @staticmethod
    def _failure(
        status_name: str,
        message: str,
        haar_count: int,
        deep_count: int | None,
        started: float,
    ) -> DeepEncodingResult:
        return DeepEncodingResult(
            success=False,
            status=status_name,
            message=message,
            haarFaceCount=haar_count,
            deepFaceCount=deep_count,
            embeddingDimension=None,
            l2Norm=None,
            processingMilliseconds=round((time.perf_counter() - started) * 1000.0, 3),
        )


_deep_face_service = DeepFaceService()


def get_deep_face_service() -> DeepFaceService:
    return _deep_face_service


def deep_face_capability(*, initialize: bool = False) -> dict:
    service = get_deep_face_service()
    if initialize:
        try:
            service.initialize()
        except DeepFaceInitializationError:
            pass
    return {
        "deepRecognitionAvailable": service.model_files_available(),
        "deepRecognitionProvider": DEEP_FACE_PROVIDER,
        "deepRecognitionModel": DEEP_FACE_MODEL_NAME,
        "deepEmbeddingDimension": DEEP_FACE_EMBEDDING_DIMENSION,
        "deepRecognitionExecutionProvider": DEEP_FACE_EXECUTION_PROVIDER,
        "deepRecognitionReady": service.ready,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "integratedForAttendance": DEEP_RECOGNITION_INTEGRATED_FOR_ATTENDANCE,
        "activeForAttendance": DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE,
        "controlledAttendanceEnabled": DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED,
        "controlledAttendanceStudentId": DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID,
        "attendanceSafetyHold": IDENTITY_MATCHING_SAFETY_HOLD,
        "modelDirectory": str(service.model_directory),
        "initializationMilliseconds": service.initialization_milliseconds,
        "error": service.initialization_error,
    }


def resolve_template_image_path(template: FaceTemplate) -> Path | None:
    if not template.templatePath:
        return None
    candidate = (BASE_DIR / Path(template.templatePath)).resolve()
    owner_root = (STORAGE_ABSOLUTE_ROOT / str(template.studentId)).resolve()
    try:
        candidate.relative_to(owner_root)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TemplateOwnershipMismatch",
                "message": "The stored template path does not belong to this student.",
            },
        )
    return candidate


def dry_run_template_encoding(
    db: Session,
    user: User,
    template_id: int,
) -> dict:
    template = get_face_template_or_404(db, template_id)
    ensure_template_access(user, template)
    image_path = resolve_template_image_path(template)
    if image_path is None or not image_path.is_file():
        return {
            "success": False,
            "status": "ImageNotFound",
            "message": "The stored enrollment image is unavailable.",
            "templateId": template.templateId,
            "studentId": template.studentId,
            "imageFound": False,
            "encodingVersion": DEEP_FACE_ENCODING_VERSION,
            "model": DEEP_FACE_MODEL_NAME,
            "executionProvider": DEEP_FACE_EXECUTION_PROVIDER,
            "attendanceCreated": False,
            "persistentWrite": False,
        }

    image_bytes = load_image_bytes_from_path(image_path)
    result = get_deep_face_service().encode_image_bytes(image_bytes)
    return {
        "success": result.success,
        "status": result.status,
        "message": result.message,
        "templateId": template.templateId,
        "studentId": template.studentId,
        "imageFound": True,
        "haarFaceCount": result.haarFaceCount,
        "deepFaceCount": result.deepFaceCount,
        "embeddingDimension": result.embeddingDimension,
        "encodingVersion": DEEP_FACE_ENCODING_VERSION,
        "l2Norm": result.l2Norm,
        "processingMilliseconds": result.processingMilliseconds,
        "model": DEEP_FACE_MODEL_NAME,
        "executionProvider": DEEP_FACE_EXECUTION_PROVIDER,
        "attendanceCreated": False,
        "persistentWrite": False,
    }
