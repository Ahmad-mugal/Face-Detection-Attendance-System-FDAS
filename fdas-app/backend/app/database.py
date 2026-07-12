from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL


class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_sqlite_compatibility_columns()


def ensure_sqlite_compatibility_columns():
    inspector = inspect(engine)
    if "face_templates" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("face_templates")}
    compatibility_columns = {
        "sampleIndex": "INTEGER",
        "isActive": "BOOLEAN NOT NULL DEFAULT 1",
        "createdByUserId": "INTEGER",
        "encodingVersion": "VARCHAR(80)",
        "faceBoxJson": "TEXT",
        "processedAt": "DATETIME",
    }

    with engine.begin() as connection:
        for column_name, column_sql in compatibility_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE face_templates ADD COLUMN {column_name} {column_sql}"))
