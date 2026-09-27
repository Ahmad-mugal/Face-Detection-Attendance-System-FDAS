from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


SOURCE_BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SOURCE_BACKEND_DIR.parent
WORKSPACE_DIR = PROJECT_DIR.parent
HOST = "127.0.0.1"
PORT = int(os.getenv("FDAS_FINAL_VERIFICATION_PORT", "8000"))
BASE_URL = f"http://{HOST}:{PORT}"
STARTUP_TIMEOUT_SECONDS = 90
SKIP_PRIOR_ENV = "FDAS_SKIP_PRIOR_VERIFIERS"


@dataclass(frozen=True)
class VerifierSpec:
    label: str
    module: str
    timeout_seconds: int = 900


@dataclass(frozen=True)
class VerifierResult:
    spec: VerifierSpec
    passed: bool
    returncode: int
    detail: str = ""


VERIFIERS: tuple[VerifierSpec, ...] = (
    VerifierSpec("Phase 2 Foundation", "app.verify_phase2"),
    VerifierSpec("Phase 3 Auth/RBAC", "app.verify_phase3"),
    VerifierSpec("Phase 4 Academic APIs", "app.verify_phase4"),
    VerifierSpec("Phase 6A Attendance Sessions", "app.verify_phase6a"),
    VerifierSpec("Phase 6B Face Enrollment/Storage", "app.verify_phase6b"),
    VerifierSpec("Phase 7A Face Processing", "app.verify_phase7a"),
    VerifierSpec("Phase 7B Face Matching", "app.verify_phase7b"),
    VerifierSpec("Phase 7C Attendance Marking", "app.verify_phase7c"),
    VerifierSpec("Phase 8B Reports/CSV", "app.verify_phase8b"),
    VerifierSpec("Phase 8C Liveness", "app.verify_phase8c"),
    VerifierSpec("Phase 10 Dashboard", "app.verify_phase10"),
    VerifierSpec("Phase 10.4 Registration Validation", "app.verify_phase10_4"),
    VerifierSpec("Phase 10.6C Single-Face Guard", "app.verify_phase10_6c"),
    VerifierSpec("Phase 10.6B Identity Integrity", "app.verify_phase10_6b"),
    VerifierSpec("Phase 10.7A Deep Recognition Foundation", "app.verify_phase10_7a", timeout_seconds=1200),
    VerifierSpec("Phase 10.7B Deep Embedding Migration", "app.verify_phase10_7b"),
    VerifierSpec("Phase 10.7B.1 Enrollment Recovery", "app.verify_phase10_7b1"),
    VerifierSpec("Phase 10.7C Deep Recognition Calibration", "app.verify_phase10_7c"),
    VerifierSpec("Phase 10.7D Identity Record Integrity", "app.verify_phase10_7d"),
    VerifierSpec("Phase 10.8 Deep Attendance Integration", "app.verify_phase10_8"),
    VerifierSpec("Phase 10.9 Genuine-User Reliability", "app.verify_phase10_9"),
    VerifierSpec("Phase 10.9B Controlled Policy Validation", "app.verify_phase10_9b"),
    VerifierSpec("Phase 10.10 Final Deep Attendance", "app.verify_phase10_10"),
    VerifierSpec("Phase 10.12A Approval Email", "app.verify_phase10_12a"),
    VerifierSpec("Phase 10.12B SMTP/UI Infrastructure", "app.verify_phase10_12b"),
    VerifierSpec("Phase 10.12D Notifications/Delete/Import", "app.verify_phase10_12d"),
    VerifierSpec("Camera Preview & Password Recovery", "app.verify_password_recovery"),
)


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
VERIFIER_RUNNER_CODE = (
    "import importlib,sys; "
    "module=importlib.import_module(sys.argv[1]); "
    "module.BASE_URL=sys.argv[2]; "
    "runner=(getattr(module,'main',None) or getattr(module,'verify_phase2',None) "
    "or getattr(module,'run_verification',None)); "
    "runner()"
)


def ensure_verifier_port_is_free() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        if probe.connect_ex((HOST, PORT)) == 0:
            raise RuntimeError(
                f"Port {PORT} is already in use. Stop the existing backend before final verification."
            )


