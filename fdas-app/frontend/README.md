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

Still intentionally dummy/static:

- Face enrollment capture/upload
- Live attendance marking
- Reports and analytics data
- Attendance session backend behavior

Verification:

```powershell
npm.cmd run build
npm.cmd run lint
```
