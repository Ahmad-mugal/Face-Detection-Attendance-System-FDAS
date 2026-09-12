from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

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

        application = self.initialize()
        with self._inference_lock:
            deep_faces = application.get(image, max_num=0)
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
        "activeForAttendance": False,
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
