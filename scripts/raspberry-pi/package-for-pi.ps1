[CmdletBinding()]
param(
    [string]$OutputPath,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir '..\..'))
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $ProjectRoot 'dist\refound-pi.tar.gz'
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)

$Tar = Get-Command 'tar.exe' -ErrorAction SilentlyContinue
if (-not $Tar) {
    $Tar = Get-Command 'tar' -ErrorAction SilentlyContinue
}
if (-not $Tar) {
    throw 'tar was not found. Current Windows 10/11 normally includes tar.exe.'
}

if ((Test-Path -LiteralPath $OutputPath) -and -not $Force) {
    throw "Archive already exists: $OutputPath`nRun again with -Force to replace this one file."
}

$OutputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}
if (Test-Path -LiteralPath "$OutputPath.sha256") {
    Remove-Item -LiteralPath "$OutputPath.sha256" -Force
}

$TemplatePath = Join-Path $ProjectRoot '.env.example'
if (-not (Test-Path -LiteralPath $TemplatePath)) {
    throw '.env.example is missing.'
}
$TemplateText = Get-Content -Raw -LiteralPath $TemplatePath
if ($TemplateText -match '(?m)^[ \t]*(OPENAI_API_KEY|GEMINI_API_KEY|SMTP_PASSWORD)[ \t]*=[ \t]*[^\s#]') {
    throw '.env.example appears to contain a secret. Packaging was stopped.'
}

# Security allowlist: only runtime source and blank configuration templates are
# eligible. In particular, .env, data, reset backups, browser caches, and the
# Windows virtual environment are never traversed or added.
$Includes = @(
    'app',
    'experiments',
    'static',
    'templates',
    'scripts/experiments',
    'scripts/raspberry-pi',
    'run.py',
    'requirements.txt',
    '.env.example'
)
foreach ($OptionalFile in @(
    'requirements-pi.txt',
    'docs/guides/FRESH_SD_START.md',
    'docs/guides/PI_ACCEPTANCE_CHECKLIST.md',
    'docs/guides/RASPBERRY_PI_GUIDE.md',
    'docs/guides/SCHOOL_DEMO_GUIDE.md',
    'docs/guides/PI_MONITOR_WIFI_GUIDE.md'
)) {
    if (Test-Path -LiteralPath (Join-Path $ProjectRoot $OptionalFile)) {
        $Includes += $OptionalFile
    }
}

$TarArguments = @(
    '-czf', $OutputPath,
    '--exclude=__pycache__',
    '--exclude=*/__pycache__/*',
    '--exclude=*.pyc',
    '--exclude=*.pyo',
    '--exclude=.pytest_cache',
    '-C', $ProjectRoot
) + $Includes

& $Tar.Source @TarArguments
if ($LASTEXITCODE -ne 0) {
    throw "tar failed with exit code $LASTEXITCODE"
}

$Entries = @(& $Tar.Source -tzf $OutputPath)
if ($LASTEXITCODE -ne 0) {
    throw 'The generated archive could not be read back.'
}
$ForbiddenPatterns = @(
    '(^|/)\.env$',
    '(^|/)data(/|$)',
    '(^|/)\.venv(/|$)',
    '(^|/)\.git(/|$)',
    '(^|/)reset-backups(/|$)',
    '(^|/)__pycache__(/|$)',
    '\.(pyc|pyo)$'
)
foreach ($Entry in $Entries) {
    foreach ($Pattern in $ForbiddenPatterns) {
        if ($Entry -match $Pattern) {
            Remove-Item -LiteralPath $OutputPath -Force
            throw "Safety check rejected archive entry: $Entry"
        }
    }
}

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPath).Hash.ToLowerInvariant()
$HashPath = "$OutputPath.sha256"
Set-Content -LiteralPath $HashPath -Encoding ascii -NoNewline -Value "$Hash  $([System.IO.Path]::GetFileName($OutputPath))`n"

$SizeMiB = [Math]::Round((Get-Item -LiteralPath $OutputPath).Length / 1MB, 2)
Write-Host "Created safe Raspberry Pi package: $OutputPath ($SizeMiB MiB)"
Write-Host "SHA-256: $Hash"
Write-Host 'Verified absent: .env, data/, .venv/, Git metadata, caches, reset backups.'
