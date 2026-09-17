from __future__ import annotations

import io
import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.database import Base
from app.dependencies import require_admin
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.routers import admin_users, students as student_routes
from app.schemas.auth import AccessUpdateRequest
from app.services import email_service
from app.services.email_service import EmailDeliveryResult, SMTP_ENVIRONMENT_KEYS
from app.utils.security import hash_password


SMTP_SECRET = "phase10-12b-secret-not-for-logs"


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_credentials = None
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
        raise OSError(f"synthetic transport failure; credential={SMTP_SECRET}")


def smtp_values(host: str = "smtp.test.local") -> dict[str, str]:
    return {
        "FDAS_SMTP_HOST": host,
        "FDAS_SMTP_PORT": "587",
        "FDAS_SMTP_USERNAME": "smtp-user",
        "FDAS_SMTP_PASSWORD": SMTP_SECRET,
        "FDAS_SMTP_FROM_EMAIL": "fdas@test.local",
        "FDAS_SMTP_FROM_NAME": "FDAS Test",
        "FDAS_SMTP_USE_TLS": "true",
    }


@contextmanager
def isolated_smtp_environment(values: dict[str, str] | None = None):
    original = {key: os.environ.get(key) for key in SMTP_ENVIRONMENT_KEYS}
    try:
        for key in SMTP_ENVIRONMENT_KEYS:
            os.environ.pop(key, None)
        for key, value in (values or {}).items():
            os.environ[key] = value
        yield
    finally:
        for key in SMTP_ENVIRONMENT_KEYS:
            os.environ.pop(key, None)
        for key, value in original.items():
            if value is not None:
                os.environ[key] = value


def expect_http_status(callback, expected_status: int) -> bool:
    try:
        callback()
    except HTTPException as exc:
        return exc.status_code == expected_status
    return False


def list_students_by_status(status_value: str, current_user: User, db):
    return student_routes.list_students(
        departmentId=None,
        classId=None,
        status=status_value,
        search=None,
        current_user=current_user,
        db=db,
    )


