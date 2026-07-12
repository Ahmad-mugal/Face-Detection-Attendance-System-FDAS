# FDAS Frontend

React + Vite frontend for the FDAS demo.

Phase 5 connects the frontend to the local FastAPI backend at:

```text
http://127.0.0.1:8000
```

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

Still intentionally dummy/static:

- Live attendance marking
- Reports and analytics data

Face enrollment behavior:

- Save the student profile first.
- Click `Start Face Registration` once.
- The camera shows a 3-second countdown, captures exactly 25 samples automatically at a 400 ms interval, stops itself, and uploads the batch to `POST /api/students/{studentId}/face-enrollment/upload`.
- `Cancel` stops the camera and clears unsaved samples.
- No live recognition, liveness detection, or attendance marking is implemented in this frontend flow.

Verification:

```powershell
npm.cmd run build
npm.cmd run lint
node .\scripts\phase5-smoke.mjs
```
