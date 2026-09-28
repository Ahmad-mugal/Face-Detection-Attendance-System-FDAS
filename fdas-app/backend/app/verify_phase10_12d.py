from __future__ import annotations

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.dependencies import require_admin
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.face_template import FaceTemplate
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.notification import Notification
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.routers import admin_users
from app.routers.notifications import to_notification_read
from app.routers.students import to_student_read
from app.services.face_enrollment import student_face_registered
from app.services.notifications import (
    create_notification,
    get_visible_notification,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    unread_count,
)
from app.services.student_import import (
    STUDENT_IMPORT_HEADERS,
    import_valid_students,
    template_csv,
    validate_student_csv,
)
from app.services.students import delete_student_safely
from app.utils.security import hash_password


def expect_http_status(callback, expected_status: int) -> bool:
    try:
        callback()
    except HTTPException as exc:
        return exc.status_code == expected_status
    return False


def csv_bytes(*rows: str) -> bytes:
    return (",".join(STUDENT_IMPORT_HEADERS) + "\n" + "\n".join(rows) + "\n").encode("utf-8")


def main() -> None:
    results: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="fdas-phase10-12d-") as directory:
        root = Path(directory)
        storage_root = root / "storage" / "face_enrollments"
        storage_root.mkdir(parents=True)
        engine = create_engine(f"sqlite:///{(root / 'phase10_12d.db').as_posix()}")
        TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=engine)

        with TestingSession() as db:
            admin_role = Role(roleName="Admin")
            user_role = Role(roleName="User")
            cs = Department(departmentName="Computer Science", status="Active")
            it = Department(departmentName="IT", status="Active")
            db.add_all([admin_role, user_role, cs, it])
            db.flush()
            cs_class = ClassRoom(className="BSCS Semester 5 - A", departmentId=cs.departmentId, yearSemester="Semester 5", section="A", status="Active")
            it_class = ClassRoom(className="BSIT Semester 3 - A", departmentId=it.departmentId, yearSemester="Semester 3", section="A", status="Active")
            db.add_all([cs_class, it_class])
            db.flush()
            admin = User(fullName="Protected Admin", email="admin@phase10.12d.local", passwordHash=hash_password("Admin-Test-123"), roleId=admin_role.roleId, status="Approved", accessScope="AllDepartments")
            second_admin = User(fullName="Second Admin", email="admin2@phase10.12d.local", passwordHash=hash_password("Admin-Test-456"), roleId=admin_role.roleId, status="Approved", accessScope="AllDepartments")
            cs_operator = User(fullName="CS Operator", email="cs.operator@phase10.12d.local", passwordHash=hash_password("Operator-Test-123"), roleId=user_role.roleId, status="Approved", assignedDepartmentId=cs.departmentId, accessScope="Department")
            it_operator = User(fullName="IT Operator", email="it.operator@phase10.12d.local", passwordHash=hash_password("Operator-Test-456"), roleId=user_role.roleId, status="Approved", assignedDepartmentId=it.departmentId, accessScope="Department")
            all_operator = User(fullName="All Operator", email="all.operator@phase10.12d.local", passwordHash=hash_password("Operator-Test-789"), roleId=user_role.roleId, status="Approved", accessScope="AllDepartments")
            eligible_operator = User(fullName="Eligible Operator", email="delete.operator@phase10.12d.local", passwordHash=hash_password("Delete-Test-123"), roleId=user_role.roleId, status="Approved", assignedDepartmentId=cs.departmentId, accessScope="Department")
            dependent_operator = User(fullName="Dependent Operator", email="dependent.operator@phase10.12d.local", passwordHash=hash_password("Dependent-Test-123"), roleId=user_role.roleId, status="Approved", assignedDepartmentId=cs.departmentId, accessScope="Department")
            db.add_all([admin, second_admin, cs_operator, it_operator, all_operator, eligible_operator, dependent_operator])
            db.flush()

            safe_student = Student(rollNo="SAFE-DELETE", fullName="Safe Delete", email="safe.delete@example.local", departmentId=cs.departmentId, classId=cs_class.classId, yearSemester=cs_class.yearSemester, section=cs_class.section, status="Active")
            history_student = Student(rollNo="HISTORY-KEEP", fullName="History Keep", email="history.keep@example.local", departmentId=cs.departmentId, classId=cs_class.classId, yearSemester=cs_class.yearSemester, section=cs_class.section, status="Active")
            it_student = Student(rollNo="IT-PRIVATE", fullName="IT Private", email="it.private@example.local", departmentId=it.departmentId, classId=it_class.classId, yearSemester=it_class.yearSemester, section=it_class.section, status="Inactive")
            db.add_all([safe_student, history_student, it_student])
            db.flush()

            safe_directory = storage_root / str(safe_student.studentId)
            safe_directory.mkdir()
            safe_file = safe_directory / "sample.jpg"
            safe_file.write_bytes(b"isolated-face-sample")
            safe_template = FaceTemplate(
                studentId=safe_student.studentId,
                templatePath=f"storage/face_enrollments/{safe_student.studentId}/sample.jpg",
                encodingData="[1.0,0.0]",
                encodingVersion="opencv_basic_v1",
                status="Encoded",
                isActive=True,
                createdByUserId=dependent_operator.userId,
            )
            db.add(safe_template)
            db.flush()
            db.add(FaceTemplateEmbedding(
                faceTemplateId=safe_template.templateId,
                studentId=safe_student.studentId,
                encodingVersion="arcface_v1",
                embeddingData="[1.0,0.0]",
                embeddingDimension=2,
                modelName="test",
                sourceImageSha256="a" * 64,
                l2Norm=1.0,
                isActive=True,
            ))
            session = AttendanceSession(
                departmentId=cs.departmentId,
                startedByUserId=cs_operator.userId,
                scheduledStartTime=datetime.now(),
                scheduledEndTime=datetime.now() + timedelta(hours=1),
                actualStartTime=datetime.now(),
                status="Closed",
                createdDate=date.today(),
            )
            db.add(session)
            db.flush()
            db.add(AttendanceRecord(
                sessionId=session.sessionId,
                studentId=history_student.studentId,
                departmentId=cs.departmentId,
                classId=cs_class.classId,
                status="Present",
            ))
            db.commit()
            for item in (admin, second_admin, cs_operator, it_operator, all_operator, eligible_operator, dependent_operator, safe_student, history_student, it_student):
                db.refresh(item)

            admin_notice = create_notification(db, recipient_role="Admin", type="ADMIN_TEST", severity="INFO", title="Admin update", message="Visible only to administrators.", action_url="/admin/users", commit=True)
            cs_notice = create_notification(db, recipient_role="User", department_id=cs.departmentId, type="CS_TEST", severity="WARNING", title="CS update", message="Computer Science operational update.", action_url="/user/students", commit=True)
            it_notice = create_notification(db, recipient_role="User", department_id=it.departmentId, type="IT_TEST", severity="INFO", title="IT update", message="IT operational update.", action_url="/user/students", commit=True)
            private_notice = create_notification(db, recipient_user_id=cs_operator.userId, type="PRIVATE_TEST", severity="ACTION_REQUIRED", title="Private update", message="Private operator update.", action_url="/account/profile", commit=True)

            results["notification_creation"] = db.query(Notification).count() == 4
            created_transport = to_notification_read(private_notice).model_dump(mode="json")
            results["notification_created_at_serialized_as_utc"] = created_transport["createdAt"].endswith("Z")
            results["admin_notification_scope"] = {item.notificationId for item in list_notifications(db, admin)} == {admin_notice.notificationId}
            results["operator_department_scope"] = {item.notificationId for item in list_notifications(db, cs_operator)} == {cs_notice.notificationId, private_notice.notificationId}
            results["all_departments_operator_scope"] = {item.notificationId for item in list_notifications(db, all_operator)} == {cs_notice.notificationId, it_notice.notificationId}
            results["unauthorized_notification_retrieval_blocked"] = get_visible_notification(db, it_operator, private_notice.notificationId) is None
            results["unread_count"] = unread_count(db, cs_operator) == 2
            mark_notification_read(db, private_notice)
            read_transport = to_notification_read(private_notice).model_dump(mode="json")
            results["notification_read_at_serialized_as_utc"] = read_transport["readAt"].endswith("Z")
            results["mark_read"] = unread_count(db, cs_operator) == 1
            results["mark_all_read"] = mark_all_notifications_read(db, cs_operator) == 1 and unread_count(db, cs_operator) == 0

            results["operator_cannot_delete_users"] = expect_http_status(lambda: require_admin(cs_operator), 403)
            results["user_self_delete_protected"] = expect_http_status(lambda: admin_users.delete_user(admin.userId, admin, db), 409)
            results["protected_admin_delete_blocked"] = expect_http_status(lambda: admin_users.delete_user(second_admin.userId, admin, db), 409)
            results["dependent_user_delete_blocked"] = expect_http_status(lambda: admin_users.delete_user(dependent_operator.userId, admin, db), 409)
            eligible_id = eligible_operator.userId
            response = admin_users.delete_user(eligible_id, admin, db)
            results["eligible_operator_deleted"] = response.deleted and db.get(User, eligible_id) is None
            results["nonexistent_user_delete_404"] = expect_http_status(lambda: admin_users.delete_user(999999, admin, db), 404)

            safe_id = safe_student.studentId
            delete_student_safely(db, admin, safe_id, storage_root=storage_root)
            results["safe_student_hard_delete"] = db.get(Student, safe_id) is None
            results["no_orphan_face_rows_or_storage"] = (
                db.query(FaceTemplate).filter(FaceTemplate.studentId == safe_id).count() == 0
                and db.query(FaceTemplateEmbedding).filter(FaceTemplateEmbedding.studentId == safe_id).count() == 0
                and not safe_directory.exists()
            )
            results["attendance_student_delete_blocked"] = expect_http_status(lambda: delete_student_safely(db, admin, history_student.studentId, storage_root=storage_root), 409)
            results["unauthorized_operator_student_delete_blocked"] = expect_http_status(lambda: delete_student_safely(db, cs_operator, it_student.studentId, storage_root=storage_root), 403)
            results["student_status_handling_unchanged"] = db.get(Student, it_student.studentId).status == "Inactive"

            results["valid_template"] = template_csv().strip() == ",".join(STUDENT_IMPORT_HEADERS)
            valid_csv = csv_bytes("Ali Khan,ali.import@example.com,CS-IMPORT-001,Computer Science,BSCS Semester 5 - A")
            preview, _ = validate_student_csv(valid_csv, admin, db)
            results["valid_csv_preview"] = preview["validRows"] == 1 and preview["invalidRows"] == 0
            results["missing_header_rejected"] = expect_http_status(lambda: validate_student_csv(b"Name,Email\nA,a@example.com\n", admin, db), 422)
            invalid_email, _ = validate_student_csv(csv_bytes("Bad Email,not-an-email,CS-BAD-EMAIL,Computer Science,BSCS Semester 5 - A"), admin, db)
            results["invalid_email_rejected"] = invalid_email["invalidRows"] == 1
            duplicate_preview, _ = validate_student_csv(csv_bytes(
                "First Student,duplicate@example.com,DUP-ROLL-1,Computer Science,BSCS Semester 5 - A",
                "Second Student,duplicate@example.com,DUP-ROLL-2,Computer Science,BSCS Semester 5 - A",
                "Third Student,third@example.com,DUP-ROLL-2,Computer Science,BSCS Semester 5 - A",
            ), admin, db)
            results["duplicate_email_rejected"] = any("Duplicate Email" in " ".join(row["issues"]) for row in duplicate_preview["rows"])
            results["duplicate_roll_rejected"] = any("Duplicate Roll Number" in " ".join(row["issues"]) for row in duplicate_preview["rows"])
            unknown_department, _ = validate_student_csv(csv_bytes("Unknown Dept,unknown.dept@example.com,UNKNOWN-DEPT,Computer Sciense,BSCS Semester 5 - A"), admin, db)
            results["unknown_department_rejected"] = unknown_department["invalidRows"] == 1 and "Unknown Department" in unknown_department["rows"][0]["issues"]
            unknown_class, _ = validate_student_csv(csv_bytes("Unknown Class,unknown.class@example.com,UNKNOWN-CLASS,Computer Science,BSCS Semester 99 - Z"), admin, db)
            results["unknown_class_rejected"] = "Unknown Class" in unknown_class["rows"][0]["issues"]
            mismatch, _ = validate_student_csv(csv_bytes("Wrong Class,wrong.class@example.com,WRONG-CLASS,Computer Science,BSIT Semester 3 - A"), admin, db)
            results["class_department_mismatch_rejected"] = "Class does not belong to Department" in mismatch["rows"][0]["issues"]
            unauthorized, _ = validate_student_csv(csv_bytes("Unauthorized,unauthorized@example.com,IT-UNAUTHORIZED,IT,BSIT Semester 3 - A"), cs_operator, db)
            results["operator_department_import_enforced"] = "Unauthorized Department" in unauthorized["rows"][0]["issues"]

            import_result = import_valid_students(valid_csv, admin, db)
            imported_id = import_result["students"][0]["studentId"]
            imported = db.get(Student, imported_id)
            second_preview, _ = validate_student_csv(valid_csv, admin, db)
            results["same_csv_is_idempotent"] = second_preview["existingRows"] == 1 and import_valid_students(valid_csv, admin, db)["imported"] == 0
            results["imported_student_pending_face"] = not student_face_registered(imported) and import_result["students"][0]["faceStatus"] == "Pending Face Registration"
            results["imported_student_available_to_enrollment"] = to_student_read(imported).studentId == imported_id and not to_student_read(imported).faceRegistered
            results["import_creates_meaningful_notification"] = db.query(Notification).filter(Notification.type == "STUDENT_IMPORT_COMPLETED", Notification.recipientUserId == admin.userId).count() >= 1

            rollback_csv = csv_bytes("Rollback Student,rollback@example.com,ROLLBACK-001,Computer Science,BSCS Semester 5 - A")
            count_before = db.query(Student).count()
            original_commit = db.commit
            with patch.object(db, "commit", side_effect=RuntimeError("synthetic batch failure")):
                try:
                    import_valid_students(rollback_csv, admin, db)
                except RuntimeError:
                    pass
            results["transactional_batch_failure_rollback"] = db.query(Student).count() == count_before
            original_commit()

        engine.dispose()

    for name, passed in results.items():
        print(f"{name}={passed}")
    if not results or not all(results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
