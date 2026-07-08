from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY


def create_access_token(claims: dict[str, Any]) -> str:
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = claims.copy()
    payload["exp"] = expire_at
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
