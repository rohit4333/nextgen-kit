# Export the 4:5 portrait (1080x1350) carousels as PNGs.
# Run:  powershell -ExecutionPolicy Bypass -File .\exports\export-pngs-45.ps1
#       powershell -ExecutionPolicy Bypass -File .\exports\export-pngs-45.ps1 -Deck riyadh
#       powershell -ExecutionPolicy Bypass -File .\exports\export-pngs-45.ps1 -Scale 2   # 2160x2700
# Out:  exports\png-45\*.png          (main deck)
#       exports\png-riyadh-45\*.png  (Riyadh deck)

param(
  [ValidateSet('all','main','riyadh')][string]$Deck = 'all',
  [double]$Scale = 1,
  [string[]]$Only
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

$chrome = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
  'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw 'Chrome or Edge not found.' }

$decks = @(
  @{ key = 'main';   source = 'nextgen-creative-kit-45.html';       out = 'exports\png-45';       prefix = 'deck' },
  @{ key = 'riyadh'; source = 'nextgen-creative-kit-riyadh-45.html'; out = 'exports\png-riyadh-45'; prefix = 'deck-riyadh' }
)

$slides = @(
  @{ key = 's1'; name = '01-the-fear' },
  @{ key = 's2'; name = '02-why-it-happens' },
  @{ key = 's3'; name = '03-the-fix' },
  @{ key = 's4'; name = '04-the-tutor' },
  @{ key = 's5'; name = '05-the-first-session' },
  @{ key = 's6'; name = '06-next-step' }
)

$expectedW = [int](1080 * $Scale)
$expectedH = [int](1350 * $Scale)

foreach ($d in $decks) {
  if ($Deck -ne 'all' -and $Deck -ne $d.key) { continue }
  $source = Join-Path $root $d.source
  if (-not (Test-Path $source)) { throw "Missing $source — run make-carousel-45.py first." }
  $outDir = Join-Path $root $d.out
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
  $baseUri = ([System.Uri]$source).AbsoluteUri
  $profile = Join-Path $env:TEMP ("c45-" + $d.key + "-" + [guid]::NewGuid().ToString('N').Substring(0, 8))

  Write-Host "`n== $($d.key) -> $($d.out) ==" -ForegroundColor Cyan
  foreach ($s in $slides) {
    if ($Only -and -not ($Only -contains $s.key -or $Only -contains $s.name)) { continue }
    $name = "$($d.prefix)-$($s.name)"
    $out = Join-Path $outDir ($name + '.png')
    $url = "$baseUri#export=$($s.key)"

    $ErrorActionPreference = 'Continue'
    & $chrome --headless=new --disable-gpu --hide-scrollbars --no-first-run `
      --force-device-scale-factor=$Scale --window-size="1080,1350" `
      --virtual-time-budget=6000 --user-data-dir="$profile" `
      --screenshot="$out" $url 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'

    if (-not (Test-Path $out)) { throw "Screenshot failed for $name" }
    $bytes = [System.IO.File]::ReadAllBytes($out)
    $pw = [int]$bytes[16] * 16777216 + [int]$bytes[17] * 65536 + [int]$bytes[18] * 256 + [int]$bytes[19]
    $ph = [int]$bytes[20] * 16777216 + [int]$bytes[21] * 65536 + [int]$bytes[22] * 256 + [int]$bytes[23]
    if ($pw -ne $expectedW -or $ph -ne $expectedH) {
      Write-Host ("  !  {0} is {1}x{2}, expected {3}x{4}" -f $name, $pw, $ph, $expectedW, $expectedH) -ForegroundColor Yellow
    }
    Write-Host ("[ok] {0,-38} {1,4}x{2,-5} {3,7:N0} KB" -f $name, $pw, $ph, ($bytes.Length / 1KB)) -ForegroundColor Green
  }
  Remove-Item -Recurse -Force $profile -ErrorAction SilentlyContinue
}

Write-Host "`nDone." -ForegroundColor Cyan
