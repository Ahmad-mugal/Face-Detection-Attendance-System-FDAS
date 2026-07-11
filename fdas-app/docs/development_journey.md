# FDAS Development Journey

## Phase 1 - Static React Frontend Shell

### Goal
Build the static React frontend shell from the Stitch screens using dummy data only. Phase 1 intentionally does not include backend APIs, database persistence, real authentication logic, or face recognition.

### Files Created Or Modified
- `frontend/src/components/CameraFrameUpload.jsx`
- `frontend/src/components/FilterBar.jsx`
- `frontend/src/pages/admin/AdminDashboard.jsx`
- `frontend/src/pages/admin/AdminStudents.jsx`
- `frontend/src/pages/admin/AdminAddStudent.jsx`
- `frontend/src/pages/admin/AdminLiveAttendance.jsx`
- `frontend/src/pages/admin/AdminAnalytics.jsx`
- `frontend/src/pages/admin/AdminRequests.jsx`
- `frontend/src/pages/admin/AdminUsers.jsx`
- `frontend/src/pages/admin/AdminClasses.jsx`
- `frontend/src/pages/admin/AdminTiming.jsx`
- `frontend/src/pages/user/UserDashboard.jsx`
- `frontend/src/pages/user/UserStudents.jsx`
- `frontend/src/pages/user/UserAddStudent.jsx`
- `frontend/src/pages/user/UserAttendance.jsx`
- `frontend/src/pages/user/UserReports.jsx`
- `docs/development_journey.md`

### Existing Components Used
- `StatsCard`
- `StudentTable`
- `FilterBar`
- `AttendanceChart`
- `AttendanceLogSidebar`
- `CameraEnrollment`
- `CameraFrameUpload`
- `CSVExportButton`

### Pages Created
- `/admin/dashboard`
- `/admin/students`
- `/admin/students/add`
- `/admin/attendance/live`
- `/admin/analytics`
- `/admin/requests`
- `/admin/users`
- `/admin/classes`
- `/admin/timing`
- `/user/dashboard`
- `/user/students`
- `/user/students/add`
- `/user/attendance`
- `/user/reports`

### Tests And Build Commands Run
- `npm run build` - blocked by Windows PowerShell execution policy for `npm.ps1`.
- `npm.cmd run build` - passed. Vite build completed successfully with a non-blocking chunk-size warning.
- `cmd /c npm run build` - passed. This verifies the requested npm build script directly through the Windows command shell.
- `npm.cmd run dev -- --host 127.0.0.1 --port 5173` - Vite dev server reached ready state at `http://127.0.0.1:5173/`; command timed out because the dev server keeps running.
- `cmd /c npm run dev -- --host 127.0.0.1 --port 5173` - Vite dev server reached ready state at `http://127.0.0.1:5173/`; command timed out because the dev server keeps running.
- `npm.cmd run lint` - passed with no warnings after cleanup.

### Errors Found And Fixed
- The router imported admin and user page modules that did not exist yet, which would cause a blank screen/build failure. Added all required static page modules.
- `docs/development_journey.md` did not exist. Created it for Phase 1 tracking.
- PowerShell blocked `npm run build` through `npm.ps1`; verified the same scripts successfully with `npm.cmd`.
- Existing lint warnings in shared Phase 1 components were fixed by rendering `FilterBar` actions directly and making `CameraFrameUpload` use its `isActive` prop.

### Remaining Issues
- Vite reports a non-blocking production chunk-size warning because the frontend bundle includes charting/router/UI dependencies. This does not prevent Phase 1 from running or building.

## Phase 1.1 - UI QA and Static Interaction Polish

### Issues Fixed
- Removed/avoided broken recognition watermark-style text on admin and user shells by keeping navigation labels clean and explicit.
- Tightened global body/root overflow behavior and added reusable page/table wrappers to prevent unwanted left-right page scrolling.
- Completed Admin Add Student and User Add Student static forms with all required profile fields and face enrollment sections.
- Replaced real camera enrollment behavior with a static dummy 3-sample enrollment preview suitable for Phase 1.1.
- Improved admin setup pages for Pending User Requests, Manage Users, Manage Classes, and Attendance Timing with clearer tables/cards and dummy action flows.
- Improved User Attendance with assigned department, attendance window, session status, Start/Stop Attendance, camera placeholder, liveness text, marked-students log, and duplicate/liveness dummy messages.
- Improved Reports and Analytics pages with visible filters, stable chart containers, export buttons, and wrapped tables.

