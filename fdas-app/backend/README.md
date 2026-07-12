# FDAS Backend

Backend foundation for the Face Detection Attendance System.

This backend is intentionally local/offline for the current single-laptop demo:

- FastAPI application
- Local SQLite database
- SQLAlchemy ORM models
- Pydantic response schemas
- Seed script for roles, departments, a default admin, and small relationship-check dummy data
- JWT authentication and role-based access control

The current backend remains local/offline for the single-laptop demo. It does not include frontend API integration, OpenCV, MediaPipe, real face recognition, attendance marking logic, or LAN deployment.

## Create Virtual Environment

From `fdas-app/backend`:

```powershell
python -m venv .venv
```

If `python` is not on PATH, use the installed interpreter directly. On this machine the verified path was:

```powershell
& 'C:\Users\WELCOME\AppData\Local\Programs\Python\Python311\python.exe' -m venv .venv
```

PowerShell activation may be blocked by execution policy, so the direct venv executable form is safe:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Install Requirements

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip list
```

Required backend packages:

- `fastapi==0.115.6`
- `uvicorn[standard]==0.34.0`
- `SQLAlchemy==2.0.36`
- `pydantic==2.10.4`
- `PyJWT==2.10.1`
- `python-multipart==0.0.20`
- `numpy==2.2.6`
- `opencv-python==4.12.0.88`

## Initialize And Seed Database

```powershell
.\.venv\Scripts\python.exe -m app.seed
```

The SQLite database is created at:

```text
fdas-app/backend/fdas_local.db
```

Seed data includes:

- Roles: `Admin`, `User`
- Departments: `Computer Science`, `IT`, `Mathematics`, `Physics`
- Default admin: `admin@fdas.local`
- One approved CS operator
- Two classrooms
- Three students

The default admin password is stored as a salted PBKDF2 hash, not as plain text.

Demo admin credentials:

```text
email: admin@fdas.local
password: Admin@12345
```

## Verify Phase 2

```powershell
.\.venv\Scripts\python.exe -m app.verify_phase2
```

This verifies:

- SQLite database file exists
- All required tables exist
- Required seed records exist
- Default admin exists
- Default admin password is not stored as `Admin@12345`

## Run API

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check:

```powershell
curl.exe http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","service":"FDAS Backend","database":"connected"}
```

Optional info endpoint:

```powershell
curl.exe http://127.0.0.1:8000/api/info
```

## Test Login

```powershell
$body = @{ email = 'admin@fdas.local'; password = 'Admin@12345' } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/auth/login -Method POST -ContentType 'application/json' -Body $body
```

The response includes a bearer token and the admin user profile.

## Verify Phase 3

Start Uvicorn first, then run:

```powershell
.\.venv\Scripts\python.exe -m app.verify_phase3
```

The verifier checks admin login, wrong-password rejection, pending/disabled login rejection, `/api/auth/me`, admin endpoint protection, operator blocking, admin user approval/access changes, and department access rules.

## Phase 3 Endpoints

Auth:

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/register-request`

Admin user management:

- `GET /api/admin/users`
- `GET /api/admin/user-requests`
- `PATCH /api/admin/users/{userId}/approve`
- `PATCH /api/admin/users/{userId}/reject`
- `PATCH /api/admin/users/{userId}/disable`
- `PATCH /api/admin/users/{userId}/enable`
- `PATCH /api/admin/users/{userId}/access`

JWT settings are currently stored in `app/config.py` for the local FYP demo. Production should load `SECRET_KEY` and token settings from environment variables.

## Phase 4 Academic Management Endpoints

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

Attendance time windows:

- `GET /api/attendance-time-windows`
- `GET /api/attendance-time-windows/{windowId}`
- `POST /api/attendance-time-windows`
- `PATCH /api/attendance-time-windows/{windowId}`
- `PATCH /api/attendance-time-windows/{windowId}/activate`
- `PATCH /api/attendance-time-windows/{windowId}/deactivate`

