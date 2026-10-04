# Build and release the PACSP-ID preprint.
#
# Usage (from anywhere):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pacsp_release.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pacsp_release.ps1 -SkipPdf
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\pacsp_release.ps1 -NoRelease
#
# Stage 1 (formulas, DOCX, checks) runs in a normal shell.
# Stage 2 (DOCX -> PDF) needs LibreOffice, which spawns a child process. Under a
# restricted sandbox that spawn is refused with EPERM, so run this script in a
# plain terminal, or grant wider access for that one command.

param(
    [string]$LibreOfficeCli = "",
    [string]$NodeExe        = "",
    [string]$Version        = "7.0.0",
    [switch]$SkipPdf,
    [switch]$NoRelease,
    [switch]$SkipChecks
)

$ErrorActionPreference = "Continue"

function Info($m) { Write-Host "  $m" }
function Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!] $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [X] $m" -ForegroundColor Red }

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $RepoRoot "docs\PACSP-ID-7.0.0-COMPLETE.md"))) {
    Bad "repository root not found from $PSScriptRoot"
    exit 1
}

$PdfPy   = "C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$MbPy    = "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
$Checker = "C:\Users\Administrator\AppData\Local\Programs\DeepSeek Harness\resources\runtime\office-skills\scripts\check_office.py"

if (-not $NodeExe) {
    $NodeExe = "C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
}
if (-not $LibreOfficeCli) {
    $LibreOfficeCli = "C:\Users\Administrator\AppData\Local\Programs\DeepSeek Harness\resources\app.asar.unpacked\dsh\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js"
}

$BuildDir = Join-Path $RepoRoot "build"
$DistDir  = Join-Path $RepoRoot "dist"
$Docx     = Join-Path $BuildDir "PACSP-ID-$Version-preprint.docx"
$Pdf      = Join-Path $BuildDir "PACSP-ID-$Version-preprint.pdf"
$OutDocx  = Join-Path $DistDir  "PACSP-ID-$Version-preprint.docx"
$OutPdf   = Join-Path $DistDir  "PACSP-ID-$Version-preprint.pdf"

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " PACSP-ID $Version preprint build" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# ---------------------------------------------------------------- stage 1
Write-Host ""
Write-Host "-- stage 1: formulas --" -ForegroundColor Cyan
$formulaScript = Join-Path $RepoRoot "scripts\pacsp_formula.py"
if (-not (Test-Path $formulaScript)) { Bad "missing $formulaScript"; exit 1 }
& $MbPy -X utf8 $formulaScript
if ($LASTEXITCODE -ne 0) { Bad "formula rendering failed"; exit 1 }
$eqCount = @(Get-ChildItem (Join-Path $RepoRoot "cache\formulas") -Filter "eq_*.png" -ErrorAction SilentlyContinue).Count
Ok "$eqCount formula images"

Write-Host ""
Write-Host "-- stage 2: parse check --" -ForegroundColor Cyan
& $MbPy -X utf8 (Join-Path $RepoRoot "scripts\pacsp_parse.py") | Select-Object -First 6 | ForEach-Object { Info $_ }

Write-Host ""
Write-Host "-- stage 3: assemble DOCX --" -ForegroundColor Cyan
if (-not (Test-Path $PdfPy)) {
    $PdfPy = $MbPy
    Warn "bundled python not found; falling back to $PdfPy (python-docx may be absent)"
}
& $PdfPy -X utf8 (Join-Path $RepoRoot "scripts\pacsp_docx.py")
if ($LASTEXITCODE -ne 0) { Bad "DOCX assembly failed"; exit 1 }
if (-not (Test-Path $Docx)) { Bad "DOCX not produced"; exit 1 }
Ok ("DOCX {0:N0} bytes" -f (Get-Item $Docx).Length)

# ---------------------------------------------------------------- checks
if (-not $SkipChecks) {
    Write-Host ""
    Write-Host "-- stage 4: structural check --" -ForegroundColor Cyan
    if (Test-Path $Checker) {
        $checksJson = Join-Path $BuildDir "checks.json"
        & $PdfPy -X utf8 $Checker $Docx --out $checksJson | Out-Null
        if (Test-Path $checksJson) {
            $cj = Get-Content $checksJson -Raw | ConvertFrom-Json
            if ($cj.verdict -eq "pass") {
                Ok ("verdict pass; paragraphs {0}, tables {1}" -f $cj.summary.paragraphs, @($cj.summary.tables).Count)
            } else {
                Bad ("verdict {0}" -f $cj.verdict)
            }
        }
    } else {
        Warn "check_office.py not found; skipping structural check"
    }
}

# ---------------------------------------------------------------- PDF
if (-not $SkipPdf) {
    Write-Host ""
    Write-Host "-- stage 5: DOCX to PDF --" -ForegroundColor Cyan
    if (-not (Test-Path $NodeExe)) { Bad "node not found at $NodeExe"; exit 1 }
    if (-not (Test-Path $LibreOfficeCli)) { Bad "LibreOffice cli not found at $LibreOfficeCli"; exit 1 }
    if (Test-Path $Pdf) { Remove-Item $Pdf -Force }
    & $NodeExe $LibreOfficeCli convert --input $Docx --output $Pdf
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Pdf)) {
        Bad "PDF conversion failed"
        Warn "if the error was 'spawn EPERM', process creation was blocked."
        Warn "run this script in a plain terminal, or widen access for that command."
        exit 1
    }
    Ok ("PDF {0:N0} bytes" -f (Get-Item $Pdf).Length)
}

# ---------------------------------------------------------------- dist
Write-Host ""
Write-Host "-- stage 6: stage deliverables --" -ForegroundColor Cyan
if (-not (Test-Path $DistDir)) { New-Item -ItemType Directory -Path $DistDir | Out-Null }
Copy-Item $Docx $OutDocx -Force
Ok "dist\$(Split-Path -Leaf $OutDocx)"
if ((Test-Path $Pdf) -and -not $SkipPdf) {
    Copy-Item $Pdf $OutPdf -Force
    Ok "dist\$(Split-Path -Leaf $OutPdf)"
}

# ---------------------------------------------------------------- release
if (-not $NoRelease) {
    Write-Host ""
    Write-Host "-- stage 7: GitHub release --" -ForegroundColor Cyan
    if (-not $env:GIT_TOKEN) {
        Warn "no GIT_TOKEN set; skipping release creation"
        Info "set `$env:GIT_USER and `$env:GIT_TOKEN, then re-run without -NoRelease"
    } else {
        $mk = Join-Path (Split-Path -Parent $RepoRoot) "chrome-debug\make_release.py"
        if (Test-Path $mk) {
            $env:PACSP_TOKEN = $env:GIT_TOKEN
            & $MbPy -X utf8 $mk
            Remove-Item Env:\PACSP_TOKEN -ErrorAction SilentlyContinue
        } else {
            Warn "make_release.py not found; skipping"
        }
    }
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host " done" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Info "next, for a DOI: enable the Zenodo integration for this repository at"
Info "  https://zenodo.org/account/settings/github/"
Info "then publish a GitHub release; Zenodo mints the DOI automatically."
