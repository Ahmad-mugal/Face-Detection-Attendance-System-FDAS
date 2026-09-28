param([string[]]$Only)

$ErrorActionPreference = 'Stop'

$backendRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$projectRoot = Split-Path -Parent $backendRoot
$frontendRoot = Join-Path $projectRoot 'frontend'
$pythonPath = Join-Path $backendRoot '.venv\Scripts\python.exe'
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
$viteScript = Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'
$viteScriptRelative = 'node_modules\vite\bin\vite.js'
$backendPort = 8016
$frontendPort = 5186
$frontendProcess = $null
$backendProcess = $null
$isolatedRoots = [System.Collections.Generic.List[string]]::new()

$suites = @(
    @{ Key = 'phase5'; Name = 'Phase 5 browser smoke'; Script = 'scripts\phase5-smoke.mjs'; Flag = 'FDAS_SMOKE_ISOLATED' },
    @{ Key = 'phase10.12b'; Name = 'Phase 10.12B browser smoke'; Script = 'scripts\phase10_12b-smoke.mjs'; Flag = 'FDAS_PHASE10_12B_ISOLATED' },
    @{ Key = 'phase10.12c'; Name = 'Phase 10.12C visual regression'; Script = 'scripts\phase10_12c-visual.mjs'; Flag = 'FDAS_PHASE10_12C_CAPTURE' },
    @{ Key = 'phase10.12d'; Name = 'Phase 10.12D browser smoke'; Script = 'scripts\phase10_12d-smoke.mjs'; Flag = 'FDAS_PHASE10_12D_ISOLATED' },
    @{ Key = 'ui-cleanup'; Name = 'UI cleanup and print browser smoke'; Script = 'scripts\ui-cleanup-print-smoke.mjs'; Flag = 'FDAS_UI_CLEANUP_ISOLATED' }
)

if ($Only.Count -gt 0) {
    $unknownSuites = @($Only | Where-Object { $_ -notin $suites.Key })
    if ($unknownSuites.Count -gt 0) { throw "Unknown browser suite key(s): $($unknownSuites -join ', ')" }
    $suites = @($suites | Where-Object { $_.Key -in $Only })
}

if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw "Missing FDAS interpreter: $pythonPath" }
if (-not (Test-Path -LiteralPath $viteScript -PathType Leaf)) { throw "Missing Vite entrypoint: $viteScript" }

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
    FDAS_API_BASE_URL = "http://127.0.0.1:$backendPort"
}

foreach ($name in $environmentChanges.Keys) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, $environmentChanges[$name], 'Process')
}

function Stop-TestProcesses {
    if ($script:backendProcess -and -not $script:backendProcess.HasExited) {
        Stop-Process -Id $script:backendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and ($_.CommandLine.Contains("--port $backendPort") -or $_.CommandLine.Contains("--port $frontendPort"))
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $script:backendProcess = $null
}

try {
    $viteStdout = Join-Path $frontendRoot 'output\playwright\frontend-regressions-vite.stdout.log'
    $viteStderr = Join-Path $frontendRoot 'output\playwright\frontend-regressions-vite.stderr.log'
    New-Item -ItemType Directory -Path (Split-Path -Parent $viteStdout) -Force | Out-Null
    $frontendProcess = Start-Process -FilePath $nodePath -ArgumentList @($viteScriptRelative, '--host', '127.0.0.1', '--port', "$frontendPort") -WorkingDirectory $frontendRoot -WindowStyle Hidden -RedirectStandardOutput $viteStdout -RedirectStandardError $viteStderr -PassThru

    $frontendReady = $false
    for ($attempt = 0; $attempt -lt 60; $attempt += 1) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$frontendPort/login" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $frontendReady = $true; break }
        }
        catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $frontendReady) { throw 'Vite did not become ready for isolated browser regressions.' }

    foreach ($suite in $suites) {
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
        $isolatedRoot = Join-Path $backendRoot "output\frontend-regression-$stamp"
        $isolatedRoots.Add($isolatedRoot)
        $isolatedBackend = Join-Path $isolatedRoot 'backend'
        New-Item -ItemType Directory -Path $isolatedBackend -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $backendRoot 'app') -Destination $isolatedBackend -Recurse
        Copy-Item -LiteralPath (Join-Path $backendRoot 'fdas_local.db') -Destination $isolatedBackend
        Copy-Item -LiteralPath (Join-Path $backendRoot 'storage') -Destination $isolatedBackend -Recurse

        $isolatedDatabase = Join-Path $isolatedBackend 'fdas_local.db'
        $normalizeCode = 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); c.execute(sys.argv[2]); c.commit(); c.close()'
        $normalizeSql = "UPDATE users SET status = 'Approved' WHERE email = 'operator.cs@fdas.local'"
        & $pythonPath -c $normalizeCode $isolatedDatabase $normalizeSql
        if ($LASTEXITCODE -ne 0) { throw "Unable to normalize isolated fixtures for $($suite.Name)." }

        $backendStdout = Join-Path $backendRoot "output\$($suite.Name.Replace(' ', '-')).stdout.log"
        $backendStderr = Join-Path $backendRoot "output\$($suite.Name.Replace(' ', '-')).stderr.log"
        $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$backendPort") -WorkingDirectory $isolatedBackend -WindowStyle Hidden -RedirectStandardOutput $backendStdout -RedirectStandardError $backendStderr -PassThru

        $backendReady = $false
        for ($attempt = 0; $attempt -lt 60; $attempt += 1) {
            try {
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:$backendPort/health" -TimeoutSec 2
                if ($health.status -eq 'ok') { $backendReady = $true; break }
            }
            catch { Start-Sleep -Milliseconds 500 }
        }
        if (-not $backendReady) { throw "Backend did not become ready for $($suite.Name)." }

        [Environment]::SetEnvironmentVariable($suite.Flag, $(if ($suite.Flag -eq 'FDAS_PHASE10_12C_CAPTURE') { 'after' } else { '1' }), 'Process')
        Write-Host "`n--- $($suite.Name) ---"
        Push-Location $frontendRoot
        try {
            & $nodePath $suite.Script
            if ($LASTEXITCODE -ne 0) { throw "$($suite.Name) failed with exit code $LASTEXITCODE." }
        }
        finally {
            Pop-Location
            [Environment]::SetEnvironmentVariable($suite.Flag, $null, 'Process')
        }

        if ($backendProcess -and -not $backendProcess.HasExited) { Stop-Process -Id $backendProcess.Id -Force }
        $backendProcess = $null
        Start-Sleep -Milliseconds 500
    }
}
finally {
    Stop-TestProcesses
    if ($frontendProcess -and -not $frontendProcess.HasExited) { Stop-Process -Id $frontendProcess.Id -Force -ErrorAction SilentlyContinue }
    foreach ($name in $environmentChanges.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    $resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $backendRoot 'output'))
    foreach ($isolatedRoot in $isolatedRoots) {
        $resolvedIsolated = [System.IO.Path]::GetFullPath($isolatedRoot)
        if ($resolvedIsolated.StartsWith($resolvedOutput, [System.StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedIsolated)) {
            Remove-Item -LiteralPath $resolvedIsolated -Recurse -Force
        }
    }
}
