$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Virtual environment not found. Run .\setup.ps1 first."
}

Set-Location -LiteralPath $ProjectDir
& $VenvPython run.py
exit $LASTEXITCODE
