$ErrorActionPreference = 'Stop'

$backendRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$projectRoot = Split-Path -Parent $backendRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
$npmPath = (Get-Command npm.cmd -ErrorAction Stop).Source
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$isolatedRoot = Join-Path $backendRoot "output\password-recovery-camera-$stamp"
$isolatedBackend = Join-Path $isolatedRoot 'backend'
$backendStdout = Join-Path $backendRoot 'output\password-recovery-camera-backend.stdout.log'
$backendStderr = Join-Path $backendRoot 'output\password-recovery-camera-backend.stderr.log'
$frontendStdout = Join-Path $frontendRoot 'output\playwright\password-recovery-camera-vite.stdout.log'
$frontendStderr = Join-Path $frontendRoot 'output\playwright\password-recovery-camera-vite.stderr.log'
$backendPort = 8015
$frontendPort = 5185
$backendProcess = $null
$frontendProcess = $null

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "FDAS virtual-environment interpreter was not found: $pythonPath"
}

New-Item -ItemType Directory -Path $isolatedBackend -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $frontendStdout) -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $backendRoot 'app') -Destination $isolatedBackend -Recurse
Copy-Item -LiteralPath (Join-Path $backendRoot 'fdas_local.db') -Destination $isolatedBackend

$savedEnvironment = @{}
$environmentChanges = @{
    FDAS_FRONTEND_BASE_URL = "http://127.0.0.1:$frontendPort"
    FDAS_EXTRA_CORS_ORIGINS = "http://127.0.0.1:$frontendPort"
    FDAS_SMTP_HOST = ''
    FDAS_SMTP_PORT = ''
    FDAS_SMTP_USERNAME = ''
    FDAS_SMTP_PASSWORD = ''
    FDAS_SMTP_FROM_EMAIL = ''
    FDAS_DEEP_FACE_MODEL_DIR = (Join-Path $backendRoot 'models\insightface\buffalo_l')
    VITE_API_BASE_URL = "http://127.0.0.1:$backendPort"
    FDAS_PASSWORD_RECOVERY_BROWSER_ISOLATED = '1'
    FDAS_API_BASE_URL = "http://127.0.0.1:$backendPort"
}

foreach ($name in $environmentChanges.Keys) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, $environmentChanges[$name], 'Process')
}

try {
    Push-Location $isolatedBackend
    try {
        $provisionCode = @'
from app.database import SessionLocal, init_db
from app.models.face_template_embedding import FaceTemplateEmbedding
from app.models.user import User
from app.services.password_recovery import issue_email_token
import sys

init_db()
db = SessionLocal()
try:
    user = db.query(User).filter(User.email == sys.argv[1]).one()
    token, _ = issue_email_token(db, user)
    deep_rows = db.query(FaceTemplateEmbedding).filter(
        FaceTemplateEmbedding.studentId == 22,
        FaceTemplateEmbedding.isActive.is_(True),
    ).order_by(FaceTemplateEmbedding.faceTemplateEmbeddingId).all()
    for row in deep_rows[19:]:
        row.isActive = False
    db.commit()
    print(token)
finally:
    db.close()
'@
        $resetTokenOutput = & $pythonPath -c $provisionCode 'phase6a.all@fdas.local'
        if ($LASTEXITCODE -ne 0 -or -not $resetTokenOutput) { throw 'Unable to provision the isolated email-reset token.' }
        $resetToken = $resetTokenOutput.Trim()
    }
    finally {
        Pop-Location
    }

    $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$backendPort") -WorkingDirectory $isolatedBackend -WindowStyle Hidden -RedirectStandardOutput $backendStdout -RedirectStandardError $backendStderr -PassThru
    $frontendProcess = Start-Process -FilePath $npmPath -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1', '--port', "$frontendPort") -WorkingDirectory $frontendRoot -WindowStyle Hidden -RedirectStandardOutput $frontendStdout -RedirectStandardError $frontendStderr -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt += 1) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health" -TimeoutSec 2
            $frontendResponse = Invoke-WebRequest -Uri "http://127.0.0.1:$frontendPort/login" -UseBasicParsing -TimeoutSec 2
            if ($health.status -eq 'ok' -and $frontendResponse.StatusCode -eq 200) {
                $ready = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) { throw 'Isolated backend/frontend did not become ready.' }

    $env:FDAS_BROWSER_EMAIL_RESET_TOKEN = $resetToken
    $env:FDAS_BROWSER_EMAIL_RESET_EMAIL = 'phase6a.all@fdas.local'
    $fixture = Get-ChildItem -LiteralPath (Join-Path $backendRoot 'storage\face_enrollments\22') -File | Select-Object -First 1 -ExpandProperty FullName
    if (-not $fixture) { throw 'Student #22 camera fixture was not found.' }
    $env:FDAS_CAMERA_FIXTURE = $fixture

    Push-Location $frontendRoot
    try {
        & $npmPath run smoke:password-recovery-camera
        if ($LASTEXITCODE -ne 0) { throw "Browser verification failed with exit code $LASTEXITCODE." }
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($frontendProcess -and -not $frontendProcess.HasExited) { Stop-Process -Id $frontendProcess.Id -Force }
    if ($backendProcess -and -not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id -Force }
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and (
            $_.CommandLine.Contains("--port $frontendPort") -or
            $_.CommandLine.Contains("--port $backendPort")
        )
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    foreach ($name in $environmentChanges.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    Remove-Item Env:FDAS_BROWSER_EMAIL_RESET_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:FDAS_BROWSER_EMAIL_RESET_EMAIL -ErrorAction SilentlyContinue
    Remove-Item Env:FDAS_CAMERA_FIXTURE -ErrorAction SilentlyContinue

    $resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $backendRoot 'output'))
    $resolvedIsolated = [System.IO.Path]::GetFullPath($isolatedRoot)
    if ($resolvedIsolated.StartsWith($resolvedOutput, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedIsolated)) {
        Remove-Item -LiteralPath $resolvedIsolated -Recurse -Force
    }
}