Phase 4 keeps soft status changes only. Departments are enabled/disabled, classes are archived/activated, and students are enabled/disabled. No delete endpoints are implemented.

## Verify Phase 4

Start Uvicorn first, then run:

```powershell
.\.venv\Scripts\python.exe -m app.verify_phase4
```

The verifier checks department scoping, admin-only academic mutations, class archive behavior, student creation/update/status changes, roll number uniqueness, attendance time window creation, and cross-department blocking for department-only operators.

## Phase 6A Attendance Session Endpoints

Attendance sessions are department-based. Admin and AllDepartments users can work with any department; department-only operators can work only with their assigned department.

- `POST /api/attendance-sessions/start`
- `POST /api/attendance-sessions/{sessionId}/stop`
- `POST /api/attendance-sessions/{sessionId}/cancel`
- `GET /api/attendance-sessions/active`
- `GET /api/attendance-sessions`
- `GET /api/attendance-sessions/{sessionId}`

Start session request body:

```json
{"departmentId":1}
```

Rules implemented:

- Only one `Active` attendance session is allowed per department.
- Starting a session uses the active department attendance time window when one exists.
- Stopping a session sets `status=Closed` and records `actualEndTime`.
- Cancelling a session sets `status=Cancelled` and records `actualEndTime`.
- No attendance records, face recognition, attendance marking, or report calculations are created in Phase 6A.

## Verify Phase 6A

Start Uvicorn first, then run:

```powershell
.\.venv\Scripts\python.exe -m app.verify_phase6a
```

Recommended backend regression sequence:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m app.verify_phase3
.\.venv\Scripts\python.exe -m app.verify_phase4
.\.venv\Scripts\python.exe -m app.verify_phase6a
```

The Phase 6A verifier checks health, admin/operator login, duplicate active-session blocking, stop/cancel behavior, department-only operator scoping, AllDepartments access, and attendance time window usage.

## Phase 6B Face Enrollment Upload And Storage Endpoints

Face enrollment is stored as local image samples linked to `Student` through `FaceTemplate` records. Phase 6B does not perform real face recognition, OpenCV/MediaPipe processing, liveness detection, embedding generation, attendance marking, or report generation.

Endpoints:

- `POST /api/students/{studentId}/face-enrollment/upload`
- `GET /api/students/{studentId}/face-enrollment`
- `GET /api/face-templates/{templateId}`
- `PATCH /api/face-templates/{templateId}/deactivate`
- `PATCH /api/students/{studentId}/face-enrollment/clear`

Upload behavior:

- Requires an approved Admin/User token.
- Admin and AllDepartments users can enroll face samples for any student.
- Department-only operators can enroll samples only for students in their assigned department.
- Accepts multipart form field `files` with exactly 25 `.jpg`, `.jpeg`, or `.png` files.
- Rejects unsupported extensions, empty files, and images over the local 5 MB upload limit.
- Uses generated safe filenames and stores only relative paths in the database.

Storage structure:

```text
fdas-app/backend/storage/face_enrollments/{studentId}/sample_YYYYMMDD_HHMMSS_micro_001_xxxxxxxx.png
```

`backend/storage/` is ignored by Git and uploaded images should not be committed.

Face template behavior:

- Each uploaded image creates a `FaceTemplate` row with `templatePath`, `sampleIndex`, `status=Stored`, `isActive=True`, and `createdByUserId`.
- `Student.faceRegistered` is returned as true only when the student has at least 25 active face templates from the fixed enrollment batch.
- Deactivate and clear operations soft-deactivate templates by setting `isActive=False` and `status=Inactive`; image files are not physically deleted in Phase 6B.

## Verify Phase 6B

Start Uvicorn first, then run:

```powershell
.\.venv\Scripts\python.exe -m app.verify_phase6b
```

Recommended backend regression sequence:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m app.verify_phase3
.\.venv\Scripts\python.exe -m app.verify_phase4
.\.venv\Scripts\python.exe -m app.verify_phase6a
.\.venv\Scripts\python.exe -m app.verify_phase6b
```