### Files Changed
- `frontend/src/index.css`
- `frontend/src/layouts/AdminLayout.jsx`
- `frontend/src/layouts/UserLayout.jsx`
- `frontend/src/components/AttendanceChart.jsx`
- `frontend/src/components/CameraEnrollment.jsx`
- `frontend/src/components/CameraFrameUpload.jsx`
- `frontend/src/components/StudentTable.jsx`
- `frontend/src/pages/admin/AdminAddStudent.jsx`
- `frontend/src/pages/admin/AdminAnalytics.jsx`
- `frontend/src/pages/admin/AdminClasses.jsx`
- `frontend/src/pages/admin/AdminDashboard.jsx`
- `frontend/src/pages/admin/AdminLiveAttendance.jsx`
- `frontend/src/pages/admin/AdminRequests.jsx`
- `frontend/src/pages/admin/AdminStudents.jsx`
- `frontend/src/pages/admin/AdminTiming.jsx`
- `frontend/src/pages/admin/AdminUsers.jsx`
- `frontend/src/pages/user/UserAddStudent.jsx`
- `frontend/src/pages/user/UserAttendance.jsx`
- `frontend/src/pages/user/UserDashboard.jsx`
- `frontend/src/pages/user/UserReports.jsx`
- `frontend/src/pages/user/UserStudents.jsx`
- `docs/development_journey.md`

### Dummy Interactions Added
- Login keeps demo credential routing to admin or operator dashboards.
- Logout buttons route back to `/login`.
- Admin and operator notification buttons open small dummy dropdowns.
- Admin and operator profile/avatar buttons open dummy profile menus.
- Admin Settings dropdown links to Manage Users, Manage Classes, Attendance Timing, and Pending Requests.
- Add Student buttons route to their respective add-student pages.
- Export CSV keeps client-side dummy CSV download behavior.
- Pending request Approve/Reject buttons update dummy request status through a confirmation modal.
- Manage Users supports Change Access modal, Grant All Departments, and Enable/Disable dummy state.
- Manage Classes supports Add/Edit modal and Archive/Restore dummy state.
- Attendance Timing supports Add/Edit modal and Activate/Deactivate dummy state.
- Admin live attendance supports Start/Stop Attendance and static Start/Stop Attendance controls.
- User attendance supports Start/Stop Attendance plus dummy duplicate and liveness messages.
- Student Edit/Archive buttons open placeholder confirmation modals.

### Build/Lint Results
- `npm.cmd run build` - passed. Vite completed production build with a non-blocking chunk-size warning.
- `npm.cmd run lint` - passed with no warnings.

### Remaining Issues
- All data remains dummy/static by design.
- No backend, database, real authentication, backend upload, or real face recognition is implemented in Phase 1.1.

### Follow-up Layout Fix
- Fixed the Admin top header overflow by compacting nav spacing, keeping header items non-wrapping, and moving Logout into the profile dropdown.
- Replaced the `face_recognition` Material Symbols ligature in Admin and User navigation with a normal attendance icon so broken `_RØGNITION Attendance` text cannot appear.
- Replaced remaining visible Recognition wording in the static frontend with Attendance wording where it affected Phase 1.1 UI polish.
- Verified with `rg` that `_RØGNITION`, `RØGNITION`, `RECOGNITION Attendance`, `Recognition Attendance`, `face_recognition`, and `Recognition` no longer appear in `frontend/src`.
- `npm.cmd run build` - passed with the existing non-blocking Vite chunk-size warning.
- `npm.cmd run lint` - passed with no warnings.

