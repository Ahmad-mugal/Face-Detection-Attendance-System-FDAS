from fastapi import APIRouter
from sqlalchemy import text

from app.config import APP_NAME, APP_PHASE, APP_VERSION, DATABASE_FILE
from app.database import SessionLocal
from app.schemas.foundation import HealthResponse, InfoResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    database_status = "connected"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        database_status = "disconnected"

    return {
        "status": "ok",
        "service": APP_NAME,
        "database": database_status,
    }


@router.get("/api/info", response_model=InfoResponse)
def api_info():
    return {
        "appName": APP_NAME,
        "version": APP_VERSION,
        "database": str(DATABASE_FILE),
        "note": "Local SQLite backend foundation only. No auth or face recognition in Phase 2.",
    }
