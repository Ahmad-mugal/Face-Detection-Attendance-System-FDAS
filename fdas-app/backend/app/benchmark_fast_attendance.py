from __future__ import annotations

import json
import os
import platform
import shutil
import statistics
import tempfile
from datetime import date, timedelta
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_FILE
from app.models.attendance_session import AttendanceSession
from app.models.user import User
from app.services.attendance_marking import mark_fast_multi_face_attendance
from app.services.deep_face import get_deep_face_service
from app.utils.time import utc_now_naive


BACKEND_DIR = Path(__file__).resolve().parent.parent
STORAGE_ROOT = BACKEND_DIR / "storage" / "face_enrollments"
BENCHMARK_STUDENTS = (24, 30, 29)


def cpu_name() -> str:
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    return platform.processor() or platform.machine()


def load_composite(student_ids: tuple[int, ...]) -> tuple[bytes, list[str], tuple[int, int]]:
    images = []
    sources = []
    deep_service = get_deep_face_service()
    for student_id in student_ids:
        candidate_paths = sorted((STORAGE_ROOT / str(student_id)).glob("*.jpg"))
        if not candidate_paths:
            raise FileNotFoundError(f"No enrollment image found for Student #{student_id}")
        selected_source = None
        selected_image = None
        for candidate_path in candidate_paths:
            img = cv2.imread(str(candidate_path))
            if img is None:
                continue
            with open(candidate_path, "rb") as f:
                frame = deep_service.encode_fast_attendance_frame_bytes(f.read())
            if len(frame.faces) == 1 and frame.faces[0].quality["passed"]:
                selected_source = candidate_path
                selected_image = img
                break
        if selected_image is None or selected_source is None:
            raise RuntimeError(f"Could not find a valid single-face enrollment sample for Student #{student_id}")
        images.append(selected_image)
        sources.append(selected_source.relative_to(BACKEND_DIR).as_posix())

    target_height = min(img.shape[0] for img in images)
    resized_images = [
        cv2.resize(img, (int(target_height * (img.shape[1] / img.shape[0])), target_height))
        for img in images
    ]
    composite = resized_images[0] if len(resized_images) == 1 else cv2.hconcat(resized_images)
    encoded, buffer = cv2.imencode(".jpg", composite, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not encoded:
        raise RuntimeError("Could not encode benchmark frame")
    height, width = composite.shape[:2]
    return buffer.tobytes(), sources, (width, height)


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "average": round(statistics.fmean(values), 3),
        "p50": round(float(np.percentile(values, 50)), 3),
        "p95": round(float(np.percentile(values, 95)), 3),
        "max": round(max(values), 3),
    }


def main() -> None:
    iterations = max(3, int(os.getenv("FDAS_FAST_BENCHMARK_ITERATIONS", "12")))
    with tempfile.TemporaryDirectory(prefix="fdas-fast-benchmark-", ignore_cleanup_errors=True) as temporary:
        benchmark_database = Path(temporary) / "benchmark.db"
        shutil.copy2(DATABASE_FILE, benchmark_database)
        engine = create_engine(
            f"sqlite:///{benchmark_database.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        frames = {
            count: load_composite(BENCHMARK_STUDENTS[:count])
            for count in (1, 2, 3)
        }
        with Session() as db:
            admin = db.query(User).filter(User.roleId == 1, User.status == "Approved").first()
            if admin is None:
                raise RuntimeError("No approved Admin is available in the disposable benchmark copy")
            next_session_id = int(db.query(func.max(AttendanceSession.sessionId)).scalar() or 0) + 1

            def execute(face_count: int) -> dict:
                nonlocal next_session_id
                now = utc_now_naive()
                session = AttendanceSession(
                    sessionId=next_session_id,
                    departmentId=1,
                    startedByUserId=admin.userId,
                    scheduledStartTime=now,
                    scheduledEndTime=now + timedelta(hours=1),
                    actualStartTime=now,
                    status="Active",
                    createdDate=date.today(),
                )
                next_session_id += 1
                db.add(session)
                db.commit()
                result = mark_fast_multi_face_attendance(db, admin, session.sessionId, frames[face_count][0])
                expected_ids = set(BENCHMARK_STUDENTS[:face_count])
                marked_ids = {face["studentId"] for face in result["faces"] if face["attendanceMarked"]}
                if marked_ids != expected_ids:
                    raise RuntimeError(
                        f"Benchmark frame with {face_count} faces marked {sorted(marked_ids)}; "
                        f"expected {sorted(expected_ids)}"
                    )
                return result

            cold = execute(1)
            measurements: dict[str, dict] = {}
            timing_fields = (
                "detectorMilliseconds",
                "alignmentMilliseconds",
                "embeddingMilliseconds",
                "galleryMilliseconds",
                "matchingMilliseconds",
                "databaseMilliseconds",
                "totalMilliseconds",
            )
            for face_count in (1, 2, 3):
                execute(face_count)  # shape-specific warm-up, excluded
                results = [execute(face_count) for _index in range(iterations)]
                measurements[str(face_count)] = {
                    "inputResolution": f"{frames[face_count][2][0]}x{frames[face_count][2][1]}",
                    "sourceStudents": list(BENCHMARK_STUDENTS[:face_count]),
                    "sourceFiles": frames[face_count][1],
                    "iterations": iterations,
                    "recognizedPerFrame": face_count,
                    "galleryStudents": results[0]["candidateStudentCount"],
                    "galleryEmbeddings": results[0]["candidateEmbeddingCount"],
                    "timingsMilliseconds": {
                        field: summarize([float(result["timing"][field]) for result in results])
                        for field in timing_fields
                    },
                }

        engine.dispose()
        report = {
            "evidenceType": "synthetic side-by-side composite of distinct real enrollment frames; not a live shared webcam scene",
            "cpu": cpu_name(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "model": "InsightFace buffalo_l / ArcFace / CPUExecutionProvider",
            "threshold": 0.85,
            "requiredMargin": 0.07,
            "fastMinimumFaceAreaRatio": 0.02,
            "coldStart": {
                "faces": 1,
                "modelInitializationMilliseconds": get_deep_face_service().initialization_milliseconds,
                "totalMilliseconds": cold["timing"]["totalMilliseconds"],
            },
            "warm": measurements,
            "frontendRoundtripMilliseconds": None,
            "notes": [
                "Every mutation occurred only in a temporary copy of fdas_local.db.",
                "Camera permission/startup and browser/network roundtrip were not measured.",
                "The same conservative 0.85 threshold and 0.07 distinct-identity margin were enforced.",
            ],
        }
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