### Camera and Dropdown Interaction Fix
- Restored browser camera preview for Admin Live Attendance and User Attendance using `navigator.mediaDevices.getUserMedia`.
- Added camera track cleanup when attendance is stopped, when the shared camera is deactivated, and when attendance pages/components unmount.
- Added friendly camera permission-denied messages while keeping recognition and liveness behavior dummy-only.
- Updated Admin dropdown behavior so Settings, notifications, and profile menus are mutually exclusive and close on outside click, Escape, and route navigation.
- Updated User top-bar dropdown behavior so notifications/profile close on outside click, Escape, route navigation, and the Settings icon.
- Kept Admin Logout inside the profile menu and kept Attendance nav labels/icons clean.
- `npm.cmd run build` - passed with the existing non-blocking Vite chunk-size warning.
- `npm.cmd run lint` - passed with no warnings.

### Attendance Control Cleanup
- Removed duplicate Start/Stop Attendance buttons from the Admin Live Attendance camera card header.
- Kept a single top-right Start/Stop Attendance toggle on Admin Live Attendance and User Attendance.
- Camera/card headers now show status badges only: Session Active, Session Inactive, and Camera Active only when the video stream is active.
- The single page-level control starts the live camera preview and stops camera tracks when attendance is stopped.
- `npm.cmd run build` - passed with the existing non-blocking Vite chunk-size warning.
- `npm.cmd run lint` - passed with no warnings.

### Active Attendance Navigation Confirmation
- Added a frontend-only attendance session context shared by Admin Live Attendance, User Attendance, AdminLayout, and UserLayout.
- Attendance pages now mark the shared session active when Start Attendance is clicked and clear it when Stop Attendance is clicked or camera permission is denied.
- Active camera stop callbacks are registered with the shared context so confirmed navigation stops camera tracks before leaving.
- Admin top navigation, Admin settings links, Admin profile logout, User sidebar links, and User logout now show the confirmation message before navigating away from an active attendance page.
- Cancel keeps the user on the same attendance page and leaves the camera/session active.
- Confirm/OK stops the registered camera/session cleanup, marks attendance inactive, and then allows navigation.
- Added `beforeunload` protection for browser refresh/close while attendance is active.
- `npm.cmd run build` - passed with the existing non-blocking Vite chunk-size warning.
- `npm.cmd run lint` - passed with no warnings.

### User Sidebar Active Route Fix
- Updated UserLayout sidebar active-state logic to use exact pathname matching.
- Fixed `/user/students` and `/user/students/add` so only Students or Add Student is highlighted, never both.
- Kept active attendance navigation confirmation behavior on all User sidebar links and Logout.
- `npm.cmd run build` - passed with the existing non-blocking Vite chunk-size warning.
- `npm.cmd run lint` - passed with no warnings.

## Phase 2 - Backend Foundation and Local Database

### Goal
Create the FastAPI backend foundation with a local SQLite database for the single-laptop/offline demo. Phase 2 intentionally does not include frontend API integration, JWT authentication, real attendance marking, OpenCV, MediaPipe, or real face recognition.

