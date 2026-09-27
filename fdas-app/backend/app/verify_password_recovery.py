from __future__ import annotations

import asyncio
import logging
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.database import Base
from app.dependencies import require_admin
from app.models.department import Department
from app.models.notification import Notification
from app.models.password_reset import PasswordResetThrottle, PasswordResetToken
from app.models.role import Role
from app.models.user import User
from app.routers import admin_users, auth
from app.schemas.auth import AdminCodePasswordResetRequest, ForgotPasswordRequest, PasswordResetRequest
from app.services.email_service import EmailDeliveryResult, build_password_reset_email
from app.services.password_recovery import (
    ADMIN_CODE,
    ADMIN_CODE_MAX_ATTEMPTS,
    EMAIL_LINK,
    INVALID_ADMIN_CODE_MESSAGE,
    PUBLIC_RECOVERY_MESSAGE,
    credential_hash,
    issue_admin_code,
    issue_email_token,
    reset_with_admin_code,
    reset_with_email_token,
)
from app.utils.security import hash_password, verify_password
from app.utils.time import utc_now_naive


def expect_http_status(callback, expected_status: int) -> bool:
    try:
        callback()
    except HTTPException as exc:
        return exc.status_code == expected_status
    return False


def request_for(client: str) -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": (client, 5000)})


