from __future__ import annotations

import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.dependencies import require_admin
from app.models.department import Department
from app.models.role import Role
from app.models.user import User
from app.routers import admin_users
from app.schemas.auth import AccessUpdateRequest
from app.services import email_service
from app.services.email_service import (
    APPROVAL_EMAIL_SUBJECT,
    EmailDeliveryResult,
    SMTP_ENVIRONMENT_KEYS,
    build_approval_email,
)
from app.utils.security import hash_password


OPERATOR_PASSWORD = "Phase10.12A-Operator@123"


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_credentials: tuple[str, str] | None = None
        self.message = None
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def ehlo(self):
        return None

    def starttls(self, *, context):
        self.started_tls = context is not None

    def login(self, username: str, password: str):
        self.login_credentials = (username, password)

    def send_message(self, message):
        self.message = message


class FailingSmtp(FakeSmtp):
    def send_message(self, message):
        raise OSError("synthetic SMTP transport failure")


def smtp_environment() -> dict[str, str]:
    return {
        "FDAS_SMTP_HOST": "smtp.test.local",
        "FDAS_SMTP_PORT": "587",
        "FDAS_SMTP_USERNAME": "smtp-user",
        "FDAS_SMTP_PASSWORD": "smtp-test-secret",
        "FDAS_SMTP_FROM_EMAIL": "fdas@test.local",
        "FDAS_SMTP_FROM_NAME": "FDAS Test",
        "FDAS_SMTP_USE_TLS": "true",
    }


def expect_http_status(callback, expected_status: int) -> bool:
    try:
        callback()
    except HTTPException as exc:
        return exc.status_code == expected_status
    return False