### Files Created Or Modified
- `backend/requirements.txt`
- `backend/.gitignore`
- `backend/README.md`
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/seed.py`
- `backend/app/models/__init__.py`
- `backend/app/models/role.py`
- `backend/app/models/department.py`
- `backend/app/models/user.py`
- `backend/app/models/classroom.py`
- `backend/app/models/student.py`
- `backend/app/models/face_template.py`
- `backend/app/models/attendance_time_window.py`
- `backend/app/models/attendance_session.py`
- `backend/app/models/attendance_record.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/foundation.py`
- `backend/app/routers/__init__.py`
- `backend/app/routers/foundation.py`
- `backend/app/services/__init__.py`
- `backend/app/utils/__init__.py`
- `backend/app/utils/security.py`
- `backend/app/verify_phase2.py`
- `docs/development_journey.md`

### Database Models
- `Role`
- `Department`
- `User`
- `ClassRoom`
- `Student`
- `FaceTemplate`
- `AttendanceTimeWindow`
- `AttendanceSession`
- `AttendanceRecord`

### Database Rules
- `User.email` is unique.
- `Student.rollNo` is unique.
- `AttendanceRecord` has unique `(sessionId, studentId)` via `uq_attendance_session_student`.
- Class deletion is not implemented; classes use a `status` field for future archive behavior.

### Seed Data
- Roles: `Admin`, `User`
- Departments: `Computer Science`, `IT`, `Mathematics`, `Physics`
- Default Admin:
  - `fullName`: `Admin User`
  - `email`: `admin@fdas.local`
  - `password`: `Admin@12345`
  - `status`: `Approved`
  - `accessScope`: `AllDepartments`
- Extra verification seed data:
  - Approved CS operator: `operator.cs@fdas.local`
  - Classrooms: `BSCS Semester 5 - A`, `BSIT Semester 3 - A`
  - Students: `CS-2026-001`, `CS-2026-002`, `IT-2026-001`

### Endpoints Created
- `GET /health`
- `GET /api/info`

### Database File Location
- `C:\Users\WELCOME\Desktop\FDAS Project\fdas-app\backend\fdas_local.db`

### Tables Created
- `attendance_records`
- `attendance_sessions`
- `attendance_time_windows`
- `classrooms`
- `departments`
- `face_templates`
- `roles`
- `students`
- `users`

### Commands Run
- `python --version` - still failed because `python` is not on PATH in this shell.
- `py --version` - still failed with `No installed Python found!`.
- Searched common install folders and found Python at `C:\Users\WELCOME\AppData\Local\Programs\Python\Python311\python.exe`.
- `& 'C:\Users\WELCOME\AppData\Local\Programs\Python\Python311\python.exe' --version` - passed with `Python 3.11.9`.
- `& 'C:\Users\WELCOME\AppData\Local\Programs\Python\Python311\python.exe' -m venv .venv` - passed.
- `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` - first run timed out after partial install; second run completed successfully.
- `.\.venv\Scripts\python.exe -m pip list` - verified installed packages.
- `.\.venv\Scripts\python.exe -m app.seed` - created and seeded the local SQLite database.
- `.\.venv\Scripts\python.exe -m app.verify_phase2` - passed schema and seed verification.
- `.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title); print([route.path for route in app.routes])"` - verified FastAPI app imports and exposes Phase 2 routes only.
- `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` - server started successfully.
- `curl.exe --max-time 10 http://127.0.0.1:8000/health` - returned `{"status":"ok","service":"FDAS Backend","database":"connected"}`.
- `curl.exe --max-time 10 http://127.0.0.1:8000/api/info` - returned backend app info and database path.

### Verification Results
- Database exists: `True`
- Tables: `attendance_records`, `attendance_sessions`, `attendance_time_windows`, `classrooms`, `departments`, `face_templates`, `roles`, `students`, `users`
- Missing tables: `none`
- Role count: `2`
- Department count: `4`
- User count: `2`
- Classroom count: `2`
- Student count: `3`
- Default admin exists: `True`
- Default admin password hashed: `True`
- `/health` response: `{"status":"ok","service":"FDAS Backend","database":"connected"}`

### Errors Found And Fixed
- Python 3.11 was installed but not discoverable through `python` or `py`; fixed verification by using the direct Python 3.11 install path.
- PowerShell activation was avoided by using `.\.venv\Scripts\python.exe` directly.
- Initial `pip install` timed out after partial installation; reran with a longer timeout and completed successfully.
- `Role.createdAt` was missing; added it as an optional Phase 2 timestamp field.
- `/health` did not report database status; updated it to run a lightweight database connectivity check and return `database: connected`.
- Removed the extra `POST /api/init-db` endpoint to keep the Phase 2 API surface limited to the requested foundation endpoints.
- Added `app.verify_phase2` to make schema and seed verification repeatable.

### Remaining Issues
- `python` and `py` are still not available on PATH in this shell. Use the direct Python path or add Python 3.11 to PATH later.
- No automated pytest suite exists yet; Phase 2 verification is covered by `app.verify_phase2`, SQLAlchemy inspection, app import, Uvicorn startup, and curl checks.
- LAN-based central local server remains a future enhancement.
- Frontend API integration, JWT authentication, real attendance marking, and real face recognition remain future phases.

## Phase 3 - Backend Authentication and Role-Based Access Control

