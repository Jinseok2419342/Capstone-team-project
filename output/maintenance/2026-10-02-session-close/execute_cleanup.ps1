$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$taskPlan = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'cleanup-plan.json') | ConvertFrom-Json
if ($taskPlan.root -ne $taskRoot -or $taskPlan.target_count -ne 13) { throw 'Unexpected cleanup plan' }
$taskMaintenance = Join-Path $taskRoot 'output\maintenance'
$taskJournal = Join-Path $PSScriptRoot 'cleanup-execution.json'
$prior = if (Test-Path -LiteralPath $taskJournal) { @(Get-Content -Raw -Encoding UTF8 -LiteralPath $taskJournal | ConvertFrom-Json) } else { @() }
# Verify every absolute target and its complete file list before any deletion.
foreach ($target in $taskPlan.targets) {
    if (-not (Test-Path -LiteralPath $target.absolute)) {
        if (@($prior | Where-Object { $_.path -eq $target.path -and $_.status -eq 'removed' }).Count -ne 1) { throw 'Unexpected missing target' }
        continue
    }
    $resolved = (Resolve-Path -LiteralPath (Join-Path $taskRoot $target.path)).Path
    if ($resolved -ne $target.absolute -or -not $resolved.StartsWith($taskMaintenance + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Target escaped maintenance workspace' }
    $item = Get-Item -Force -LiteralPath $resolved
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw 'Refusing reparse point' }
    $members = if ($item.PSIsContainer) { @(Get-ChildItem -Force -Recurse -LiteralPath $resolved) } else { @($item) }
    if (@($members | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }).Count -gt 0) { throw 'Refusing nested reparse point' }
    $files = @($members | Where-Object { -not $_.PSIsContainer })
    # A stopped recursive deletion may have removed part of a directory.
    # Only the original, hash-verified allowlist may remain on resume.
    $allowedFiles = @($target.files | ForEach-Object { [System.IO.Path]::GetFullPath((Join-Path $taskRoot $_.path)) })
    foreach ($file in $files) { if ($file.FullName -notin $allowedFiles) { throw 'Unexpected file in deletion target' } }
    foreach ($entry in $target.files) {
        if (-not (Test-Path -LiteralPath (Join-Path $taskRoot $entry.path))) { continue }
        $filePath = (Resolve-Path -LiteralPath (Join-Path $taskRoot $entry.path)).Path
        if ($filePath -ne $resolved -and -not $filePath.StartsWith($resolved + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'File escaped deletion target' }
        $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $filePath).Hash.ToLowerInvariant()
        if ($hash -ne $entry.sha256) { throw 'File changed after inspection' }
    }
}
$executed = [System.Collections.Generic.List[object]]::new()
foreach ($target in $taskPlan.targets) {
    if (Test-Path -LiteralPath $target.absolute) {
        $resolved = (Resolve-Path -LiteralPath $target.absolute).Path
        if (-not $resolved.StartsWith($taskMaintenance + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe final path' }
        Remove-Item -LiteralPath $resolved -Recurse -Force -Confirm:$false
        if (Test-Path -LiteralPath $resolved) { throw 'Deletion incomplete' }
    }
    $executed.Add([pscustomobject]@{path=$target.path;files=$target.count;bytes=$target.bytes;status='removed'})
    $executed | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'cleanup-execution.json')
}
[pscustomobject]@{removedTargets=$executed.Count;removedFiles=$taskPlan.file_count;removedMiB=[math]::Round($taskPlan.bytes / 1MB,2)} | ConvertTo-Json
