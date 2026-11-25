# One-time setup: sign in to GitHub, create the private repo, and push this project.
#
# Run (double-click or from a terminal):
#   powershell -ExecutionPolicy Bypass -File .\push-to-github.ps1
#
# It only does work that is not already done: it reuses an existing gh login,
# an existing remote, and only commits when there are changes to commit.

$ErrorActionPreference = 'Stop'
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")

Set-Location $PSScriptRoot

$repoName = 'nextgen-creative-kit'

# 1. authenticate (skipped when already signed in)
gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nSigning in to GitHub..." -ForegroundColor Cyan
    gh auth login --hostname github.com --git-protocol https --web --scopes repo
    if ($LASTEXITCODE -ne 0) { throw "GitHub sign-in failed." }
}

$login = gh api user --jq .login
$mail  = gh api user --jq '.email // empty'
if (-not $mail) { $mail = "$login@users.noreply.github.com" }

# 2. commit identity (local to this repo)
git config user.name  $login
git config user.email $mail

# 3. commit (only if something is staged/unstaged)
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "NextGen creative kit: deck, social exports, 60s reel with produced audio"
} else {
    Write-Host "Nothing new to commit." -ForegroundColor DarkGray
}

# 4. create the private repo and push (or just push if it already exists)
$hasRemote = (git remote) -contains 'origin'
if (-not $hasRemote) {
    gh repo create $repoName --private --source=. --remote=origin --push
} else {
    git push -u origin HEAD
}

Write-Host "`nDone -> https://github.com/$login/$repoName" -ForegroundColor Green
