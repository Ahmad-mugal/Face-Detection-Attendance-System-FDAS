"""Read-only Phase 10.9A threshold/margin calibration over preserved evidence."""

from __future__ import annotations

import json
from collections import Counter

from app.config import BASE_DIR, DATABASE_FILE, DEEP_FACE_ENCODING_VERSION, DEEP_MATCH_SCORING_METHOD
from app.database import SessionLocal
from app.models.attendance_record import AttendanceRecord
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.student import Student
from app.services.deep_face_matching import (
    DeepMatchCandidate,
    exclude_query_leakage,
    parse_deep_embedding,
    rank_deep_candidates,
)


DISTINCT_STUDENT_IDS = (18, 22, 23, 24, 25, 27, 28, 29)
EXCLUDED_SAME_PERSON_STUDENT_IDS = (19,)
THRESHOLDS = (0.80, 0.81, 0.82, 0.83, 0.84, 0.85)
MARGINS = (0.07, 0.10, 0.15, 0.20, 0.25)

# Existing real-webcam results. Phase 10.9 supplied a conservative lower bound
# of 0.503 for all eight margins; that bound is above every grid margin.
LIVE_GENUINE = (
    ("10.7D", 0.904451, 0.682914),
    ("10.7D", 0.904949, 0.666959),
    ("10.7D", 0.850916, 0.611809),
    ("10.7D", 0.882848, 0.583440),
    ("10.7D", 0.904872, 0.647005),
    ("10.7D", 0.897288, 0.641999),
    ("10.7D", 0.868168, 0.632734),
    ("10.7D", 0.850690, 0.631106),
    ("10.7D", 0.855995, 0.566263),
    ("10.7D", 0.899178, 0.688325),
    ("10.8", 0.884575, 0.610336),
    ("10.8", 0.848377, 0.552420),
    ("10.8", 0.841062, 0.546489),
    ("10.8", 0.845205, 0.589420),
    ("10.8", 0.848254, 0.597776),
    ("10.8", 0.856475, 0.552553),
    ("10.9", 0.816142, 0.503000),
    ("10.9", 0.787559, 0.503000),
    ("10.9", 0.822095, 0.503000),
    ("10.9", 0.811141, 0.503000),
    ("10.9", 0.810322, 0.503000),
    ("10.9", 0.810170, 0.503000),
    ("10.9", 0.795756, 0.503000),
    ("10.9", 0.811310, 0.503000),
)


def production_inventory() -> dict:
    with SessionLocal() as db:
        logical_counts = {
            "students": db.query(Student).count(),
            "faceTemplates": db.query(FaceTemplate).count(),
            "deepEmbeddings": db.query(FaceTemplateEmbedding).count(),
            "attendanceRecords": db.query(AttendanceRecord).count(),
        }
    storage_files = [path for path in (BASE_DIR / "storage").rglob("*") if path.is_file()]
    return {
        **logical_counts,
        "databaseBytes": DATABASE_FILE.stat().st_size,
        "storageFiles": len(storage_files),
        "storageBytes": sum(path.stat().st_size for path in storage_files),
    }


def load_candidates() -> list[DeepMatchCandidate]:
    with SessionLocal() as db:
        rows = (
            db.query(FaceTemplateEmbedding, FaceTemplate, Student)
            .join(FaceTemplate, FaceTemplate.templateId == FaceTemplateEmbedding.faceTemplateId)
            .join(Student, Student.studentId == FaceTemplateEmbedding.studentId)
            .filter(
                Student.studentId.in_(DISTINCT_STUDENT_IDS),
                Student.status == "Active",
                FaceTemplateEmbedding.encodingVersion == DEEP_FACE_ENCODING_VERSION,
                FaceTemplateEmbedding.isActive.is_(True),
                FaceTemplate.isActive.is_(True),
            )
            .order_by(FaceTemplateEmbedding.faceTemplateEmbeddingId)
            .all()
        )
        candidates = []
        for embedding, template, student in rows:
            vector = parse_deep_embedding(embedding.embeddingData)
            if vector is not None:
                candidates.append(DeepMatchCandidate(embedding, template, student, vector))
        return candidates


