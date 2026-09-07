$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "[1/3] Creating the Python virtual environment..."
    python -m venv (Join-Path $ProjectDir ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the virtual environment (exit code $LASTEXITCODE)."
    }
}

Write-Host "[2/3] Installing runtime dependencies..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip (exit code $LASTEXITCODE)."
}
& $VenvPython -m pip install -r (Join-Path $ProjectDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install dependencies (exit code $LASTEXITCODE)."
}

$EnvFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Copy-Item -LiteralPath (Join-Path $ProjectDir ".env.example") -Destination $EnvFile
    Write-Host "[3/3] Created .env. Add API keys there if needed."
} else {
    Write-Host "[3/3] Kept the existing .env file."
}

Write-Host "Setup complete. Run .\start.ps1 to start the server." -ForegroundColor Green
