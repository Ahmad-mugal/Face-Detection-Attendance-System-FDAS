import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"


def load_local_environment(environment_file: Path = ENV_FILE) -> bool:
    """Load optional local configuration without overriding host variables."""
    return load_dotenv(dotenv_path=environment_file, override=False)


load_local_environment()
DATABASE_FILE = BASE_DIR / "fdas_local.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE.as_posix()}"
CORS_ALLOWED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
CORS_ALLOWED_ORIGINS.extend(
    origin.strip()
    for origin in os.getenv("FDAS_EXTRA_CORS_ORIGINS", "").split(",")
    if origin.strip()
)

APP_NAME = "FDAS Backend"
APP_VERSION = "1.0.4"
APP_PHASE = "Phase 10.12D - Notifications, Safe Deletion, and Student Import"
FACE_MATCH_THRESHOLD = 0.75
FACE_MATCH_AGGREGATION = "maximum"
MIN_IDENTITY_MARGIN = 0.05
IDENTITY_MATCHING_SAFETY_HOLD = False
FACE_CONTINUITY_MIN_SIMILARITY = 0.10
DEEP_FACE_MODEL_NAME = "buffalo_l"
DEEP_FACE_ENCODING_VERSION = "arcface_v1"
DEEP_FACE_EMBEDDING_DIMENSION = 512
DEEP_FACE_EXECUTION_PROVIDER = "CPUExecutionProvider"
DEEP_ENROLLMENT_MIN_EMBEDDINGS = 20
DEEP_MATCH_SCORING_METHOD = "mean_top_3"
DEEP_MATCH_THRESHOLD = 0.85
DEEP_MATCH_MIN_IDENTITY_MARGIN = 0.07
DEEP_CONTROLLED_MATCH_THRESHOLD = 0.80
DEEP_CONTROLLED_MATCH_MIN_IDENTITY_MARGIN = 0.10
DEEP_MATCH_CALIBRATION_LABEL = "preliminary_fyp_v1"
DEEP_QUERY_BURST_COUNT = 3
DEEP_QUERY_CONSENSUS_MIN_COUNT = 2
DEEP_QUERY_MAX_RETRIES = 2
DEEP_QUERY_MIN_FACE_AREA_RATIO = 0.05
DEEP_QUERY_MIN_BLUR_VARIANCE = 50.0
DEEP_QUERY_MIN_BRIGHTNESS = 45.0
DEEP_QUERY_MAX_BRIGHTNESS = 210.0
DEEP_QUERY_MIN_EDGE_CLEARANCE_RATIO = 0.02
DEEP_RECOGNITION_INTEGRATED_FOR_ATTENDANCE = True
DEEP_RECOGNITION_ACTIVE_FOR_ATTENDANCE = True
DEEP_ATTENDANCE_CONTROLLED_TEST_ENABLED = os.getenv(
    "FDAS_DEEP_ATTENDANCE_CONTROLLED_TEST",
    # Fail closed unless the explicitly scoped local reliability launcher sets
    # this flag for its Uvicorn child process.
    "false",
).strip().lower() in {"1", "true", "yes", "on"}
DEEP_ATTENDANCE_CONTROLLED_STUDENT_ID = 22
DEEP_FACE_MODEL_DIRECTORY = Path(
    os.getenv("FDAS_DEEP_FACE_MODEL_DIR")
    or BASE_DIR / "models" / "insightface" / DEEP_FACE_MODEL_NAME
).resolve()
LIVENESS_MODE = "basic"
LIVENESS_BASELINE_FRAME_COUNT = 2
LIVENESS_MOVEMENT_FRAME_COUNT = 10
LIVENESS_FRAME_COUNT = LIVENESS_BASELINE_FRAME_COUNT + LIVENESS_MOVEMENT_FRAME_COUNT
LIVENESS_MIN_BASELINE_DETECTED_FRAMES = 2
LIVENESS_MIN_MOVEMENT_DETECTED_FRAMES = 4
LIVENESS_MIN_DIRECTIONAL_FRAME_COUNT = 2
LIVENESS_PREVIEW_MIRRORED = True
LIVENESS_MIN_CENTER_SHIFT_RATIO = 0.08
LIVENESS_MIN_AREA_CHANGE_RATIO = 0.12
LIVENESS_ALLOWED_CHALLENGES = ["MOVE_CLOSER"]

# The fallback keeps the offline FYP demo easy to run; it is development/demo-only.
SECRET_KEY = os.getenv("FDAS_SECRET_KEY") or "fdas-local-demo-change-before-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
