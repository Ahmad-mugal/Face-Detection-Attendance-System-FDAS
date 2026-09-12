# FDAS Frontend

React + Vite frontend for the FDAS demo.

- Frontend URL: `http://127.0.0.1:5173`
- Backend API URL: `http://127.0.0.1:8000`
- Interactive API Documentation: `http://127.0.0.1:8000/docs`

> [!IMPORTANT]
> - **Backend Dependency:** The FastAPI backend server MUST be running at `http://127.0.0.1:8000` before opening the frontend.
> - **Webcam Permission:** Browser camera permissions are required for face enrollment (25 auto-captures) and live attendance scanning.

Run the frontend dev server:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Demo login:

```text
Admin: admin@fdas.local / Admin@12345
Operator: operator.cs@fdas.local / Operator@12345
```

Connected in Phase 5:

- Login/logout and protected routes
- Admin user requests and user access management
- Departments, classes, students, and attendance time windows
- Dashboard summary counts where backend APIs exist
- Add Student face enrollment upload through the backend enrollment endpoint
- Live attendance session controls and face attendance marking through the backend attendance APIs
- Admin and operator attendance records/reports through backend report APIs

Live attendance usage:

- Start the backend first at `http://127.0.0.1:8000`.
- Login as Admin or an approved User/operator.
- Admin: open `/admin/attendance/live`, select a department, then start or load the active session.
- Operator: open `/user/attendance`; department-only operators use their assigned department, while AllDepartments users can select a department.
- Start the camera, allow browser camera permission, then click `Start Scanning`.
- The page shows one random basic liveness challenge per scan attempt: move face slightly left, move face slightly right, or move closer to camera.
- The page captures 5 frames over about 2-3 seconds and posts them to `POST /api/attendance/mark-by-face-live`.
- Attendance is marked only when liveness passes, face matching passes, the session is active, and duplicate rules pass.
- Session records are loaded from `GET /api/attendance-sessions/{sessionId}/records`.
- Stop scanning/camera/session when finished. Camera tracks are stopped when the page cleanup runs.
- Liveness is basic challenge-response only. It reduces simple photo/screen spoofing but is not production-grade PAD.

Reports usage:

- Start the backend first.
- Admin: open `/admin/analytics` to view attendance records across departments.
- Operator: open `/user/reports`; department-only users are scoped to their assigned department.
- Use filters for department, class, date range, student, and status.
- Summary cards show total records, present count, unique students, and average confidence.
- CSV export downloads the filtered attendance records.
- Liveness may show `Passed`, `Failed`, or `NotChecked` depending on which attendance endpoint created the record.
- PDF export and advanced analytics are future work.

Face enrollment behavior:

- Save the student profile first.
- Click `Start Face Registration` once.
- The camera shows a 3-second countdown, captures exactly 25 samples automatically at a 400 ms interval, stops itself, and uploads the batch to `POST /api/students/{studentId}/face-enrollment/upload`.
- `Cancel` stops the camera and clears unsaved samples.
- Enrollment capture does not run liveness; liveness is used only during live attendance scanning.

## Final Verification

Start the backend with its normal local `.venv` at `http://127.0.0.1:8000`, then run from `fdas-app/frontend`:

```powershell
npm.cmd run lint
npm.cmd run build
node .\scripts\phase5-smoke.mjs
```

Run these commands sequentially. Because the smoke script submits a test registration request, the backend must use a disposable copy of `fdas_local.db` and an empty disposable `storage/` directory rather than the active demo data. The script otherwise uses the normal local frontend/backend environments and writes screenshots under `output/playwright/`; remove the disposable backend copy afterward. Real-face recognition and real-camera liveness remain separate manual acceptance tests.
