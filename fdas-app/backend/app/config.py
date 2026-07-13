from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_FILE = BASE_DIR / "fdas_local.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE.as_posix()}"

APP_NAME = "FDAS Backend"
APP_VERSION = "0.8.0"
APP_PHASE = "Phase 8B - Attendance Records and Reports Integration Foundation"
FACE_MATCH_THRESHOLD = 0.75

# Local FYP demo secret only. Production deployments should load this from environment variables.
SECRET_KEY = "fdas-local-demo-change-before-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
