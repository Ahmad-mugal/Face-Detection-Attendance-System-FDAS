from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_FILE = BASE_DIR / "fdas_local.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE.as_posix()}"

APP_NAME = "FDAS Backend"
APP_VERSION = "0.8.1"
APP_PHASE = "Phase 8C - Lightweight Liveness / Anti-Spoofing Foundation"
FACE_MATCH_THRESHOLD = 0.75
LIVENESS_MODE = "basic"
LIVENESS_FRAME_COUNT = 5
LIVENESS_MIN_CENTER_SHIFT_RATIO = 0.08
LIVENESS_MIN_AREA_CHANGE_RATIO = 0.12
LIVENESS_ALLOWED_CHALLENGES = ["MOVE_LEFT", "MOVE_RIGHT", "MOVE_CLOSER"]

# Local FYP demo secret only. Production deployments should load this from environment variables.
SECRET_KEY = "fdas-local-demo-change-before-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