def main() -> None:
    results: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="fdas-password-recovery-") as directory:
        root = Path(directory)
        engine = create_engine(f"sqlite:///{(root / 'password_recovery.db').as_posix()}")
        TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=engine)

        with TestingSession() as db:
            admin_role = Role(roleName="Admin")
            user_role = Role(roleName="User")
            department = Department(departmentName="Computer Science", status="Active")
            db.add_all([admin_role, user_role, department])
            db.flush()
            admin = User(fullName="Recovery Admin", email="admin@recovery.local", passwordHash=hash_password("Admin-Old-123"), roleId=admin_role.roleId, status="Approved", accessScope="AllDepartments")
            approved = User(fullName="Approved Operator", email="approved@recovery.local", passwordHash=hash_password("Approved-Old-123"), roleId=user_role.roleId, status="Approved", accessScope="Department", assignedDepartmentId=department.departmentId)
            disabled = User(fullName="Disabled Operator", email="disabled@recovery.local", passwordHash=hash_password("Disabled-Old-123"), roleId=user_role.roleId, status="Disabled", accessScope="Department", assignedDepartmentId=department.departmentId)
            pending = User(fullName="Pending Operator", email="pending@recovery.local", passwordHash=hash_password("Pending-Old-123"), roleId=user_role.roleId, status="Pending", accessScope="Department", assignedDepartmentId=department.departmentId)
            rejected = User(fullName="Rejected Operator", email="rejected@recovery.local", passwordHash=hash_password("Rejected-Old-123"), roleId=user_role.roleId, status="Rejected", accessScope="Department", assignedDepartmentId=department.departmentId)
            expiry_user = User(fullName="Expiry Operator", email="expiry@recovery.local", passwordHash=hash_password("Expiry-Old-123"), roleId=user_role.roleId, status="Approved", accessScope="Department", assignedDepartmentId=department.departmentId)
            attempt_user = User(fullName="Attempt Operator", email="attempt@recovery.local", passwordHash=hash_password("Attempt-Old-123"), roleId=user_role.roleId, status="Approved", accessScope="Department", assignedDepartmentId=department.departmentId)
            single_use_user = User(fullName="Single Use Operator", email="single@recovery.local", passwordHash=hash_password("Single-Old-123"), roleId=user_role.roleId, status="Approved", accessScope="Department", assignedDepartmentId=department.departmentId)
            db.add_all([admin, approved, disabled, pending, rejected, expiry_user, attempt_user, single_use_user])
            db.commit()
            for user in (admin, approved, disabled, pending, rejected, expiry_user, attempt_user, single_use_user):
                db.refresh(user)

            sent: dict[str, str] = {}
            background = BackgroundTasks()

            def capture_reset_email(**kwargs):
                sent.update(kwargs)
                return EmailDeliveryResult(True, "Password reset email sent successfully.")

            with patch("app.routers.auth.load_smtp_settings", return_value=SimpleNamespace(configured=True)), patch("app.routers.auth.send_password_reset_email", side_effect=capture_reset_email):
                existing_response = auth.forgot_password(
                    ForgotPasswordRequest(email="  APPROVED@RECOVERY.LOCAL "),
                    request_for("127.0.0.10"),
                    background,
                    db,
                )
                results["existing_eligible_email_request"] = existing_response["message"] == PUBLIC_RECOVERY_MESSAGE
                results["email_normalization"] = ForgotPasswordRequest(email="  APPROVED@RECOVERY.LOCAL ").email == approved.email
                asyncio.run(background())

            email_record = db.query(PasswordResetToken).filter(PasswordResetToken.userId == approved.userId, PasswordResetToken.tokenType == EMAIL_LINK).one()
            raw_email_token = parse_qs(urlparse(sent["reset_url"]).query)["token"][0]
            results["smtp_configured_email_reset"] = sent.get("recipient_email") == approved.email and sent["reset_url"].startswith("http://127.0.0.1:5173/reset-password?")
            results["token_stored_hashed"] = email_record.tokenHash == credential_hash(raw_email_token, EMAIL_LINK) and raw_email_token not in email_record.tokenHash
            results["public_response_contains_no_token"] = raw_email_token not in str(existing_response)

            unknown_background = BackgroundTasks()
            with patch("app.routers.auth.load_smtp_settings", return_value=SimpleNamespace(configured=True)):
                unknown_response = auth.forgot_password(ForgotPasswordRequest(email="unknown@recovery.local"), request_for("127.0.0.11"), unknown_background, db)
            results["unknown_email_same_public_response"] = unknown_response == existing_response and len(unknown_background.tasks) == 0

            before_unconfigured = db.query(PasswordResetToken).count()
            with patch("app.routers.auth.load_smtp_settings", return_value=SimpleNamespace(configured=False)):
                unavailable_response = auth.forgot_password(ForgotPasswordRequest(email=disabled.email), request_for("127.0.0.12"), BackgroundTasks(), db)
            results["smtp_unavailable_remains_safe"] = unavailable_response == existing_response and db.query(PasswordResetToken).count() == before_unconfigured
            results["request_rate_limit"] = expect_http_status(
                lambda: auth.forgot_password(ForgotPasswordRequest(email=disabled.email), request_for("127.0.0.12"), BackgroundTasks(), db),
                429,
            )

            original_role = approved.roleId
            original_department = approved.assignedDepartmentId
            original_scope = approved.accessScope
            reset_with_email_token(db, raw_token=raw_email_token, new_password="Approved-New-456")
            results["valid_email_token_reset"] = email_record.usedAt is not None
            results["new_password_pbkdf2_hashed"] = approved.passwordHash.startswith("pbkdf2_sha256$") and "Approved-New-456" not in approved.passwordHash
            results["login_new_password_works"] = verify_password("Approved-New-456", approved.passwordHash)
            results["old_password_fails"] = not verify_password("Approved-Old-123", approved.passwordHash)
            results["used_token_rejected"] = expect_http_status(lambda: reset_with_email_token(db, raw_token=raw_email_token, new_password="Another-New-789"), 400)
            results["role_department_scope_unchanged"] = (approved.roleId, approved.assignedDepartmentId, approved.accessScope) == (original_role, original_department, original_scope)

            expired_raw, expired_record = issue_email_token(db, expiry_user, now=utc_now_naive() - timedelta(minutes=30))
            db.commit()
            results["expired_token_rejected"] = expect_http_status(lambda: reset_with_email_token(db, raw_token=expired_raw, new_password="Expiry-New-456"), 400)
            results["random_token_rejected"] = expect_http_status(lambda: reset_with_email_token(db, raw_token="random-invalid-token-value-that-is-long-enough", new_password="Random-New-456"), 400)

            first_raw, first_record = issue_email_token(db, expiry_user)
            second_raw, second_record = issue_email_token(db, expiry_user)
            db.commit()
            results["replacement_email_token_revokes_old"] = first_record.revokedAt is not None and second_record.revokedAt is None and expect_http_status(lambda: reset_with_email_token(db, raw_token=first_raw, new_password="Expiry-New-456"), 400)

            for blocked, client in ((pending, "127.0.0.13"), (rejected, "127.0.0.14")):
                with patch("app.routers.auth.load_smtp_settings", return_value=SimpleNamespace(configured=True)):
                    response = auth.forgot_password(ForgotPasswordRequest(email=blocked.email), request_for(client), BackgroundTasks(), db)
                results[f"{blocked.status.lower()}_cannot_bypass_approval"] = response == existing_response and db.query(PasswordResetToken).filter(PasswordResetToken.userId == blocked.userId).count() == 0

            disabled_code, disabled_credential = issue_admin_code(db, disabled, admin)
            db.commit()
            reset_with_admin_code(db, email=disabled.email, recovery_code=disabled_code, new_password="Disabled-New-456")
            results["disabled_reset_does_not_enable"] = disabled.status == "Disabled" and verify_password("Disabled-New-456", disabled.passwordHash)

            results["operator_cannot_generate_admin_code"] = expect_http_status(lambda: require_admin(approved), 403)
            generated = admin_users.generate_password_recovery_code(single_use_user.userId, admin, db)
            generated_code = generated["recoveryCode"]
            generated_record = db.query(PasswordResetToken).filter(PasswordResetToken.userId == single_use_user.userId, PasswordResetToken.tokenType == ADMIN_CODE, PasswordResetToken.usedAt.is_(None), PasswordResetToken.revokedAt.is_(None)).one()
            results["admin_generates_operator_recovery_code"] = len(generated_code.replace("-", "")) == 12 and generated_record.tokenHash == credential_hash(generated_code.replace("-", ""), ADMIN_CODE)
            results["admin_never_receives_final_password"] = set(generated) == {"recoveryCode", "expiresAt", "message"} and "password" not in str(generated).lower()

            expired_code, expired_admin_record = issue_admin_code(db, expiry_user, admin, now=utc_now_naive() - timedelta(minutes=20))
            db.commit()
            results["admin_code_expires"] = expect_http_status(lambda: reset_with_admin_code(db, email=expiry_user.email, recovery_code=expired_code, new_password="Expiry-New-456"), 400)

            attempt_code, attempt_record = issue_admin_code(db, attempt_user, admin)
            db.commit()
            for _ in range(ADMIN_CODE_MAX_ATTEMPTS):
                try:
                    reset_with_admin_code(db, email=attempt_user.email, recovery_code="ZZZZ-ZZZZ-ZZZZ", new_password="Attempt-New-456")
                except HTTPException as exc:
                    if exc.detail != INVALID_ADMIN_CODE_MESSAGE:
                        raise
            db.refresh(attempt_record)
            results["admin_code_attempt_limit"] = attempt_record.failedAttemptCount == ADMIN_CODE_MAX_ATTEMPTS and attempt_record.revokedAt is not None and expect_http_status(lambda: reset_with_admin_code(db, email=attempt_user.email, recovery_code=attempt_code, new_password="Attempt-New-456"), 400)

            reset_with_admin_code(db, email=single_use_user.email, recovery_code=generated_code, new_password="Single-New-456")
            results["admin_code_single_use"] = generated_record.usedAt is not None and expect_http_status(lambda: reset_with_admin_code(db, email=single_use_user.email, recovery_code=generated_code, new_password="Single-Again-789"), 400)

            replacement_code, replacement_first = issue_admin_code(db, attempt_user, admin)
            replacement_code_2, replacement_second = issue_admin_code(db, attempt_user, admin)
            db.commit()
            results["replacement_admin_code_revokes_old"] = replacement_first.revokedAt is not None and replacement_second.revokedAt is None and replacement_code != replacement_code_2

            email_content = build_password_reset_email(user_name=approved.fullName, reset_url="http://127.0.0.1:5173/reset-password?token=safe-test-token")
            security_notice = db.query(Notification).filter(
                Notification.recipientUserId == approved.userId,
                Notification.type == "PASSWORD_CHANGED",
            ).count()
            combined_responses = str([existing_response, unknown_response, unavailable_response, generated])
            results["security_notice_created"] = security_notice >= 1
            results["no_secrets_in_responses_or_email"] = (
                "Approved-New-456" not in combined_responses
                and "passwordHash" not in combined_responses
                and "FDAS_SMTP_PASSWORD" not in email_content.text_body + email_content.html_body
                and "Approved-Old-123" not in email_content.text_body + email_content.html_body
                and "Approved-New-456" not in email_content.text_body + email_content.html_body
                and "jwt" not in email_content.text_body.lower()
            )
            results["request_throttle_stores_no_email"] = all(approved.email not in f"{row.emailKeyHash}{row.clientKeyHash}" for row in db.query(PasswordResetThrottle).all())
            results["schema_validates_matching_passwords"] = PasswordResetRequest(token="x" * 40, newPassword="Schema-Test-123", confirmPassword="Schema-Test-123").newPassword == "Schema-Test-123" and AdminCodePasswordResetRequest(email=approved.email, recoveryCode="ABCD-EFGH-JK23", newPassword="Schema-Test-456", confirmPassword="Schema-Test-456").email == approved.email

        engine.dispose()

    for name, passed in results.items():
        print(f"{name}={passed}")
    if not results or not all(results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    main()
