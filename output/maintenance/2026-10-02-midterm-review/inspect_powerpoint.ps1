param([string]$DeckPath,[string]$RenderName = 'powerpoint-v4')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$deckFull = (Resolve-Path -LiteralPath $DeckPath).Path
$renderDir = Join-Path $PSScriptRoot $RenderName
New-Item -ItemType Directory -Path $renderDir -Force | Out-Null
$hadPowerPoint = @(Get-Process POWERPNT -ErrorAction SilentlyContinue).Count -gt 0
$app = New-Object -ComObject PowerPoint.Application
$presentation = $null
$records = [System.Collections.Generic.List[object]]::new()
function Inspect-Text($shape, [int]$slideNo, [string]$kind) {
    if ($shape.HasTextFrame -ne -1 -or $shape.TextFrame.HasText -ne -1) { return }
    $tr = $shape.TextFrame.TextRange
    $text = [string]$tr.Text
    $tf = $shape.TextFrame
    $bounds = @{left=[double]$tr.BoundLeft;top=[double]$tr.BoundTop;width=[double]$tr.BoundWidth;height=[double]$tr.BoundHeight}
    $lines = @()
    $lineCount = $tr.Lines().Count
    for ($n = 1; $n -le $lineCount; $n++) {
        $lineRange = $tr.Lines($n,1)
        $lines += [pscustomobject]@{text=[string]$lineRange.Text;left=[double]$lineRange.BoundLeft;top=[double]$lineRange.BoundTop;width=[double]$lineRange.BoundWidth;height=[double]$lineRange.BoundHeight}
    }
    $availableW = [double]$shape.Width - [double]$tf.MarginLeft - [double]$tf.MarginRight
    $availableH = [double]$shape.Height - [double]$tf.MarginTop - [double]$tf.MarginBottom
    $records.Add([pscustomobject]@{
        slide=$slideNo;kind=$kind;name=[string]$shape.Name;text=$text
        x=[double]$shape.Left;y=[double]$shape.Top;width=[double]$shape.Width;height=[double]$shape.Height
        availableW=$availableW;availableH=$availableH;bounds=$bounds;lines=$lines
        overflowW=([double]$tr.BoundWidth - $availableW -gt 1.5)
        overflowH=([double]$tr.BoundHeight - $availableH -gt 1.5)
    })
}
try {
    $presentation = $app.Presentations.Open($deckFull, -1, 0, 0)
    foreach ($slide in $presentation.Slides) {
        $no = [int]$slide.SlideIndex
        $slide.Export((Join-Path $renderDir ('slide-{0:d2}.png' -f $no)), 'PNG',1600,900)
        foreach ($shape in $slide.Shapes) {
            if ($shape.HasTable -eq -1) {
                for($r=1;$r -le $shape.Table.Rows.Count;$r++){
                    for($c=1;$c -le $shape.Table.Columns.Count;$c++){
                        Inspect-Text $shape.Table.Cell($r,$c).Shape $no ('cell:{0},{1}' -f $r,$c)
                    }
                }
            } else { Inspect-Text $shape $no 'shape' }
        }
    }
    $records | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $renderDir 'text-layout.json') -Encoding UTF8
    $issues=@($records | Where-Object {$_.overflowW -or $_.overflowH})
    [pscustomobject]@{slides=$presentation.Slides.Count;textAreas=$records.Count;overflowCount=$issues.Count;renderDir=$renderDir;issues=$issues} | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $renderDir 'summary.json') -Encoding UTF8
    [pscustomobject]@{slides=$presentation.Slides.Count;textAreas=$records.Count;overflowCount=$issues.Count;renderDir=$renderDir} | ConvertTo-Json
    $issues | Select-Object slide,kind,text,overflowW,overflowH | ConvertTo-Json -Depth 5
} finally {
    if ($null -ne $presentation) { $presentation.Close() }
    if (-not $hadPowerPoint) { $app.Quit() }
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
