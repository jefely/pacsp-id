# Push PACSP-ID to the remote repository.
#
# Run this in your own PowerShell window:
#   cd D:\myproject\PACSP-ID
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\push_all.ps1
#
# To supply credentials (prefer a personal access token over a password):
#   $env:GIT_USER  = "jefely"
#   $env:GIT_TOKEN = "ghp_xxxxxxxxxxxx"
#
# Optionally also push to Gitee:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\push_all.ps1 -Gitee "git@gitee.com:jefely/pacsp-id.git"

param(
    [string]$Remote = "origin",
    [string]$Branch = "main",
    [string]$Gitee  = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Continue"
function Info($m) { Write-Host "  $m" }
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!] $m"  -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [X] $m"  -ForegroundColor Red }

Write-Host "== 1/6 repository state ==" -ForegroundColor Cyan
$dirty = @(git status --porcelain)
if ($dirty.Count -gt 0) {
    Warn "there are $($dirty.Count) uncommitted change(s):"
    $dirty | Select-Object -First 10 | ForEach-Object { Info $_ }
} else {
    Ok "working tree clean"
}
Info "branch : $(git branch --show-current)"
Info "remote : $(git remote get-url $Remote 2>&1)"

Write-Host ""
Write-Host "== 2/6 commits to push ==" -ForegroundColor Cyan
$ahead = @(git log --oneline "$Remote/$Branch..HEAD" 2>&1)
if ($LASTEXITCODE -ne 0) {
    Warn "cannot compare against $Remote/$Branch; listing recent commits instead"
    $ahead = @(git log --oneline -10)
}
Info "ahead of $Remote/$Branch by $($ahead.Count) commit(s)"
$ahead | ForEach-Object { Info $_ }

if (-not $SkipTests) {
    Write-Host ""
    Write-Host "== 3/6 pre-push verification ==" -ForegroundColor Cyan
    $py = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
    if (Test-Path -LiteralPath $py) {
        $env:PYTHONIOENCODING = "utf-8"
        $env:PYTHONPATH = "$PWD\scripts"
        Info "six-layer verification..."
        $pass = 0
        $fail = 0
        foreach ($f in Get-ChildItem "$PWD\records" -Filter *.pacsp) {
            $dom = $f.Name -replace "^(machine_)?([a-z]+)_.*$", "$1$2"
            $res = & $py -X utf8 "$PWD\scripts\pacsp_verify.py" $f.FullName "$PWD\data\$dom" 2>&1 | Out-String
            if ($res -match "结果: VERIFIED") { $pass++ } else { $fail++; Bad $f.Name }
        }
        if ($fail -eq 0) { Ok "six-layer verification $pass/$($pass + $fail) passed" }
        else { Bad "$fail record(s) failed" }
        Info "compile check..."
        & $py -X utf8 -c "import compileall,sys; sys.exit(0 if compileall.compile_dir(r'$PWD\scripts', quiet=2, force=True) else 1)" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Ok "scripts compile" } else { Bad "compile failed" }
    } else {
        Warn "python not found; skipping verification"
    }
} else {
    Write-Host ""
    Write-Host "== 3/6 verification skipped ==" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "== 4/6 credentials ==" -ForegroundColor Cyan
$url = git remote get-url $Remote 2>&1
$restore = $null
if ($env:GIT_TOKEN -and $url -match "^https://github\.com/(.+?)(\.git)?$") {
    $repoPath = $matches[1] -replace "\.git$", ""
    $user = if ($env:GIT_USER) { $env:GIT_USER } else { "git" }
    git remote set-url $Remote "https://${user}:$($env:GIT_TOKEN)@github.com/${repoPath}.git"
    $restore = $url
    Ok "temporary authenticated remote set"
} else {
    Info "no GIT_TOKEN; relying on the system credential manager"
    Warn "if that fails: git config --global credential.helper manager"
}

Write-Host ""
Write-Host "== 5/6 push to $Remote ==" -ForegroundColor Cyan
git push $Remote $Branch 2>&1 | ForEach-Object { Info $_ }
$pushOk = ($LASTEXITCODE -eq 0)

if ($restore) {
    git remote set-url $Remote $restore
    Ok "remote url restored (token removed)"
}

if ($pushOk) { Ok "push succeeded" } else { Bad "push failed; see git output above" }

if ($Gitee) {
    Write-Host ""
    Write-Host "== 5b/6 push to Gitee ==" -ForegroundColor Cyan
    if (@(git remote) -notcontains "gitee") {
        git remote add gitee $Gitee
        Info "added remote gitee"
    } else {
        git remote set-url gitee $Gitee
    }
    git push gitee $Branch 2>&1 | ForEach-Object { Info $_ }
    if ($LASTEXITCODE -eq 0) { Ok "Gitee push succeeded" } else { Bad "Gitee push failed" }
}

Write-Host ""
Write-Host "== 6/6 result ==" -ForegroundColor Cyan
git log --oneline -3 | ForEach-Object { Info $_ }
Info "$Remote/$Branch : $(if ($pushOk) { 'in sync' } else { 'NOT in sync' })"

if (-not $pushOk) {
    Write-Host ""
    Warn "push did not succeed. Common causes:"
    Info "1. no credentials     -> git config --global credential.helper manager"
    Info "2. network intercepted (domains resolve to 198.18.x.x) -> change network or use Gitee"
    Info "3. remote has new work -> git pull --rebase $Remote $Branch, then retry"
    Info "4. token lacks scope  -> needs repo or public_repo"
}
