# --- Activate venv if not already active ---
if (-not $env:VIRTUAL_ENV) {
    & "$PSScriptRoot\.venv\Scripts\Activate.ps1"
}

# --- Prepare log file for backend ---
$logFile = Join-Path $PSScriptRoot "uvicorn.log"
if (Test-Path $logFile) { Remove-Item $logFile }

# --- Start backend in a new terminal, teeing output to log file ---
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$PSScriptRoot'; " +
    "& '.venv\Scripts\Activate.ps1'; " +
    "uvicorn Backend.main:app --reload 2>&1 | Tee-Object -FilePath '$logFile'"
)

Write-Host "Waiting for backend to start..."

# --- Wait until Uvicorn logs 'Application startup complete.' ---
while ($true) {
    if (Test-Path $logFile) {
        $content = Get-Content $logFile -Raw
        if ($content -match 'Application startup complete') {
            Write-Host "Backend is ready."
            break
        }
    }
    Start-Sleep -Milliseconds 200
}

# --- Start frontend in a new terminal ---
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev -- --open"