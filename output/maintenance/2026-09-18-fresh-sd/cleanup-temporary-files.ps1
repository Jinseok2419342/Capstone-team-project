# Optional manual cleanup after reviewing cleanup-retry-plan.json.
# Preview: powershell.exe -NoProfile -ExecutionPolicy Bypass -File <this-file> -WhatIf
# The assistant has tested this file with -WhatIf only (no deletion).
[CmdletBinding(SupportsShouldProcess = $true)]
param()
$ErrorActionPreference = 'Stop'
$cleanupRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$fixtureParent = Join-Path $cleanupRoot 'output\maintenance\2026-09-18-live-flow-review'
# Windows PowerShell 5.1 emits a JSON array as one pipeline object. Assign it
# directly so foreach sees its entries rather than a nested Object[].
$cleanupPlan = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'cleanup-retry-plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$verifiedTargets = @()
foreach ($entry in $cleanupPlan) {
    if ($entry.relative_path -isnot [string] -or $entry.absolute_path -isnot [string] -or [string]::IsNullOrWhiteSpace($entry.relative_path)) {
        throw 'Invalid cleanup plan entry: expected one relative and one absolute path string.'
    }
    $candidate = Join-Path $cleanupRoot $entry.relative_path
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $target = (Resolve-Path -LiteralPath $candidate).Path
    if ($target -ne $entry.absolute_path -or -not $target.StartsWith($cleanupRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target outside the reviewed workspace: $candidate"
    }
    $leaf = Split-Path -Leaf $target
    $isCache = $leaf -eq '__pycache__'
    $isFixture = (Split-Path -Parent $target) -eq $fixtureParent -and $leaf -match '^browser-fixture-[a-z0-9_]+$'
    $isEmptyTemp = $target -eq (Join-Path $cleanupRoot 'tmp')
    if (-not ($isCache -or $isFixture -or $isEmptyTemp)) { throw "Unapproved target: $target" }
    $ancestor = $target
    while ($ancestor -ne $cleanupRoot) {
        if ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked path refused: $ancestor" }
        $ancestor = Split-Path -Parent $ancestor
    }
    $entries = @(Get-ChildItem -LiteralPath $target -Recurse -Force)
    if (@($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count) { throw "Linked descendant: $target" }
    if ($isCache -and @($entries | Where-Object { -not $_.PSIsContainer -and $_.Extension -ne '.pyc' }).Count) { throw "Unexpected cache contents: $target" }
    if ($isEmptyTemp -and $entries.Count) { throw 'tmp is no longer empty.' }
    $verifiedTargets += $target
}
if (Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -in @(8765, 8766) }) {
    throw 'A process is listening on a browser test port. Stop the test server/browser before cleanup.'
}
foreach ($target in $verifiedTargets) {
    if ($PSCmdlet.ShouldProcess($target, 'Delete reviewed generated files')) {
        Remove-Item -LiteralPath $target -Recurse -Force
        Write-Output "Removed: $target"
    }
}
Write-Output ("Checked {0} temporary directories. WhatIf={1}" -f $verifiedTargets.Count, [bool]$WhatIfPreference)
