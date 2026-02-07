# Activate venv if not already active
if (-not $env:VIRTUAL_ENV) {
    & "$PSScriptRoot\.venv\Scripts\Activate.ps1"
}

# Start backend in a new terminal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; & '.venv\Scripts\Activate.ps1'; uvicorn Backend.main:app --reload"

# Wait then start frontend in a new terminal
Start-Sleep -Seconds 5
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev -- --open"