def main() -> None:
    results: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="fdas-phase10-12b-") as temp_directory:
        temp_root = Path(temp_directory)
        environment_file = temp_root / ".env"
        environment_file.write_text(
            "\n".join(f"{key}={value}" for key, value in smtp_values().items()),
            encoding="utf-8",
        )

        with isolated_smtp_environment():
            loaded = config.load_local_environment(environment_file)
            discovered = email_service.load_smtp_settings()
            results["backend_env_discovery"] = loaded and discovered.configured and discovered.host == "smtp.test.local"

        with isolated_smtp_environment({"FDAS_SMTP_HOST": "smtp.host-precedence.local"}):
            config.load_local_environment(environment_file)
            precedence = email_service.load_smtp_settings()
            results["host_environment_has_precedence"] = precedence.host == "smtp.host-precedence.local"

        with isolated_smtp_environment():
            missing_loaded = config.load_local_environment(temp_root / "missing.env")
            missing_settings = email_service.load_smtp_settings()
            missing_capability = email_service.get_email_capability()
            results["missing_config_is_nonfatal"] = (
                missing_loaded is False
                and missing_settings.configured is False
                and missing_capability == {
                    "configured": False,
                    "deliveryOptional": True,
                    "message": "Approval email unavailable because SMTP is not configured.",
                }
            )

        FakeSmtp.instances.clear()
        with isolated_smtp_environment(smtp_values()), patch("app.services.email_service.smtplib.SMTP", FakeSmtp):
            success = email_service.send_approval_email(
                operator_name="Phase 10.12B Operator",
                recipient_email="operator@test.local",
                department_name="Computer Science",
            )
            capability = email_service.get_email_capability()
        smtp = FakeSmtp.instances[-1]
        serialized_email = smtp.message.as_string()
        results["configured_state_is_public_safe"] = (
            capability == {
                "configured": True,
                "deliveryOptional": True,
                "message": "Approval email delivery is configured.",
            }
            and SMTP_SECRET not in str(capability)
        )
        results["mocked_smtp_success"] = (
            success.sent
            and smtp.started_tls
            and smtp.login_credentials == ("smtp-user", SMTP_SECRET)
            and SMTP_SECRET not in serialized_email
        )

        log_output = io.StringIO()
        handler = logging.StreamHandler(log_output)
        email_service.logger.addHandler(handler)
        try:
            with isolated_smtp_environment(smtp_values()), patch("app.services.email_service.smtplib.SMTP", FailingSmtp):
                failure = email_service.send_approval_email(
                    operator_name="Failure Operator",
                    recipient_email="failure@test.local",
                    department_name="Computer Science",
                )
        finally:
            email_service.logger.removeHandler(handler)
        results["mocked_smtp_failure_is_safe"] = (
            failure.sent is False
            and failure.message == "Approval email could not be sent."
            and SMTP_SECRET not in log_output.getvalue()
        )

        engine = create_engine(f"sqlite:///{(temp_root / 'phase10_12b.db').as_posix()}")
        TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        Base.metadata.create_all(bind=engine)
        with TestingSession() as db:
            admin_role = Role(roleName="Admin")
            operator_role = Role(roleName="User")
            department_one = Department(departmentName="Computer Science", status="Active")
            department_two = Department(departmentName="Information Technology", status="Active")
            db.add_all([admin_role, operator_role, department_one, department_two])
            db.flush()
            class_one = ClassRoom(className="CS-6", departmentId=department_one.departmentId, yearSemester="6", section="A", status="Active")
            class_two = ClassRoom(className="IT-6", departmentId=department_two.departmentId, yearSemester="6", section="A", status="Active")
            db.add_all([class_one, class_two])
            db.flush()
            admin = User(fullName="Phase 10.12B Admin", email="admin@phase10.12b.local", passwordHash=hash_password("Admin-Phase10.12B"), roleId=admin_role.roleId, status="Approved", accessScope="AllDepartments")
            operator = User(fullName="Scoped Operator", email="operator@phase10.12b.local", passwordHash=hash_password("Operator-Phase10.12B"), roleId=operator_role.roleId, status="Approved", assignedDepartmentId=department_one.departmentId, accessScope="Department")
            pending = User(fullName="Pending Operator", email="pending@phase10.12b.local", passwordHash=hash_password("Pending-Phase10.12B"), roleId=operator_role.roleId, status="Pending", assignedDepartmentId=department_one.departmentId, accessScope="Department")
            approved = User(fullName="Approved Operator", email="approved@phase10.12b.local", passwordHash=hash_password("Approved-Phase10.12B"), roleId=operator_role.roleId, status="Approved", assignedDepartmentId=department_one.departmentId, accessScope="Department")
            db.add_all([admin, operator, pending, approved])
            db.flush()
            db.add_all([
                Student(rollNo="CS-ACTIVE", fullName="CS Active", email="cs-active@test.local", departmentId=department_one.departmentId, classId=class_one.classId, yearSemester="6", section="A", status="Active"),
                Student(rollNo="CS-INACTIVE", fullName="CS Inactive", email="cs-inactive@test.local", departmentId=department_one.departmentId, classId=class_one.classId, yearSemester="6", section="A", status="Inactive"),
                Student(rollNo="CS-DISABLED", fullName="CS Disabled", email="cs-disabled@test.local", departmentId=department_one.departmentId, classId=class_one.classId, yearSemester="6", section="A", status="Disabled"),
                Student(rollNo="IT-ACTIVE", fullName="IT Active", email="it-active@test.local", departmentId=department_two.departmentId, classId=class_two.classId, yearSemester="6", section="A", status="Active"),
            ])
            db.commit()
            for item in (admin, operator, pending, approved):
                db.refresh(item)

            admin_active = list_students_by_status("active", admin, db)
            admin_inactive = list_students_by_status("inactive", admin, db)
            operator_active = list_students_by_status("active", operator, db)
            operator_inactive = list_students_by_status("inactive", operator, db)
            results["student_status_views_and_scope"] = (
                {student.rollNo for student in admin_active} == {"CS-ACTIVE", "IT-ACTIVE"}
                and {student.rollNo for student in admin_inactive} == {"CS-INACTIVE", "CS-DISABLED"}
                and {student.rollNo for student in operator_active} == {"CS-ACTIVE"}
                and {student.rollNo for student in operator_inactive} == {"CS-INACTIVE", "CS-DISABLED"}
            )

            disabled = next(student for student in admin_inactive if student.rollNo == "CS-DISABLED")
            student_routes.enable_student(disabled.studentId, operator, db)
            reactivated = list_students_by_status("active", operator, db)
            results["reactivation_moves_student_to_active"] = {student.rollNo for student in reactivated} == {"CS-ACTIVE", "CS-DISABLED"}

            active = next(student for student in reactivated if student.rollNo == "CS-ACTIVE")
            student_routes.disable_student(active.studentId, operator, db)
            moved_inactive = list_students_by_status("inactive", operator, db)
            results["deactivation_preserves_record_and_moves_view"] = {student.rollNo for student in moved_inactive} == {"CS-ACTIVE", "CS-INACTIVE"}

            with patch("app.routers.admin_users.send_approval_email", return_value=EmailDeliveryResult(False, "Approval email could not be sent.")):
                approval = admin_users.approve_user(
                    pending.userId,
                    AccessUpdateRequest(assignedDepartmentId=department_one.departmentId, accessScope="Department"),
                    admin,
                    db,
                )
            persisted_pending = db.get(User, pending.userId)
            results["approval_commit_survives_smtp_failure"] = (
                approval["emailNotificationSent"] is False
                and persisted_pending is not None
                and persisted_pending.status == "Approved"
            )

            with patch("app.routers.admin_users.send_approval_email", return_value=EmailDeliveryResult(True, "Approval email sent successfully.")):
                resend = admin_users.resend_approval_email(approved.userId, admin, db)
            results["admin_resend_works"] = resend["emailNotificationSent"] is True and db.get(User, approved.userId).status == "Approved"
            results["unauthorized_email_actions_rejected"] = expect_http_status(lambda: require_admin(operator), 403)

            with isolated_smtp_environment(smtp_values()):
                endpoint_capability = admin_users.email_status(admin)
            results["email_status_endpoint_has_no_secrets"] = (
                set(endpoint_capability) == {"configured", "deliveryOptional", "message"}
                and SMTP_SECRET not in str(endpoint_capability)
            )

        engine.dispose()

    for name, passed in results.items():
        print(f"{name}={passed}")
    if not results or not all(results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
