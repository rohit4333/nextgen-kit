# Export every asset in nextgen-creative-kit.html as a high-res PNG (2x).
# Uses the locally installed Chrome in headless mode - no npm packages required.
# Run:  powershell -ExecutionPolicy Bypass -File .\exports\export-pngs.ps1
# Output: exports\png\*.png  (slides 2160x2160, reel frames 2160x3840, banner 3168x792)

param(
  [double]$Scale = 2,
  # Optional filter: re-export only these assets, by key or file name.
  # e.g.  -Only s4  or  -Only deck-04-the-tutor
  [string[]]$Only
)

$ErrorActionPreference = 'Stop'

$root   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$source = Join-Path $root 'nextgen-creative-kit.html'
$outDir = Join-Path $root 'exports\png'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$chrome = @(
  'C:\Program Files\Google\Chrome\Application\chrome.exe',
  'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
  "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
  'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
  'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { throw 'Chrome or Edge not found. Install one, or pass a browser path.' }

# key = #export= hash, w/h = natural CSS size of the asset, name = output file
$assets = @(
  @{ key = 's1';     w = 1080; h = 1080; name = 'deck-01-the-fear' },
  @{ key = 's2';     w = 1080; h = 1080; name = 'deck-02-why-it-happens' },
  @{ key = 's3';     w = 1080; h = 1080; name = 'deck-03-the-fix' },
  @{ key = 's4';     w = 1080; h = 1080; name = 'deck-04-the-tutor' },
  @{ key = 's5';     w = 1080; h = 1080; name = 'deck-05-the-first-session' },
  @{ key = 's6';     w = 1080; h = 1080; name = 'deck-06-next-step' },
  @{ key = 'li';     w = 1200; h = 1200; name = 'linkedin-founder-post' },
  @{ key = 'banner'; w = 1584; h = 396;  name = 'banner-linkedin' },
  @{ key = 'r1';     w = 1080; h = 1920; name = 'reel-01' },
  @{ key = 'r2';     w = 1080; h = 1920; name = 'reel-02' },
  @{ key = 'r3';     w = 1080; h = 1920; name = 'reel-03' },
  @{ key = 'r4';     w = 1080; h = 1920; name = 'reel-04' },
  @{ key = 'r5';     w = 1080; h = 1920; name = 'reel-05' },
  @{ key = 'r6';     w = 1080; h = 1920; name = 'reel-06' },
  @{ key = 'r7';     w = 1080; h = 1920; name = 'reel-07' },
  @{ key = 'r8';     w = 1080; h = 1920; name = 'reel-08' }
)

$baseUri = ([System.Uri]$source).AbsoluteUri
$profile = Join-Path $env:TEMP ("kit-export-" + [guid]::NewGuid().ToString('N').Substring(0, 8))

foreach ($a in $assets) {
  if ($Only -and -not ($Only -contains $a.key -or $Only -contains $a.name)) { continue }
  $out  = Join-Path $outDir ($a.name + '.png')
  $w    = [int]($a.w * $Scale)
  $h    = [int]($a.h * $Scale)
  $url  = "$baseUri#export=$($a.key)"

  $ErrorActionPreference = 'Continue'
  & $chrome --headless=new --disable-gpu --hide-scrollbars --no-first-run `
    --force-device-scale-factor=$Scale --window-size="$($a.w),$($a.h)" `
    --virtual-time-budget=5000 --user-data-dir="$profile" `
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
