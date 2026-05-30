# PaperHelp one-time setup script (Windows PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=== PaperHelp Setup ===" -ForegroundColor Cyan

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
Require-Command rustc "Install Rust from https://rustup.rs/ (required for Tauri)"

$env:Path = "$env:USERPROFILE\.cargo\bin;" + $env:Path
Require-Command cargo "Ensure Rust toolchain is installed via rustup"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "`nInstalling dependencies..." -ForegroundColor Cyan
pnpm install

Write-Host "`nInstalling Puppeteer Chromium (PDF export, ~150MB)..." -ForegroundColor Cyan
Push-Location packages/export
pnpm exec puppeteer browsers install chrome
Pop-Location

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