def analyze_stored(candidates: list[DeepMatchCandidate]) -> tuple[list[dict], list[dict]]:
    genuine: list[dict] = []
    proxy: list[dict] = []
    for query in candidates:
        filtered, _ = exclude_query_leakage(
            candidates,
            excluded_embedding_id=query.embedding.faceTemplateEmbeddingId,
            excluded_source_sha256=query.embedding.sourceImageSha256,
        )
        ranking = rank_deep_candidates(query.vector, filtered, DEEP_MATCH_SCORING_METHOD)
        expected = next(item for item in ranking if item.student.studentId == query.student.studentId)
        strongest_other = next(item for item in ranking if item.student.studentId != query.student.studentId)
        genuine.append(
            {
                "correctTop1": ranking[0].student.studentId == query.student.studentId,
                "score": expected.score,
                "margin": round(expected.score - strongest_other.score, 6),
            }
        )

        proxy_candidates = [item for item in filtered if item.student.studentId != query.student.studentId]
        proxy_ranking = rank_deep_candidates(query.vector, proxy_candidates, DEEP_MATCH_SCORING_METHOD)
        proxy.append(
            {
                "score": proxy_ranking[0].score,
                "margin": round(proxy_ranking[0].score - proxy_ranking[1].score, 6),
            }
        )
    return genuine, proxy


def main() -> None:
    candidates = load_candidates()
    counts = Counter(item.student.studentId for item in candidates)
    genuine, proxy = analyze_stored(candidates)
    grid = []
    for threshold in THRESHOLDS:
        for margin in MARGINS:
            stored_accepted = sum(
                row["correctTop1"] and row["score"] >= threshold and row["margin"] >= margin
                for row in genuine
            )
            stored_ambiguous = sum(
                row["correctTop1"] and row["score"] >= threshold and row["margin"] < margin
                for row in genuine
            )
            proxy_accepted = sum(row["score"] >= threshold and row["margin"] >= margin for row in proxy)
            live_accepted = sum(score >= threshold and live_margin >= margin for _, score, live_margin in LIVE_GENUINE)
            phase10_9_accepted = sum(
                score >= threshold and live_margin >= margin
                for phase, score, live_margin in LIVE_GENUINE
                if phase == "10.9"
            )
            grid.append(
                {
                    "threshold": threshold,
                    "margin": margin,
                    "storedGenuineAccepted": stored_accepted,
                    "storedGenuineRejected": len(genuine) - stored_accepted,
                    "storedAmbiguousRejects": stored_ambiguous,
                    "proxyImpostorAccepted": proxy_accepted,
                    "proxyImpostorRejected": len(proxy) - proxy_accepted,
                    "liveGenuineAccepted": live_accepted,
                    "liveGenuineRejected": len(LIVE_GENUINE) - live_accepted,
                    "phase10_9LiveAccepted": phase10_9_accepted,
                    "phase10_9LiveRejected": 8 - phase10_9_accepted,
                }
            )

    report = {
        "phase": "10.9A",
        "readOnly": True,
        "productionInventory": production_inventory(),
        "scoringMethod": DEEP_MATCH_SCORING_METHOD,
        "distinctStudentIds": list(DISTINCT_STUDENT_IDS),
        "excludedSamePhysicalIdentityStudentIds": list(EXCLUDED_SAME_PERSON_STUDENT_IDS),
        "embeddingCounts": dict(sorted(counts.items())),
        "storedQueryCount": len(genuine),
        "storedWrongTop1Count": sum(not row["correctTop1"] for row in genuine),
        "storedGenuineScoreRange": [min(row["score"] for row in genuine), max(row["score"] for row in genuine)],
        "storedGenuineMarginRange": [min(row["margin"] for row in genuine), max(row["margin"] for row in genuine)],
        "proxyImpostorCount": len(proxy),
        "proxyImpostorScoreRange": [min(row["score"] for row in proxy), max(row["score"] for row in proxy)],
        "liveGenuineCount": len(LIVE_GENUINE),
        "phase10_9LiveCount": 8,
        "phase10_9Consensus": "8/8 results selected Student #22 with 3/3 query consensus",
        "phase10_9MarginHandling": "0.503 conservative lower bound; all observed margins were approximately 0.503-0.553",
        "grid": grid,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
