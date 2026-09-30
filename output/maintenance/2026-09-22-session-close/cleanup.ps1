param([switch]$Preview)
$ErrorActionPreference='Stop'
$auditPath=$PSScriptRoot
$plan=Get-Content -LiteralPath (Join-Path $auditPath 'cleanup-plan.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$workspacePath=(Resolve-Path -LiteralPath $plan.workspace).Path.TrimEnd('\')
$runtimePath='C:\Users\pppp\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
$validated=@()
foreach($target in $plan.targets){
  $candidate=[IO.Path]::GetFullPath((Join-Path $workspacePath $target.relative_path))
  if(-not $candidate.StartsWith($workspacePath+'\',[StringComparison]::OrdinalIgnoreCase) -or $candidate -ne $target.absolute_path){throw "Path outside recorded workspace: $candidate"}
  if(-not (Test-Path -LiteralPath $candidate)){continue}
  $item=Get-Item -LiteralPath $candidate -Force
  if($target.kind -eq 'junction'){
    if($item.LinkType -ne 'Junction' -or $item.Target[0] -ne $runtimePath){throw 'Unexpected junction identity'}
  } else {
    if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Unexpected reparse point'}
    $parent=$item.Parent
    if($item.PSIsContainer){$parent=$item.Parent}
    while($parent -and $parent.FullName -ne $workspacePath){
      if($parent.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse ancestor'}
      $parent=$parent.Parent
    }
    if($item.PSIsContainer){
      $nested=@(Get-ChildItem -LiteralPath $candidate -Force -Recurse | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
      if($nested.Count -gt 0){throw 'Nested reparse point'}
    }
  }
  $validated+=@{path=$candidate;kind=$target.kind}
}
if($Preview){$validated | ForEach-Object { "PREVIEW $($_.kind): $($_.path)" };exit 0}
$results=@()
foreach($entry in $validated){
  try {
    if($entry.kind -eq 'junction'){
      # Nonrecursive directory deletion unlinks this junction without visiting the target.
      [IO.Directory]::Delete($entry.path,$false)
    }elseif($entry.kind -eq 'directory'){
      Remove-Item -LiteralPath $entry.path -Recurse -Force
    }else{
      Remove-Item -LiteralPath $entry.path -Force
    }
    $results+=@{path=$entry.path;status='removed'}
  }catch{
    $results+=@{path=$entry.path;status='failed';error=$_.Exception.Message}
  }
}
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $auditPath 'cleanup-execution.json') -Encoding UTF8
if(-not (Test-Path -LiteralPath $runtimePath)){throw 'External runtime disappeared'}
$results | Group-Object status | Select-Object Name,Count
