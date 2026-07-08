from fastapi import FastAPI

from app.config import APP_NAME, APP_PHASE, APP_VERSION
from app.routers.foundation import router as foundation_router


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_PHASE,
)

app.include_router(foundation_router)