### Goal
Implement backend authentication, JWT bearer tokens, role-based access control, user approval/status checks, admin user management, and reusable department-access helpers. Phase 3 intentionally does not include frontend API integration, student/class CRUD, attendance sessions, attendance marking, reports, face enrollment, OpenCV, MediaPipe, or LAN deployment.

### Files Created Or Modified
- `backend/requirements.txt`
- `backend/README.md`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/dependencies.py`
- `backend/app/verify_phase3.py`
- `backend/app/routers/auth.py`
- `backend/app/routers/admin_users.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/access_control.py`
- `backend/app/utils/jwt.py`
- `backend/app/utils/security.py`
- `docs/development_journey.md`

### Auth Endpoints Created
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/register-request`

### Admin User Management Endpoints Created
- `GET /api/admin/users`
- `GET /api/admin/user-requests`
- `PATCH /api/admin/users/{userId}/approve`
- `PATCH /api/admin/users/{userId}/reject`
- `PATCH /api/admin/users/{userId}/disable`
- `PATCH /api/admin/users/{userId}/enable`
- `PATCH /api/admin/users/{userId}/access`

### RBAC Rules Implemented
- JWT tokens include `userId`, `email`, `role`, `accessScope`, `assignedDepartmentId`, and expiration time.
- `get_current_user` validates bearer tokens and reloads the user from the database.
- `require_approved_user` blocks Pending, Rejected, and Disabled users from protected endpoints.
- `require_admin` allows only approved Admin users.
- `require_operator_or_admin` allows approved Admin and User/operator accounts.
- Disabled users with previously issued tokens are blocked because protected endpoints check current database status.

### Department Access Rules Implemented
- `can_access_department(user, departmentId)` returns true for Admin users.
- `AllDepartments` access can reach any department.
- `Department` access can reach only the user assigned department.
- Other scopes return false.
- `require_department_access(departmentId)` returns a reusable FastAPI dependency for later department-scoped endpoints.

### Commands Run
- `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
- `.\.venv\Scripts\python.exe -m app.seed`
- `.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title); print([route.path for route in app.routes])"`
- `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- `.\.venv\Scripts\python.exe -m app.verify_phase3`

### Tests Performed
- `/health` still works.
- Admin login works with `admin@fdas.local` / `Admin@12345`.
- Wrong password is rejected.
- Pending user cannot login.
- Approved operator can login.
- `/api/auth/me` works with a valid token.
- `/api/auth/me` fails without a token.
- Admin endpoint fails without a token.
- Normal operator cannot access admin user endpoints.
- Admin can list users.
- Admin can list pending user requests.
- Admin can approve a pending user.
- Admin can change user access to `AllDepartments`.
- Admin can change user access back to `Department`.
- Admin can disable a user.
- Disabled user cannot login.
- Department access helper works for Admin, AllDepartments user, Department-only own department, and Department-only blocked from another department.

### Verification Results
- `health=True`
- `admin_login=True`
- `wrong_password_rejected=True`
- `pending_register=True`
- `pending_user_rejected=True`
- `operator_login=True`
- `me_endpoint=True`
- `me_without_token_rejected=True`
- `admin_endpoint_protected=True`
- `operator_admin_blocked=True`
- `admin_list_users=True`
- `admin_list_pending_requests=True`
- `approve_user=True`
- `all_departments_access_update=True`
- `department_access_update=True`
- `disable_user=True`
- `disabled_user_rejected=True`
- `admin_department_access=True`
- `all_departments_access=True`
- `department_only_access=True`
- `department_only_blocked=True`

### Errors Found And Fixed
- Pydantic `EmailStr` rejected the required local demo email domain `admin@fdas.local`; changed auth schema email fields to plain strings so `.local` demo addresses are accepted.
- Manual curl JSON quoting in PowerShell produced invalid JSON; used PowerShell JSON conversion and the Python verifier for reliable endpoint tests.

### Remaining Issues
- `python` and `py` are still not available on PATH in this shell. Continue using `.\.venv\Scripts\python.exe` or add Python 3.11 to PATH later.
- `SECRET_KEY` is stored in `app/config.py` for the local FYP demo. Production should use environment variables.
- No frontend API integration yet.
- No student/class CRUD, attendance session, attendance marking, report, face enrollment, OpenCV, MediaPipe, or LAN deployment work has been started.

## Phase 4 - Backend Academic Management APIs

### Goal
Implement backend academic management APIs for Departments, Classes, Students, and Attendance Time Windows. Phase 4 intentionally does not include frontend API integration, real login UI integration, face enrollment upload, OpenCV/MediaPipe, attendance session start/stop backend, attendance marking, reports, LAN deployment, or Phase 5 work.

### Files Created Or Modified
- `backend/README.md`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/schemas/academic.py`
- `backend/app/services/departments.py`
- `backend/app/services/classes.py`
- `backend/app/services/students.py`
- `backend/app/services/attendance_time_windows.py`
- `backend/app/routers/departments.py`
- `backend/app/routers/classes.py`
- `backend/app/routers/students.py`
- `backend/app/routers/attendance_time_windows.py`
- `backend/app/verify_phase4.py`
- `docs/development_journey.md`