## Phase 7A Face Processing And Embedding Foundation

Phase 7A adds backend-only processing for stored face enrollment samples. It decodes uploaded images with OpenCV, detects a face region with OpenCV's built-in Haar cascade, crops the largest detected face, normalizes it to a small equalized grayscale descriptor, and stores the descriptor JSON in `FaceTemplate.encodingData`.

Current encoding provider:

```text
provider: OpenCV
encodingVersion: opencv_basic_v1
descriptor: 16x16 equalized grayscale crop flattened and L2-normalized
```

This is a lightweight foundation descriptor, not final production face recognition. Actual live recognition matching, liveness detection, attendance marking, reports, and LAN deployment are still not implemented.

Face template processing fields:

- `encodingData`
- `encodingVersion`
- `faceBoxJson`
- `processedAt`
- `status`

Statuses used by Phase 7A:

- `Encoded` when a face is detected and descriptor data is stored.
- `NoFaceDetected` when the image is valid but no face is found.
- `ProcessingFailed` when a stored image cannot be processed later.

Endpoints:

- `POST /api/face-templates/{templateId}/process`
- `POST /api/students/{studentId}/face-enrollment/process-all`
- `GET /api/face-processing/info`

Existing Phase 6B endpoints continue to work:

- `POST /api/students/{studentId}/face-enrollment/upload`
- `GET /api/students/{studentId}/face-enrollment`
- `GET /api/face-templates/{templateId}`
- `PATCH /api/face-templates/{templateId}/deactivate`
- `PATCH /api/students/{studentId}/face-enrollment/clear`

Upload behavior after Phase 7A:

- Exactly 25 image files are required for a new enrollment upload.
- Unsupported extensions and empty files are still rejected.
- Invalid image bytes are rejected.
- Valid images are stored even when no face is detected.
- Successful face detection sets `status=Encoded`, `encodingVersion=opencv_basic_v1`, `faceBoxJson`, `processedAt`, and `encodingData`.
- No-face samples are kept active with `status=NoFaceDetected` and no `encodingData`.

Access rules remain department-scoped:

- Admin and AllDepartments users can process any student's templates.
- Department-only operators can process only templates for students in their assigned department.

## Verify Phase 7A

Start Uvicorn first, then run:

```powershell
.\.venv\Scripts\python.exe -m app.verify_phase7a
```

Recommended backend regression sequence:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m app.verify_phase3
.\.venv\Scripts\python.exe -m app.verify_phase4
.\.venv\Scripts\python.exe -m app.verify_phase6a
.\.venv\Scripts\python.exe -m app.verify_phase6b
.\.venv\Scripts\python.exe -m app.verify_phase7a
```

## Phase 7B Face Matching API Foundation

Phase 7B adds backend-only face matching APIs. The matcher accepts one uploaded image, processes it through the existing `opencv_basic_v1` descriptor pipeline, compares it with eligible enrolled templates, and returns the best matching student candidate. It does not mark attendance, create `AttendanceRecord` rows, start/stop attendance sessions, run liveness checks, update reports, or change frontend attendance behavior.

Matching provider:

```text
provider: OpenCV
encodingVersion: opencv_basic_v1
threshold: 0.75
similarity: cosine similarity / normalized dot product
```

Endpoints:

- `POST /api/face-matching/match`
- `POST /api/students/{studentId}/face-matching/test`
- `GET /api/face-matching/info`

Matching request:

- Multipart form field `file`: one `.jpg`, `.jpeg`, or `.png` image.
- Multipart form field `departmentId`: required for `/api/face-matching/match`.

Candidate filtering:

- Department-scoped only.
- Active students only.
- Active face templates only.
- `FaceTemplate.status=Encoded`.
- `FaceTemplate.encodingData` must be present and parseable.
- Student must be registered with at least 25 active templates.

Access rules:

- Admin users can match within any provided department.
- AllDepartments users can match within any provided department.
- Department-only operators can match only within their assigned department.
- Cross-department access is blocked with `403`.

Failure/status handling:

- Unsupported file types and empty files are rejected.
- No-face images return `matched=false` with `status=NoFaceDetected`.
- Empty departments/no eligible students return `NoEligibleStudents`.
- Registered students without encoded templates return `NoEncodedTemplates`.
- Scores below threshold return `MatchBelowThreshold`.
- Bad stored template encodings are skipped instead of crashing.

## Verify Phase 7B

Start Uvicorn first, then run:

```powershell
.\.venv\Scripts\python.exe -m app.verify_phase7b
```

Recommended backend regression sequence:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m app.verify_phase3
.\.venv\Scripts\python.exe -m app.verify_phase4
.\.venv\Scripts\python.exe -m app.verify_phase6a
.\.venv\Scripts\python.exe -m app.verify_phase6b
.\.venv\Scripts\python.exe -m app.verify_phase7a
.\.venv\Scripts\python.exe -m app.verify_phase7b
```

