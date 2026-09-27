from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import SECRET_KEY
from app.models.password_reset import PasswordResetThrottle, PasswordResetToken
from app.models.user import User
from app.services.notifications import create_notification
from app.utils.security import hash_password
from app.utils.time import utc_now_naive


EMAIL_LINK = "EMAIL_LINK"
ADMIN_CODE = "ADMIN_CODE"
RECOVERABLE_STATUSES = {"Approved", "Disabled"}
PUBLIC_RECOVERY_MESSAGE = (
    "If an eligible account exists for this email, password recovery instructions have been prepared."
)
INVALID_EMAIL_TOKEN_MESSAGE = "This password reset link is invalid, expired, or has already been used."
INVALID_ADMIN_CODE_MESSAGE = "The recovery code is invalid, expired, or has already been used."
EMAIL_TOKEN_LIFETIME = timedelta(minutes=20)
ADMIN_CODE_LIFETIME = timedelta(minutes=10)
ADMIN_CODE_MAX_ATTEMPTS = 5
REQUEST_COOLDOWN = timedelta(seconds=60)
REQUEST_WINDOW = timedelta(minutes=15)
MAX_EMAIL_REQUESTS_PER_WINDOW = 5
MAX_CLIENT_REQUESTS_PER_WINDOW = 20
THROTTLE_RETENTION = timedelta(hours=24)
ADMIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def credential_hash(value: str, token_type: str) -> str:
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{token_type}:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def privacy_key(value: str, purpose: str) -> str:
    return credential_hash(value, f"PRIVACY_{purpose}")


def normalize_admin_code(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def is_recovery_eligible(user: User | None) -> bool:
    return bool(user and user.status in RECOVERABLE_STATUSES)


def enforce_recovery_rate_limit(
    db: Session,
    *,
    email: str,
    client_identity: str,
    now: datetime | None = None,
) -> None:
    current = now or utc_now_naive()
    email_hash = privacy_key(email, "EMAIL")
    client_hash = privacy_key(client_identity or "local-unknown", "CLIENT")
    retention_cutoff = current - THROTTLE_RETENTION
    window_cutoff = current - REQUEST_WINDOW
    cooldown_cutoff = current - REQUEST_COOLDOWN

    db.query(PasswordResetThrottle).filter(PasswordResetThrottle.createdAt < retention_cutoff).delete(
        synchronize_session=False,
    )
    latest = (
        db.query(PasswordResetThrottle)
        .filter(PasswordResetThrottle.emailKeyHash == email_hash)
        .order_by(PasswordResetThrottle.createdAt.desc())
        .first()
    )
    email_count = db.query(PasswordResetThrottle).filter(
        PasswordResetThrottle.emailKeyHash == email_hash,
        PasswordResetThrottle.createdAt >= window_cutoff,
    ).count()
    client_count = db.query(PasswordResetThrottle).filter(
        PasswordResetThrottle.clientKeyHash == client_hash,
        PasswordResetThrottle.createdAt >= window_cutoff,
    ).count()
    if (
        (latest is not None and latest.createdAt > cooldown_cutoff)
        or email_count >= MAX_EMAIL_REQUESTS_PER_WINDOW
        or client_count >= MAX_CLIENT_REQUESTS_PER_WINDOW
    ):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting password recovery again.",
        )

    db.add(PasswordResetThrottle(
        emailKeyHash=email_hash,
        clientKeyHash=client_hash,
        createdAt=current,
    ))
    db.flush()


def revoke_active_credentials(
    db: Session,
    *,
    user_id: int,
    token_type: str | None = None,
    now: datetime | None = None,
    exclude_id: int | None = None,
) -> int:
    current = now or utc_now_naive()
    query = db.query(PasswordResetToken).filter(
        PasswordResetToken.userId == user_id,
        PasswordResetToken.usedAt.is_(None),
        PasswordResetToken.revokedAt.is_(None),
    )
    if token_type is not None:
        query = query.filter(PasswordResetToken.tokenType == token_type)
    if exclude_id is not None:
        query = query.filter(PasswordResetToken.passwordResetTokenId != exclude_id)
    return query.update({PasswordResetToken.revokedAt: current}, synchronize_session=False)


def issue_email_token(db: Session, user: User, now: datetime | None = None) -> tuple[str, PasswordResetToken]:
    current = now or utc_now_naive()
    revoke_active_credentials(db, user_id=user.userId, token_type=EMAIL_LINK, now=current)
    raw_token = secrets.token_urlsafe(48)
    record = PasswordResetToken(
        userId=user.userId,
        tokenHash=credential_hash(raw_token, EMAIL_LINK),
        tokenType=EMAIL_LINK,
        expiresAt=current + EMAIL_TOKEN_LIFETIME,
        createdAt=current,
    )
    db.add(record)
    db.flush()
    return raw_token, record