### Endpoints Created
Departments:
- `GET /api/departments`
- `GET /api/departments/{departmentId}`
- `POST /api/departments`
- `PATCH /api/departments/{departmentId}`
- `PATCH /api/departments/{departmentId}/disable`
- `PATCH /api/departments/{departmentId}/enable`

Classes:
- `GET /api/classes`
- `GET /api/classes/{classId}`
- `POST /api/classes`
- `PATCH /api/classes/{classId}`
- `PATCH /api/classes/{classId}/archive`
- `PATCH /api/classes/{classId}/activate`

Students:
- `GET /api/students`
- `GET /api/students/{studentId}`
- `POST /api/students`
- `PATCH /api/students/{studentId}`
- `PATCH /api/students/{studentId}/disable`
- `PATCH /api/students/{studentId}/enable`

Attendance Time Windows:
- `GET /api/attendance-time-windows`
- `GET /api/attendance-time-windows/{windowId}`
- `POST /api/attendance-time-windows`
- `PATCH /api/attendance-time-windows/{windowId}`
- `PATCH /api/attendance-time-windows/{windowId}/activate`
- `PATCH /api/attendance-time-windows/{windowId}/deactivate`

### Schemas Created
- `DepartmentCreate`
- `DepartmentUpdate`
- `DepartmentRead`
- `ClassRoomCreate`
- `ClassRoomUpdate`
- `ClassRoomRead`
- `StudentCreate`
- `StudentUpdate`
- `StudentRead`
- `AttendanceTimeWindowCreate`
- `AttendanceTimeWindowUpdate`
- `AttendanceTimeWindowRead`

### Access Rules Implemented
- Admin users can access all department data and all Phase 4 endpoints.
- Approved User/operator accounts with `AllDepartments` can read all department-scoped academic data and can create/update students in any valid department/class.
- Department-only User/operator accounts can read only their assigned department data.
- Department-only User/operator accounts can create/update students only inside their assigned department.
- Department-only User/operator accounts are blocked from creating students in another department.
- Department-only User/operator accounts are blocked from admin-only department, class, and attendance time window create/update/archive endpoints.
- Department, class, student, and time-window detail reads enforce department access.

