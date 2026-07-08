from fastapi import FastAPI

from app.config import APP_NAME, APP_PHASE, APP_VERSION
from app.routers.admin_users import router as admin_users_router
from app.routers.auth import router as auth_router
from app.routers.foundation import router as foundation_router


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_PHASE,
)

app.include_router(foundation_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
