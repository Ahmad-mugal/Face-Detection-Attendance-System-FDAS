from sqlalchemy import inspect

from app.config import DATABASE_FILE
from app.database import SessionLocal, init_db
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.seed import seed_database


REQUIRED_TABLES = [
    "roles",
    "departments",
    "users",
    "classrooms",
    "students",
    "face_templates",
    "attendance_time_windows",
    "attendance_sessions",
    "attendance_records",
]


def verify_phase2() -> None:
    init_db()
    seed_database()

    with SessionLocal() as db:
        inspector = inspect(db.bind)
        tables = sorted(inspector.get_table_names())
        missing_tables = sorted(set(REQUIRED_TABLES) - set(tables))

        counts = {
            "roles": db.query(Role).count(),
            "departments": db.query(Department).count(),
            "users": db.query(User).count(),
            "classrooms": db.query(ClassRoom).count(),
            "students": db.query(Student).count(),
        }

        admin = db.query(User).filter(User.email == "admin@fdas.local").one_or_none()
        admin_hash_is_safe = bool(admin and admin.passwordHash != "Admin@12345")

    print(f"database_file={DATABASE_FILE}")
    print(f"database_exists={DATABASE_FILE.exists()}")
    print(f"tables={','.join(tables)}")
    print(f"missing_tables={','.join(missing_tables) if missing_tables else 'none'}")
    for name, count in counts.items():
        print(f"{name}_count={count}")
    print(f"admin_exists={admin is not None}")
    print(f"admin_password_hashed={admin_hash_is_safe}")

    if missing_tables:
        raise SystemExit(1)
    if counts["roles"] < 2 or counts["departments"] < 4 or admin is None or not admin_hash_is_safe:
        raise SystemExit(1)


if __name__ == "__main__":
    verify_phase2()