### Commands Run
- `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`
- `.\.venv\Scripts\python.exe -m app.seed`
- `.\.venv\Scripts\python.exe -c "from app.main import app; print(app.title); print([route.path for route in app.routes])"`
- `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- `.\.venv\Scripts\python.exe -m app.verify_phase4`

### Verification Results
- `health=True`
- `admin_login=True`
- `operator_login=True`
- `admin_list_departments=True`
- `operator_department_scope=True`
- `create_department=True`
- `operator_department_create_blocked=True`
- `create_class=True`
- `archive_class=True`
- `archive_class_not_deleted=True`
- `operator_class_archive_blocked=True`
- `create_student=True`
- `operator_create_own_department_student=True`
- `operator_cross_department_blocked=True`
- `roll_no_unique=True`
- `update_student=True`
- `disable_student=True`
- `enable_student=True`
- `create_time_window=True`
- `operator_own_time_windows_only=True`
- `operator_time_window_create_blocked=True`
- `class_filters=True`
- `student_filters=True`
- `phase4_passed=True`

### Errors Found And Fixed
- The first Phase 4 verifier run failed only on `student_filters` because the test query searched `Phase 4` while the seeded test student names used `Phase Four`. Updated the verifier to search the correct student text and reran successfully.

### Remaining Issues
- `python` and `py` are still not available on PATH in this shell. Continue using `.\.venv\Scripts\python.exe`.
- No frontend API integration yet.
- No real login UI integration yet.
- No face enrollment upload, OpenCV/MediaPipe, attendance session backend, attendance marking, reports, or LAN deployment yet.
- Face registered status is returned from existing `FaceTemplate` relationships and remains false/placeholder unless templates are added later.

## Phase 5 - Frontend Integration with Backend Auth and Academic APIs

### Goal
Connect the React frontend to the existing FastAPI backend for authentication, role-based navigation, admin user approval/access management, departments, classes, students, and attendance time windows. Phase 5 intentionally does not implement face recognition, OpenCV/MediaPipe, real attendance marking, reports backend, LAN deployment, or Phase 6 work.

### Frontend Files Created Or Modified
- `frontend/src/api/client.js`
- `frontend/src/api/authApi.js`
- `frontend/src/api/adminUsersApi.js`
- `frontend/src/api/departmentsApi.js`
- `frontend/src/api/classesApi.js`
- `frontend/src/api/studentsApi.js`
- `frontend/src/api/attendanceTimeWindowsApi.js`
- `frontend/src/context/authCore.js`
- `frontend/src/context/AuthContext.jsx`
- `frontend/src/context/useAuth.js`
- `frontend/src/components/ProtectedRoute.jsx`
- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/layouts/AdminLayout.jsx`
- `frontend/src/layouts/UserLayout.jsx`
- `frontend/src/pages/LoginPage.jsx`
- `frontend/src/pages/admin/AdminDashboard.jsx`
- `frontend/src/pages/admin/AdminRequests.jsx`
- `frontend/src/pages/admin/AdminUsers.jsx`
- `frontend/src/pages/admin/AdminClasses.jsx`
- `frontend/src/pages/admin/AdminStudents.jsx`
- `frontend/src/pages/admin/AdminAddStudent.jsx`
- `frontend/src/pages/admin/AdminTiming.jsx`
- `frontend/src/pages/user/UserDashboard.jsx`
- `frontend/src/pages/user/UserStudents.jsx`
- `frontend/src/pages/user/UserAddStudent.jsx`
- `frontend/README.md`
- `docs/development_journey.md`

### Backend Files Modified
- `backend/app/main.py` - added local CORS for `http://127.0.0.1:5173` and `http://localhost:5173`.

### API Layer Created
- Axios client uses base URL `http://127.0.0.1:8000`.
- Bearer token is attached from localStorage.
- API error details are normalized for page-level messages.
- Separate modules were created for auth, admin users, departments, classes, students, and attendance time windows.

### Auth Integration
- Login now calls `POST /api/auth/login`.
- Auth state stores access token, current user, role, status, access scope, assigned department id, and assigned department name.
- Auth state persists with localStorage for the Phase 5 demo.
- Protected routes redirect unauthenticated users to `/login`.
- Admin routes require Admin role.
- User/operator routes require User role; admins are redirected back to the admin dashboard.
- Logout clears the token and current user.

### Pages Integrated
- `/login`
- `/admin/dashboard`
- `/admin/requests`
- `/admin/users`
- `/admin/classes`
- `/admin/students`
- `/admin/students/add`
- `/admin/timing`
- `/user/dashboard`
- `/user/students`
- `/user/students/add`

Live attendance, analytics, and reports remain dummy/static where backend APIs do not exist yet.

