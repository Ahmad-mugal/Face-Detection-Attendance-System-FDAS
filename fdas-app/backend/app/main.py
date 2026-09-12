from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_NAME, APP_PHASE, APP_VERSION, CORS_ALLOWED_ORIGINS
from app.routers.admin_users import router as admin_users_router
from app.routers.attendance_marking import router as attendance_marking_router
from app.routers.attendance_records import router as attendance_records_router
from app.routers.attendance_sessions import router as attendance_sessions_router
from app.routers.auth import router as auth_router
from app.routers.attendance_time_windows import router as attendance_time_windows_router
from app.routers.classes import router as classes_router
from app.routers.dashboard import router as dashboard_router
from app.routers.departments import router as departments_router
from app.routers.deep_face import router as deep_face_router
from app.routers.face_enrollment import router as face_enrollment_router
from app.routers.face_matching import router as face_matching_router
from app.routers.foundation import router as foundation_router
from app.routers.liveness import router as liveness_router
from app.routers.students import router as students_router


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_PHASE,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(foundation_router)
app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(departments_router)
app.include_router(deep_face_router)
app.include_router(classes_router)
app.include_router(students_router)
app.include_router(attendance_time_windows_router)
app.include_router(attendance_sessions_router)
app.include_router(face_enrollment_router)
app.include_router(face_matching_router)
app.include_router(attendance_marking_router)
app.include_router(attendance_records_router)
app.include_router(liveness_router)
app.include_router(dashboard_router)
