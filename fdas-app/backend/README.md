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

Required Phase 2 packages:

- `fastapi==0.115.6`
- `uvicorn[standard]==0.34.0`
- `SQLAlchemy==2.0.36`
- `pydantic==2.10.4`
- `PyJWT==2.10.1`

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

## Current Limitations

- No frontend API integration yet.
- No student CRUD endpoints yet.
- No attendance session endpoints yet.
- No attendance marking logic yet.
- No face recognition or liveness implementation yet.
- LAN-based central local server deployment remains a future enhancement.
