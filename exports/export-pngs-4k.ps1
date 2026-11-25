# Export the 6 carousel slides as true 4K PNGs (4320 x 4320).
# Chrome re-rasterises all text / SVG / gradients at 4x, so they stay perfectly
# sharp; the tutor cutout is pre-upscaled to 1654x2450 by prepare-tutor-photo.py.
# Run:  powershell -ExecutionPolicy Bypass -File .\exports\export-pngs-4k.ps1
#       ... -Only s4      # re-export just one slide
# Output: exports\png-4k\*.png

param(
  [double]$Scale = 4,
  [string[]]$Only
)

$ErrorActionPreference = 'Stop'

$root   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$source = Join-Path $root 'nextgen-creative-kit.html'
$outDir = Join-Path $root 'exports\png-4k'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$chrome = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
  'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw 'Chrome or Edge not found. Install one, or pass a browser path.' }

$assets = @(
  @{ key = 's1'; name = 'deck-01-the-fear' },
  @{ key = 's2'; name = 'deck-02-why-it-happens' },
  @{ key = 's3'; name = 'deck-03-the-fix' },
  @{ key = 's4'; name = 'deck-04-the-tutor' },
  @{ key = 's5'; name = 'deck-05-the-first-session' },
  @{ key = 's6'; name = 'deck-06-next-step' }
)

$baseUri = ([System.Uri]$source).AbsoluteUri
$profile = Join-Path $env:TEMP ("kit-4k-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
$w = [int](1080 * $Scale)
$h = [int](1080 * $Scale)

foreach ($a in $assets) {
  if ($Only -and -not ($Only -contains $a.key -or $Only -contains $a.name)) { continue }
  $out = Join-Path $outDir ($a.name + '.png')
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
  Write-Host ("[ok] {0,-26} {1,4}x{2,-4}  {3,7:N0} KB" -f $a.name, $pw, $ph, ($bytes.Length / 1KB)) -ForegroundColor Green
}

Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
Write-Host "`nDone -> $outDir" -ForegroundColor Cyan
