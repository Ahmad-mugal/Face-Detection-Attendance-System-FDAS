from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_FILE = BASE_DIR / "fdas_local.db"
DATABASE_URL = f"sqlite:///{DATABASE_FILE.as_posix()}"

APP_NAME = "FDAS Backend"
APP_VERSION = "0.6.1"
APP_PHASE = "Phase 6B - Face Enrollment Upload and Storage APIs"

# Local FYP demo secret only. Production deployments should load this from environment variables.
SECRET_KEY = "fdas-local-demo-change-before-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
