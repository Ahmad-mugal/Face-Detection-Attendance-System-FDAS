$ErrorActionPreference = 'Stop'

$backendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "FDAS virtual-environment interpreter was not found: $pythonPath"
}

# This flag exists only in this launcher process and the Uvicorn child process.
# Ordinary backend startup remains fail-closed for controlled attendance.
$env:FDAS_DEEP_ATTENDANCE_CONTROLLED_TEST = 'true'

Write-Host 'Starting the Phase 10.9 Admin/#22 controlled reliability backend.'
Write-Host 'Normal attendance remains disabled and IDENTITY_MATCHING_SAFETY_HOLD remains active.'

Push-Location $backendRoot
try {
    & $pythonPath -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