def prepare_isolated_backend(temp_root: Path) -> Path:
    isolated_backend = temp_root / "fdas-app" / "backend"
    isolated_backend.mkdir(parents=True)
    shutil.copytree(
        SOURCE_BACKEND_DIR / "app",
        isolated_backend / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    database_source = SOURCE_BACKEND_DIR / "fdas_local.db"
    if not database_source.is_file():
        raise FileNotFoundError(f"Active database was not found at {database_source}")
    isolated_database = isolated_backend / "fdas_local.db"
    shutil.copy2(database_source, isolated_database)

    # Legacy Phase 3 uses this seeded operator as its positive RBAC fixture.
    # Normalize only the disposable copy because the real account may be
    # intentionally disabled in production.
    with sqlite3.connect(isolated_database) as connection:
        connection.execute(
            "UPDATE users SET status = 'Approved' WHERE email = 'operator.cs@fdas.local'"
        )
        connection.commit()

    gitignore_source = SOURCE_BACKEND_DIR / ".gitignore"
    if gitignore_source.is_file():
        shutil.copy2(gitignore_source, isolated_backend / ".gitignore")
    (isolated_backend / "storage").mkdir()
    source_enrollment_root = SOURCE_BACKEND_DIR / "storage" / "face_enrollments"
    isolated_enrollment_root = isolated_backend / "storage" / "face_enrollments"
    for student_id in ("19", "22", "26", "27", "28", "29"):
        source_student_directory = source_enrollment_root / student_id
        if source_student_directory.is_dir():
            shutil.copytree(
                source_student_directory,
                isolated_enrollment_root / student_id,
            )
    return isolated_backend


def wait_for_isolated_server(process: subprocess.Popen[str], expected_database: Path) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error = "no response"

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Isolated Uvicorn exited during startup with code {process.returncode}.")
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=3) as response:
                health = json.loads(response.read().decode("utf-8"))
            with urllib.request.urlopen(f"{BASE_URL}/api/info", timeout=3) as response:
                info = json.loads(response.read().decode("utf-8"))
            database_path = Path(info.get("database", "")).resolve()
            if response.status == 200 and health.get("database") == "connected" and database_path == expected_database.resolve():
                return
            last_error = f"unexpected health/info response: health={health}, database={database_path}"
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(1)

    raise TimeoutError(f"Isolated Uvicorn did not become ready: {last_error}")


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def execute_verifiers(
    specs: Sequence[VerifierSpec],
    isolated_backend: Path,
    environment: dict[str, str],
    command_runner: CommandRunner = subprocess.run,
    *,
    show_output: bool = True,
) -> list[VerifierResult]:
    results: list[VerifierResult] = []

    for spec in specs:
        print(f"\n--- {spec.label}: {spec.module} ---", flush=True)
        try:
            completed = command_runner(
                [sys.executable, "-c", VERIFIER_RUNNER_CODE, spec.module, BASE_URL],
                cwd=isolated_backend,
                env=environment,
                capture_output=True,
                text=True,
                timeout=spec.timeout_seconds,
                check=False,
            )
            if show_output and completed.stdout:
                print(completed.stdout.rstrip(), flush=True)
            if show_output and completed.stderr:
                print(completed.stderr.rstrip(), file=sys.stderr, flush=True)
            passed = completed.returncode == 0
            detail = "" if passed else f"process exited with code {completed.returncode}"
            results.append(VerifierResult(spec, passed, completed.returncode, detail))
        except subprocess.TimeoutExpired as exc:
            if show_output and exc.stdout:
                print(exc.stdout.rstrip(), flush=True)
            if show_output and exc.stderr:
                print(exc.stderr.rstrip(), file=sys.stderr, flush=True)
            results.append(
                VerifierResult(
                    spec,
                    False,
                    124,
                    f"timed out after {spec.timeout_seconds} seconds",
                )
            )

        if not results[-1].passed:
            print(f"Stopping after failed verifier: {spec.module}", flush=True)
            break

    return results


def print_summary(specs: Sequence[VerifierSpec], results: Sequence[VerifierResult]) -> int:
    print("\nFDAS FINAL VERIFICATION\n", flush=True)
    result_by_module = {result.spec.module: result for result in results}
    label_width = max(len(spec.label) for spec in specs)

    for spec in specs:
        result = result_by_module.get(spec.module)
        if result is None:
            outcome = "NOT RUN"
        elif result.passed:
            outcome = "PASS"
        else:
            outcome = f"FAIL ({result.detail})"
        print(f"{spec.label:<{label_width}}  {outcome}", flush=True)

    passed = len(results) == len(specs) and all(result.passed for result in results)
    print(f"\nFINAL RESULT: {'PASS' if passed else 'FAIL'}", flush=True)
    return 0 if passed else 1


def print_log_tail(path: Path, heading: str, line_count: int = 40) -> None:
    if not path.is_file():
        return
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return
    print(f"\n{heading}", file=sys.stderr)
    print("\n".join(lines[-line_count:]), file=sys.stderr)


def main() -> int:
    print("FDAS FINAL VERIFICATION", flush=True)
    print("Mode: sequential, isolated database and storage", flush=True)
    ensure_verifier_port_is_free()

    environment = os.environ.copy()
    environment[SKIP_PRIOR_ENV] = "1"
    environment["FDAS_FINAL_VERIFICATION_ISOLATED"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    environment["FDAS_DEEP_FACE_MODEL_DIR"] = str(
        SOURCE_BACKEND_DIR / "models" / "insightface" / "buffalo_l"
    )

    try:
        with tempfile.TemporaryDirectory(
            prefix=".fdas-final-verification-",
            dir=WORKSPACE_DIR,
        ) as temp_directory:
            isolated_backend = prepare_isolated_backend(Path(temp_directory))
            stdout_path = isolated_backend / "uvicorn.stdout.log"
            stderr_path = isolated_backend / "uvicorn.stderr.log"
            server: subprocess.Popen[str] | None = None
            results: list[VerifierResult] = []

            with stdout_path.open("w", encoding="utf-8") as stdout_log, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr_log:
                try:
                    server = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "app.main:app",
                            "--host",
                            HOST,
                            "--port",
                            str(PORT),
                        ],
                        cwd=isolated_backend,
                        env=environment,
                        stdout=stdout_log,
                        stderr=stderr_log,
                        text=True,
                    )
                    wait_for_isolated_server(server, isolated_backend / "fdas_local.db")
                    print(f"Isolated backend: {isolated_backend}", flush=True)
                    results = execute_verifiers(VERIFIERS, isolated_backend, environment)
                finally:
                    if server is not None:
                        stop_process_tree(server)

            exit_code = print_summary(VERIFIERS, results)
            if exit_code != 0:
                print_log_tail(stderr_path, "Isolated Uvicorn stderr (tail)")
                print_log_tail(stdout_path, "Isolated Uvicorn stdout (tail)")
            return exit_code
    except Exception:
        traceback.print_exc()
        print("\nFINAL RESULT: FAIL", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
