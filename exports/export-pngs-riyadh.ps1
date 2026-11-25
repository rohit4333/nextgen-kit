# Export the six Riyadh carousel slides as high-res PNGs (2x or 4K).
# Run:  powershell -ExecutionPolicy Bypass -File .\exports\export-pngs-riyadh.ps1
#       powershell -ExecutionPolicy Bypass -File .\exports\export-pngs-riyadh.ps1 -Scale 4
# Out:  exports\png-riyadh\*.png      (2160x2160)  when -Scale 2
#       exports\png-riyadh-4k\*.png  (4320x4320)  when -Scale 4

param(
  [double]$Scale = 2,
  [string[]]$Only,
  [string]$OutDir
)

$ErrorActionPreference = 'Stop'

$root   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$source = Join-Path $root 'nextgen-creative-kit-riyadh.html'
if (-not $OutDir) {
  $OutDir = if ($Scale -ge 4) { 'exports\png-riyadh-4k' } else { 'exports\png-riyadh' }
}
$outDir = Join-Path $root $OutDir
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$chrome = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
  'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw 'Chrome or Edge not found.' }

$assets = @(
  @{ key = 's1'; name = 'deck-riyadh-01-the-fear' },
  @{ key = 's2'; name = 'deck-riyadh-02-why-it-happens' },
  @{ key = 's3'; name = 'deck-riyadh-03-the-fix' },
  @{ key = 's4'; name = 'deck-riyadh-04-the-tutor' },
  @{ key = 's5'; name = 'deck-riyadh-05-the-first-session' },
  @{ key = 's6'; name = 'deck-riyadh-06-next-step' }
)

$baseUri = ([System.Uri]$source).AbsoluteUri
$profile = Join-Path $env:TEMP ("riyadh-export-" + [guid]::NewGuid().ToString('N').Substring(0, 8))

foreach ($a in $assets) {
  if ($Only -and -not ($Only -contains $a.key -or $Only -contains $a.name)) { continue }
  $out = Join-Path $outDir ($a.name + '.png')
  $w = [int](1080 * $Scale)
  $h = [int](1080 * $Scale)
  $url = "$baseUri#export=$($a.key)"

  $ErrorActionPreference = 'Continue'
  & $chrome --headless=new --disable-gpu --hide-scrollbars --no-first-run `
    --force-device-scale-factor=$Scale --window-size="1080,1080" `
    --virtual-time-budget=6000 --user-data-dir="$profile" `
    --screenshot="$out" $url 2>&1 | Out-Null
  $ErrorActionPreference = 'Stop'

  if (-not (Test-Path $out)) { throw "Screenshot failed for $($a.name)" }
  $bytes = [System.IO.File]::ReadAllBytes($out)
  $pw = [int]$bytes[16] * 16777216 + [int]$bytes[17] * 65536 + [int]$bytes[18] * 256 + [int]$bytes[19]
  $ph = [int]$bytes[20] * 16777216 + [int]$bytes[21] * 65536 + [int]$bytes[22] * 256 + [int]$bytes[23]
  if ($pw -ne $w -or $ph -ne $h) { Write-Host ("  !  {0} is {1}x{2}, expected {3}x{4}" -f $a.name, $pw, $ph, $w, $h) -ForegroundColor Yellow }
  Write-Host ("[ok] {0,-30} {1,4}x{2,-4}  {3,7:N0} KB" -f $a.name, $pw, $ph, ($bytes.Length / 1KB)) -ForegroundColor Green
}

Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
Write-Host "`nDone -> $outDir" -ForegroundColor Cyan
