from __future__ import annotations

import argparse
import json

from app.database import SessionLocal, engine
from app.services.deep_embedding_migration import (
    DEEP_ENROLLMENT_MIN_EMBEDDINGS,
    create_embedding_table,
    run_migration,
)
from app.services.deep_face import get_deep_face_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Non-destructively inventory or persist versioned arcface_v1 enrollment embeddings."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Analyze active enrollment images without database writes.")
    mode.add_argument("--apply", action="store_true", help="Persist valid embeddings in the additive versioned table.")
    parser.add_argument("--student-id", type=int, help="Restrict processing to one student.")
    parser.add_argument(
        "--minimum",
        type=int,
        default=DEEP_ENROLLMENT_MIN_EMBEDDINGS,
        help=f"Deep eligibility minimum (default: {DEEP_ENROLLMENT_MIN_EMBEDDINGS}).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = get_deep_face_service()
    if not service.model_files_available():
        raise SystemExit("Required local buffalo_l model files are missing; migration stopped safely.")
    service.initialize()

    if args.apply:
        create_embedding_table(engine)

    with SessionLocal() as db:
        report = run_migration(
            db,
            apply=args.apply,
            student_id=args.student_id,
            minimum_embeddings=args.minimum,
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
