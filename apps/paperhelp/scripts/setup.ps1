# PaperHelp one-time setup script (Windows PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=== PaperHelp Setup ===" -ForegroundColor Cyan

function Ensure-CargoBinOnUserPath {
    $cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
    if (-not (Test-Path (Join-Path $cargoBin "cargo.exe"))) {
        Write-Host "cargo.exe not found at $cargoBin — install Rust via rustup first." -ForegroundColor Yellow
        return
    }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($null -eq $userPath) { $userPath = "" }

    $normalizedCargo = $cargoBin.TrimEnd("\")
    $alreadyPresent = ($userPath -split ";" | Where-Object { $_.Trim().TrimEnd("\") -ieq $normalizedCargo }).Count -gt 0

    if (-not $alreadyPresent) {
        $newUserPath = if ($userPath.Trim()) { "$userPath;$cargoBin" } else { $cargoBin }
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
        Write-Host "Added $cargoBin to user PATH (new terminals will pick this up automatically)." -ForegroundColor Green
        $userPath = $newUserPath
    } else {
        Write-Host "OK user PATH already includes .cargo\bin" -ForegroundColor Green
    }

    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($null -eq $machinePath) { $machinePath = "" }
    $env:Path = "$cargoBin;$userPath;$machinePath"
}

function Require-Command($name, $installHint) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        Write-Host "Missing: $name" -ForegroundColor Red
        Write-Host $installHint
        exit 1
    }
    $v = & $name --version 2>$null
    if (-not $v) { $v = & $name -v 2>$null }
    Write-Host "OK $name : $v" -ForegroundColor Green
}

Require-Command node "Install Node.js 20+ from https://nodejs.org/"
Require-Command pnpm "Run: npm install -g pnpm"

Ensure-CargoBinOnUserPath
Require-Command rustc "Install Rust from https://rustup.rs/ (required for Tauri)"
Require-Command cargo "Ensure Rust toolchain is installed via rustup"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "`nInstalling dependencies..." -ForegroundColor Cyan
pnpm install

Write-Host "`nChecking PDF export browser..." -ForegroundColor Cyan
$chromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$hasChrome = $false
foreach ($p in $chromePaths) {
    if (Test-Path $p) { $hasChrome = $true; Write-Host "OK System Chrome: $p" -ForegroundColor Green; break }
}
if (-not $hasChrome) {
    Write-Host "System Chrome not found — downloading Puppeteer Chromium (~150MB)..." -ForegroundColor Yellow
    Push-Location packages/export
    pnpm exec puppeteer browsers install chrome@stable
    Pop-Location
} else {
    Write-Host "PDF export will use system Chrome (no Puppeteer download needed)." -ForegroundColor Green
}

Write-Host "`nBuilding all packages..." -ForegroundColor Cyan
pnpm build

Write-Host "`nChecking Rust/Tauri backend..." -ForegroundColor Cyan
Push-Location apps/desktop/src-tauri
cargo check
Pop-Location

Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host "Start dev:  pnpm dev:desktop"
Write-Host "Build app:  pnpm build:desktop"
Write-Host "From apps/desktop: pnpm tauri dev"