def main() -> None:
    results: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="fdas-phase10-12a-") as temp_directory:
        temp_root = Path(temp_directory)
        (temp_root / "storage").mkdir()
        engine = create_engine(f"sqlite:///{(temp_root / 'phase10_12a.db').as_posix()}")
        TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)

        with TestingSession() as db:
            admin_role = Role(roleName="Admin")
            operator_role = Role(roleName="User")
            department = Department(departmentName="Computer Science", status="Active")
            db.add_all([admin_role, operator_role, department])
            db.flush()

            users = [
                User(
                    fullName="Phase 10.12A Admin",
                    email="phase10.12a.admin@fdas.local",
                    passwordHash=hash_password("Phase10.12A-Admin@123"),
                    roleId=admin_role.roleId,
                    status="Approved",
                    accessScope="AllDepartments",
                ),
                User(
                    fullName="Approved Operator",
                    email="phase10.12a.approved@fdas.local",
                    passwordHash=hash_password(OPERATOR_PASSWORD),
                    roleId=operator_role.roleId,
                    status="Approved",
                    assignedDepartmentId=department.departmentId,
                    accessScope="Department",
                ),
                User(
                    fullName="Phase <Operator>",
                    email="phase10.12a.success@fdas.local",
                    passwordHash=hash_password(OPERATOR_PASSWORD),
                    roleId=operator_role.roleId,
                    status="Pending",
                    assignedDepartmentId=department.departmentId,
                    accessScope="Department",
                ),
                User(
                    fullName="Failure Operator",
                    email="phase10.12a.failure@fdas.local",
                    passwordHash=hash_password(OPERATOR_PASSWORD),
                    roleId=operator_role.roleId,
                    status="Pending",
                    assignedDepartmentId=department.departmentId,
                    accessScope="Department",
                ),
                User(
                    fullName="Unauthorized Target",
                    email="phase10.12a.unauthorized@fdas.local",
                    passwordHash=hash_password(OPERATOR_PASSWORD),
                    roleId=operator_role.roleId,
                    status="Pending",
                    assignedDepartmentId=department.departmentId,
                    accessScope="Department",
                ),
                User(
                    fullName="Unconfigured SMTP Operator",
                    email="phase10.12a.unconfigured@fdas.local",
                    passwordHash=hash_password(OPERATOR_PASSWORD),
                    roleId=operator_role.roleId,
                    status="Pending",
                    assignedDepartmentId=department.departmentId,
                    accessScope="Department",
                ),
            ]
            db.add_all(users)
            db.commit()
            for user in users:
                db.refresh(user)

            admin_id = users[0].userId
            approved_operator_id = users[1].userId
            pending_success_id = users[2].userId
            pending_failure_id = users[3].userId
            pending_unauthorized_id = users[4].userId
            pending_unconfigured_id = users[5].userId
            department_id = department.departmentId
            pending_success_hash = users[2].passwordHash

        approval_payload = AccessUpdateRequest(
            assignedDepartmentId=department_id,
            accessScope="Department",
        )
        delivery_calls: list[dict] = []
        delivery_saw_committed_approval = False

        def successful_delivery(**kwargs):
            nonlocal delivery_saw_committed_approval
            with TestingSession() as check_db:
                persisted = check_db.get(User, pending_success_id)
                delivery_saw_committed_approval = persisted is not None and persisted.status == "Approved"
            delivery_calls.append(kwargs)
            return EmailDeliveryResult(True, "Approval email sent successfully.")

        with TestingSession() as db:
            admin = db.get(User, admin_id)
            with patch("app.routers.admin_users.send_approval_email", side_effect=successful_delivery) as mocked_delivery:
                approval_response = admin_users.approve_user(
                    pending_success_id,
                    approval_payload,
                    admin,
                    db,
                )
                duplicate_rejected = expect_http_status(
                    lambda: admin_users.approve_user(
                        pending_success_id,
                        approval_payload,
                        admin,
                        db,
                    ),
                    409,
                )
                results["approval_email_service_called_once"] = mocked_delivery.call_count == 1

        with TestingSession() as db:
            approved = db.get(User, pending_success_id)
            user_count_after_duplicate = db.query(User).count()
        results["pending_operator_approved"] = (
            approved is not None
            and approved.status == "Approved"
            and approval_response["user"].status == "Approved"
        )
        results["email_called_after_commit"] = delivery_saw_committed_approval
        results["approval_response_reports_email_success"] = (
            approval_response["emailNotificationSent"] is True
            and approval_response["emailNotificationMessage"] == "Approval email sent successfully."
        )
        results["correct_recipient_used"] = bool(
            delivery_calls
            and delivery_calls[0].get("recipient_email") == "phase10.12a.success@fdas.local"
        )
        results["actual_department_used"] = bool(
            delivery_calls and delivery_calls[0].get("department_name") == "Computer Science"
        )
        results["duplicate_approval_rejected_without_duplicate_account_or_email"] = (
            duplicate_rejected and user_count_after_duplicate == 6 and len(delivery_calls) == 1
        )

        with TestingSession() as db:
            admin = db.get(User, admin_id)
            with patch(
                "app.routers.admin_users.send_approval_email",
                return_value=EmailDeliveryResult(False, "Approval email could not be sent."),
            ) as failed_delivery:
                failure_response = admin_users.approve_user(
                    pending_failure_id,
                    approval_payload,
                    admin,
                    db,
                )
        with TestingSession() as db:
            failure_user = db.get(User, pending_failure_id)
        results["smtp_failure_does_not_undo_approval"] = (
            failure_response["emailNotificationSent"] is False
            and failure_user is not None
            and failure_user.status == "Approved"
            and failed_delivery.call_count == 1
        )

        with TestingSession() as db:
            operator = db.get(User, approved_operator_id)
            operator_blocked = expect_http_status(lambda: require_admin(operator), 403)
        approval_route_is_admin_only = any(
            route.path == "/api/admin/users/{userId}/approve"
            and any(dependency.call is require_admin for dependency in route.dependant.dependencies)
            for route in admin_users.router.routes
        )
        resend_route_is_admin_only = any(
            route.path == "/api/admin/users/{userId}/resend-approval-email"
            and any(dependency.call is require_admin for dependency in route.dependant.dependencies)
            for route in admin_users.router.routes
        )
        results["operator_cannot_approve_or_resend"] = (
            operator_blocked and approval_route_is_admin_only and resend_route_is_admin_only
        )

        with TestingSession() as db:
            admin = db.get(User, admin_id)
            with patch(
                "app.routers.admin_users.send_approval_email",
                return_value=EmailDeliveryResult(True, "Approval email sent successfully."),
            ) as resend_delivery:
                resend_response = admin_users.resend_approval_email(approved_operator_id, admin, db)
                pending_resend_rejected = expect_http_status(
                    lambda: admin_users.resend_approval_email(pending_unauthorized_id, admin, db),
                    409,
                )
        with TestingSession() as db:
            resent_user = db.get(User, approved_operator_id)
        results["admin_resend_is_explicit_and_non_mutating"] = (
            resend_response["emailNotificationSent"] is True
            and pending_resend_rejected
            and resend_delivery.call_count == 1
            and resent_user is not None
            and resent_user.status == "Approved"
        )

        blank_smtp_environment = {key: "" for key in SMTP_ENVIRONMENT_KEYS}
        with TestingSession() as db, ExitStack() as stack:
            admin = db.get(User, admin_id)
            stack.enter_context(patch.dict(os.environ, blank_smtp_environment, clear=False))
            stack.enter_context(
                patch("app.routers.admin_users.send_approval_email", email_service.send_approval_email)
            )
            unconfigured_response = admin_users.approve_user(
                pending_unconfigured_id,
                approval_payload,
                admin,
                db,
            )
            unconfigured_settings = email_service.load_smtp_settings()
        with TestingSession() as db:
            unconfigured_user = db.get(User, pending_unconfigured_id)
        results["smtp_not_configured_is_graceful"] = (
            unconfigured_settings.configured is False
            and unconfigured_response["emailNotificationSent"] is False
            and "not configured" in unconfigured_response["emailNotificationMessage"]
            and unconfigured_user is not None
            and unconfigured_user.status == "Approved"
        )

        FakeSmtp.instances.clear()
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, smtp_environment(), clear=False))
            stack.enter_context(patch("app.services.email_service.smtplib.SMTP", FakeSmtp))
            transport_result = email_service.send_approval_email(
                operator_name="Phase <Operator>",
                recipient_email="phase10.12a.success@fdas.local",
                department_name="Computer Science",
            )

        smtp_instance = FakeSmtp.instances[-1]
        email_message = smtp_instance.message
        plain_body = email_message.get_body(preferencelist=("plain",)).get_content()
        html_body = email_message.get_body(preferencelist=("html",)).get_content()
        serialized_message = email_message.as_string()
        results["smtp_transport_success_and_tls"] = (
            transport_result.sent is True
            and smtp_instance.host == "smtp.test.local"
            and smtp_instance.port == 587
            and smtp_instance.started_tls
            and smtp_instance.login_credentials == ("smtp-user", "smtp-test-secret")
        )
        results["correct_subject_and_multipart_content"] = (
            email_message["Subject"] == APPROVAL_EMAIL_SUBJECT
            and email_message["To"] == "phase10.12a.success@fdas.local"
            and "Phase <Operator>" in plain_body
            and "phase10.12a.success@fdas.local" in plain_body
            and "Computer Science" in plain_body
            and "Account Status:\nApproved" in plain_body
            and "&lt;Operator&gt;" in html_body
            and email_message.is_multipart()
        )
        results["password_and_hash_absent_from_email"] = (
            OPERATOR_PASSWORD not in serialized_message
            and pending_success_hash not in serialized_message
            and "smtp-test-secret" not in serialized_message
        )

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, smtp_environment(), clear=False))
            stack.enter_context(patch("app.services.email_service.smtplib.SMTP", FailingSmtp))
            failed_transport_result = email_service.send_approval_email(
                operator_name="Failure Operator",
                recipient_email="phase10.12a.failure@fdas.local",
                department_name="Computer Science",
            )
        results["raw_smtp_failure_is_safely_reported"] = (
            failed_transport_result.sent is False
            and failed_transport_result.message == "Approval email could not be sent."
        )

        built_content = build_approval_email(
            operator_name="Phase <Operator>",
            login_id="phase10.12a.success@fdas.local",
            department_name="Computer Science",
        )
        results["content_builder_has_text_and_safe_html"] = (
            built_content.subject == APPROVAL_EMAIL_SUBJECT
            and "Phase <Operator>" in built_content.text_body
            and "&lt;Operator&gt;" in built_content.html_body
            and "Computer Science" in built_content.text_body
        )

        engine.dispose()

    for name, passed in results.items():
        print(f"{name}={passed}")

    if not results or not all(results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