def issue_admin_code(
    db: Session,
    user: User,
    admin: User,
    now: datetime | None = None,
) -> tuple[str, PasswordResetToken]:
    if not user.role or user.role.roleName != "User":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrator recovery codes are available only for Operator accounts.",
        )
    if not is_recovery_eligible(user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Password recovery is available only for approved or disabled Operator accounts.",
        )

    current = now or utc_now_naive()
    revoke_active_credentials(db, user_id=user.userId, token_type=ADMIN_CODE, now=current)
    compact_code = "".join(secrets.choice(ADMIN_CODE_ALPHABET) for _ in range(12))
    display_code = "-".join(compact_code[index:index + 4] for index in range(0, 12, 4))
    record = PasswordResetToken(
        userId=user.userId,
        tokenHash=credential_hash(compact_code, ADMIN_CODE),
        tokenType=ADMIN_CODE,
        expiresAt=current + ADMIN_CODE_LIFETIME,
        createdAt=current,
        createdByAdminUserId=admin.userId,
    )
    db.add(record)
    db.flush()
    return display_code, record


def _claim_credential(
    db: Session,
    *,
    credential: PasswordResetToken,
    now: datetime,
    invalid_message: str,
) -> None:
    """Atomically consume one still-valid credential before changing a password."""
    claimed = db.query(PasswordResetToken).filter(
        PasswordResetToken.passwordResetTokenId == credential.passwordResetTokenId,
        PasswordResetToken.usedAt.is_(None),
        PasswordResetToken.revokedAt.is_(None),
        PasswordResetToken.expiresAt > now,
        PasswordResetToken.failedAttemptCount < ADMIN_CODE_MAX_ATTEMPTS,
    ).update({PasswordResetToken.usedAt: now}, synchronize_session=False)
    if claimed != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=invalid_message)


def _complete_reset(db: Session, *, user: User, credential: PasswordResetToken, new_password: str, now: datetime) -> None:
    user.passwordHash = hash_password(new_password)
    revoke_active_credentials(
        db,
        user_id=user.userId,
        now=now,
        exclude_id=credential.passwordResetTokenId,
    )
    create_notification(
        db,
        recipient_user_id=user.userId,
        type="PASSWORD_CHANGED",
        severity="ACTION_REQUIRED",
        title="Account password changed",
        message="Your FDAS account password was changed. Contact an administrator immediately if you did not perform this action.",
        action_url="/login",
    )
    db.commit()


def reset_with_email_token(db: Session, *, raw_token: str, new_password: str, now: datetime | None = None) -> User:
    current = now or utc_now_naive()
    token_hash = credential_hash(raw_token, EMAIL_LINK)
    credential = db.query(PasswordResetToken).filter(
        PasswordResetToken.tokenHash == token_hash,
        PasswordResetToken.tokenType == EMAIL_LINK,
    ).one_or_none()
    if (
        credential is None
        or credential.usedAt is not None
        or credential.revokedAt is not None
        or credential.expiresAt <= current
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_EMAIL_TOKEN_MESSAGE)
    user = db.get(User, credential.userId)
    if not is_recovery_eligible(user):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_EMAIL_TOKEN_MESSAGE)
    _claim_credential(
        db,
        credential=credential,
        now=current,
        invalid_message=INVALID_EMAIL_TOKEN_MESSAGE,
    )
    _complete_reset(db, user=user, credential=credential, new_password=new_password, now=current)
    db.refresh(user)
    return user


def reset_with_admin_code(
    db: Session,
    *,
    email: str,
    recovery_code: str,
    new_password: str,
    now: datetime | None = None,
) -> User:
    current = now or utc_now_naive()
    user = db.query(User).filter(func.lower(User.email) == email).one_or_none()
    if not is_recovery_eligible(user) or not user.role or user.role.roleName != "User":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_ADMIN_CODE_MESSAGE)

    credential = db.query(PasswordResetToken).filter(
        PasswordResetToken.userId == user.userId,
        PasswordResetToken.tokenType == ADMIN_CODE,
        PasswordResetToken.usedAt.is_(None),
        PasswordResetToken.revokedAt.is_(None),
    ).order_by(PasswordResetToken.createdAt.desc()).first()
    if credential is None or credential.expiresAt <= current or credential.failedAttemptCount >= ADMIN_CODE_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_ADMIN_CODE_MESSAGE)

    supplied_hash = credential_hash(normalize_admin_code(recovery_code), ADMIN_CODE)
    if not hmac.compare_digest(supplied_hash, credential.tokenHash):
        credential.failedAttemptCount += 1
        if credential.failedAttemptCount >= ADMIN_CODE_MAX_ATTEMPTS:
            credential.revokedAt = current
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_ADMIN_CODE_MESSAGE)

    _claim_credential(
        db,
        credential=credential,
        now=current,
        invalid_message=INVALID_ADMIN_CODE_MESSAGE,
    )
    _complete_reset(db, user=user, credential=credential, new_password=new_password, now=current)
    db.refresh(user)
    return user
