# start.ps1 - Script to release port and start Offerte Monitor

$Port = 5000

# Try to parse port from config/config.yaml
if (Test-Path "config/config.yaml") {
    $config = Get-Content "config/config.yaml" -Raw
    if ($config -match 'port:\s*(\d+)') {
        $Port = [int]$Matches[1]
    }
}

Write-Host "Checking for active connections on port $Port..." -ForegroundColor Cyan

# Find any listening TCP connections on specified port
$connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue

if ($connections) {
    $procIds = $connections.OwningProcess | Select-Object -Unique
    foreach ($procId in $procIds) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            Write-Host "Terminating process '$($proc.Name)' (PID: $procId) using port $Port..." -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "Successfully released port." -ForegroundColor Green
        } catch {
            Write-Host "Could not kill process (PID: $procId): $_" -ForegroundColor Red
        }
    }
    Start-Sleep -Seconds 1
} else {
    Write-Host "Port $Port is free." -ForegroundColor Green
}

Write-Host "Launching Offerte Monitor application..." -ForegroundColor Cyan
if (Test-Path ".\\.venv\\Scripts\\python.exe") {
    .\\.venv\\Scripts\\python.exe main.py
} else {
    Write-Host "Error: .\\.venv\\Scripts\\python.exe not found. Make sure virtualenv is created." -ForegroundColor Red
}
