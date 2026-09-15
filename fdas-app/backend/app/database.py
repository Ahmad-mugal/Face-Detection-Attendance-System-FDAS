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
    available_tables = set(inspector.get_table_names())
    compatibility_columns = {
        "face_templates": {
            "sampleIndex": "INTEGER",
            "isActive": "BOOLEAN NOT NULL DEFAULT 1",
            "createdByUserId": "INTEGER",
            "encodingVersion": "VARCHAR(80)",
            "faceBoxJson": "TEXT",
            "processedAt": "DATETIME",
        },
        "attendance_records": {
            "recognitionProvider": "VARCHAR(40)",
            "recognitionEncodingVersion": "VARCHAR(80)",
            "recognitionMethod": "VARCHAR(40)",
            "identityMargin": "FLOAT",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in compatibility_columns.items():
            if table_name not in available_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, column_sql in columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}"))