### Backend Endpoints Used
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/admin/user-requests`
- `GET /api/admin/users`
- `PATCH /api/admin/users/{userId}/approve`
- `PATCH /api/admin/users/{userId}/reject`
- `PATCH /api/admin/users/{userId}/disable`
- `PATCH /api/admin/users/{userId}/enable`
- `PATCH /api/admin/users/{userId}/access`
- `GET /api/departments`
- `GET /api/classes`
- `POST /api/classes`
- `PATCH /api/classes/{classId}`
- `PATCH /api/classes/{classId}/archive`
- `PATCH /api/classes/{classId}/activate`
- `GET /api/students`
- `POST /api/students`
- `PATCH /api/students/{studentId}`
- `PATCH /api/students/{studentId}/disable`
- `PATCH /api/students/{studentId}/enable`
- `GET /api/attendance-time-windows`
- `POST /api/attendance-time-windows`
- `PATCH /api/attendance-time-windows/{windowId}`
- `PATCH /api/attendance-time-windows/{windowId}/activate`
- `PATCH /api/attendance-time-windows/{windowId}/deactivate`

### Commands Run
- `.\.venv\Scripts\python.exe -m app.seed`
- `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- `.\.venv\Scripts\python.exe -m app.verify_phase3`
- `.\.venv\Scripts\python.exe -m app.verify_phase4`
- `npm.cmd run dev -- --host 127.0.0.1 --port 5173`
- `npm.cmd run build`
- `npm.cmd run lint`
- `Invoke-WebRequest http://127.0.0.1:5173/login`
- PowerShell API checks for admin login, operator login, wrong login rejection, admin protected data, and operator admin-endpoint blocking.

### Testing Performed
- Backend `/health` returned `database=connected`.
- Admin login returned a bearer token and Admin profile.
- Operator login returned a bearer token and User profile scoped to Computer Science.
- Wrong admin password returned `401`.
- Operator call to `/api/admin/users` returned `403`.
- Admin token loaded users, classes, students, and attendance time windows.
- Operator token loaded only one department: Computer Science.
- `app.verify_phase3` passed.
- `app.verify_phase4` passed.
- Frontend `/login` route returned HTTP 200 from Vite.
- `npm.cmd run build` passed with the existing non-blocking chunk-size warning.
- `npm.cmd run lint` passed with no warnings.

### Errors Found And Fixed
- Browser-to-backend requests required CORS because Vite runs on port 5173 and FastAPI on port 8000; added FastAPI CORS middleware for local dev origins.
- Oxlint found missing hook dependency warnings in admin student/class pages; fixed with `useCallback`.
- The browser-control runtime had no available browser instances, so browser console inspection could not be completed in this session.

### Remaining Issues
- No browser console inspection was possible because the browser runtime reported no available browsers.
- Vite build still reports the existing non-blocking large chunk warning.
- Face enrollment remains frontend-only/dummy; no face upload/templates are sent.
- Live attendance marking, attendance session backend, reports backend, OpenCV/MediaPipe, LAN deployment, and Phase 6 are not implemented.

### Offline Font/Icon Fix
- Removed Google Fonts and Material Symbols external links from `frontend/index.html`.
- Replaced the `Plus Jakarta Sans` dependency with a local/system font stack: `system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.
- Removed Material Symbols CSS from `frontend/src/index.css`.
- Added `frontend/src/components/Icon.jsx`, a local Lucide icon wrapper that maps the old icon names to `lucide-react` icons.
- Replaced remaining `material-symbols-outlined` icon-font spans in components, layouts, login, dashboard, student, class, timing, and attendance pages.
- Added Playwright artifact paths to `frontend/.gitignore`: `output/`, `test-results/`, and `playwright-report/`.
- Kept the Phase 5 Playwright smoke script for repeatable browser verification.
- Kept `@tailwindcss/vite` because it is required by `vite.config.js`.

### Offline Fix Verification
- `npm.cmd run build` - passed with the existing non-blocking large chunk warning.
- `npm.cmd run lint` - passed with no warnings.
- `node .\scripts\phase5-smoke.mjs` - passed all smoke checks.
- Confirmed no `fonts.googleapis.com`, `fonts.gstatic.com`, or Material Symbols console/resource errors remain.
- Remaining console error is expected from the wrong-login test: `POST /api/auth/login` returned `401 Unauthorized`.
