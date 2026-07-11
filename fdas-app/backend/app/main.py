from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_NAME, APP_PHASE, APP_VERSION
from app.routers.admin_users import router as admin_users_router
from app.routers.attendance_sessions import router as attendance_sessions_router
from app.routers.auth import router as auth_router
from app.routers.attendance_time_windows import router as attendance_time_windows_router
from app.routers.classes import router as classes_router
from app.routers.departments import router as departments_router
from app.routers.foundation import router as foundation_router
from app.routers.students import router as students_router


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_PHASE,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(foundation_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(departments_router)
app.include_router(classes_router)
app.include_router(students_router)
app.include_router(attendance_time_windows_router)
app.include_router(attendance_sessions_router)
