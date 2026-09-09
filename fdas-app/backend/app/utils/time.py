from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Return naive UTC for the existing SQLite DATETIME schema."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
