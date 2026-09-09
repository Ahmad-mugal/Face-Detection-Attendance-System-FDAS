from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models.classroom import ClassRoom
from app.models.department import Department
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.utils.security import hash_demo_password


ROLE_NAMES = ["Admin", "User"]
DEPARTMENT_NAMES = ["Computer Science", "IT", "Mathematics", "Physics"]


def seed_database(db: Session | None = None):
    owns_session = db is None
    session = db or SessionLocal()

    try:
        roles_by_name = {}
        for role_name in ROLE_NAMES:
            role = session.query(Role).filter(Role.roleName == role_name).one_or_none()
            if role is None:
                role = Role(roleName=role_name)
                session.add(role)
                session.flush()
            roles_by_name[role_name] = role

        departments_by_name = {}
        for department_name in DEPARTMENT_NAMES:
            department = session.query(Department).filter(Department.departmentName == department_name).one_or_none()
            if department is None:
                department = Department(departmentName=department_name, status="Active")
                session.add(department)
                session.flush()
            departments_by_name[department_name] = department

        admin = session.query(User).filter(User.email == "admin@fdas.local").one_or_none()
        if admin is None:
            session.add(
                User(
                    fullName="Admin User",
                    email="admin@fdas.local",
                    passwordHash=hash_demo_password("Admin@12345"),
                    roleId=roles_by_name["Admin"].roleId,
                    status="Approved",
                    assignedDepartmentId=None,
                    accessScope="AllDepartments",
                )
            )
        elif admin.passwordHash == "Admin@12345":
            admin.passwordHash = hash_demo_password("Admin@12345")

        operator = session.query(User).filter(User.email == "operator.cs@fdas.local").one_or_none()
        if operator is None:
            session.add(
                User(
                    fullName="CS Operator",
                    email="operator.cs@fdas.local",
                    passwordHash=hash_demo_password("Operator@12345"),
                    roleId=roles_by_name["User"].roleId,
                    status="Approved",
                    assignedDepartmentId=departments_by_name["Computer Science"].departmentId,
                    accessScope="Department",
                )
            )

        classroom_specs = [
            ("BSCS Semester 5 - A", "Computer Science", "Semester 5", "A"),
            ("BSIT Semester 3 - A", "IT", "Semester 3", "A"),
        ]
        classrooms_by_name = {}
        for class_name, department_name, year_semester, section in classroom_specs:
            classroom = session.query(ClassRoom).filter(ClassRoom.className == class_name).one_or_none()
            if classroom is None:
                classroom = ClassRoom(
                    className=class_name,
                    departmentId=departments_by_name[department_name].departmentId,
                    yearSemester=year_semester,
                    section=section,
                    status="Active",
                )
                session.add(classroom)
                session.flush()
            classrooms_by_name[class_name] = classroom

        student_specs = [
            ("CS-2026-001", "Ayesha Khan", "ayesha.khan@example.local", "Computer Science", "BSCS Semester 5 - A"),
            ("CS-2026-002", "Bilal Ahmed", "bilal.ahmed@example.local", "Computer Science", "BSCS Semester 5 - A"),
            ("IT-2026-001", "Sara Malik", "sara.malik@example.local", "IT", "BSIT Semester 3 - A"),
        ]
        for roll_no, full_name, email, department_name, class_name in student_specs:
            student = session.query(Student).filter(Student.rollNo == roll_no).one_or_none()
            classroom = classrooms_by_name[class_name]
            if student is None:
                session.add(
                    Student(
                        rollNo=roll_no,
                        fullName=full_name,
                        email=email,
                        phone=None,
                        departmentId=departments_by_name[department_name].departmentId,
                        classId=classroom.classId,
                        yearSemester=classroom.yearSemester,
                        section=classroom.section,
                        status="Active",
                    )
                )

        session.commit()
    finally:
        if owns_session:
            session.close()


if __name__ == "__main__":
    init_db()
    seed_database()
    print("FDAS local SQLite database initialized and seeded.")