## Phase 7C Attendance Marking API Foundation

Phase 7C adds backend attendance marking from a valid face match inside an active attendance session. It creates `AttendanceRecord` rows only after the Phase 7B matcher returns a valid above-threshold match for an eligible student in the session department. This phase does not add frontend live attendance integration, liveness detection, reports backend, LAN deployment, or Phase 7D behavior.

Endpoints:

- `POST /api/attendance/mark-by-face`
- `GET /api/attendance-sessions/{sessionId}/records`

`POST /api/attendance/mark-by-face` request:

- Multipart form field `sessionId`: active attendance session id.
- Multipart form field `file`: one `.jpg`, `.jpeg`, or `.png` image.

Attendance marking rules:

- The session must exist and have `status=Active`.
- The current approved user must have access to the session department.
- Matching is scoped to the session department only.
- The matched student must be active and belong to the session department.
- The matched student must be registered with at least 25 active face templates.
- The face match must be above the configured threshold.
- No attendance record is created for `NoFaceDetected`, `MatchBelowThreshold`, `NoEligibleStudents`, `NoEncodedTemplates`, invalid sessions, closed sessions, or department access denial.

Attendance record fields saved by Phase 7C:

- `sessionId`
- `studentId`
- `departmentId`
- `classId`
- `markedAt`
- `status=Present`
- `recognitionConfidence`
- `livenessStatus=NotChecked`

Duplicate prevention:

- Attendance is unique by `sessionId` and `studentId`.
- Duplicate attempts return the existing record with `status=DuplicateAttendance` and do not create another row.

`GET /api/attendance-sessions/{sessionId}/records` returns the session attendance records with student name, roll number, class, department, marked time, confidence, attendance status, and liveness placeholder.

Liveness is not implemented yet. Frontend live attendance integration is also not implemented yet.

## Verify Phase 7C

Start Uvicorn first, then run:

```powershell
.\.venv\Scripts\python.exe -m app.verify_phase7c
```

Recommended backend regression sequence:

```powershell
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m app.verify_phase3
.\.venv\Scripts\python.exe -m app.verify_phase4
.\.venv\Scripts\python.exe -m app.verify_phase6a
.\.venv\Scripts\python.exe -m app.verify_phase6b
.\.venv\Scripts\python.exe -m app.verify_phase7a
.\.venv\Scripts\python.exe -m app.verify_phase7b
.\.venv\Scripts\python.exe -m app.verify_phase7c
```

## Current Limitations

- Face enrollment upload/storage uses a fixed 25-sample automatic registration batch.
- OpenCV basic descriptor generation and foundation-level matching APIs exist, but final production face recognition accuracy is not claimed.
- Manual real-face enrollment and matching were verified separately, but generated verifier images still do not contain a real human face.
- Backend attendance marking foundation exists, but frontend live attendance integration is not implemented yet.
- No MediaPipe, liveness detection, or report endpoints yet.
- LAN-based central local server deployment remains a future enhancement.
