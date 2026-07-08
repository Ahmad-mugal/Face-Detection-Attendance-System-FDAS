from app.models.user import User


def can_access_department(user: User, departmentId: int) -> bool:
    role_name = user.role.roleName if user.role else ""
    if role_name == "Admin":
        return True
    if user.accessScope == "AllDepartments":
        return True
    if user.accessScope == "Department":
        return user.assignedDepartmentId == departmentId
    return False
