#Requires -Version 5.1
<#
.SYNOPSIS
  ResearchOS one-click start: Docker Compose + Windows TIA Openness.

.PARAMETER Mode
  Full    = full Docker stack + Openness CLI ready
  Hybrid  = Docker data-plane only + host Gateway/Frontend + Openness (.ap19)

.PARAMETER SkipDocker
  Skip Docker Desktop / Compose.

.PARAMETER SkipOpenness
  Skip Openness build and status check.

.PARAMETER NoBuild
  Do not pass --build to compose.

.PARAMETER Profiles
  Extra compose profiles (default includes plc).
#>
[CmdletBinding()]
param(
    [ValidateSet("Full", "Hybrid")]
    [string] $Mode = "Full",

    [switch] $SkipDocker,
    [switch] $SkipOpenness,
    [switch] $NoBuild,
    [string[]] $Profiles = @("plc"),
    [int] $DockerWaitSeconds = 120
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunDir = Join-Path $Root ".researchos\run"
$LogDir = Join-Path $Root ".researchos\logs"
$EnvFile = Join-Path $Root "deploy\env\.env"
$EnvExample = Join-Path $Root "deploy\env\.env.example"
$ComposeDir = Join-Path $Root "deploy\compose"
$OpennessProj = Join-Path $Root "tools\industrial-mcp\tia-openness\TiaOpenness.sln"
$OpennessExeCandidates = @(
    (Join-Path $Root "tools\industrial-mcp\tia-openness\src\TiaOpenness.Server\bin\Release\net481\TiaOpenness.Server.exe"),
    (Join-Path $Root "tools\industrial-mcp\tia-openness\src\TiaOpenness.Server\bin\Debug\net481\TiaOpenness.Server.exe")
)

New-Item -ItemType Directory -Force -Path $RunDir, $LogDir | Out-Null

function Write-Step([string] $Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string] $Message) {
    Write-Host "    OK  $Message" -ForegroundColor Green
}

function Write-WarnLine([string] $Message) {
    Write-Host "    WARN  $Message" -ForegroundColor Yellow
}

function Ensure-EnvFile {
    if (-not (Test-Path $EnvFile)) {
        if (-not (Test-Path $EnvExample)) {
            throw "Missing $EnvExample"
        }
        Copy-Item $EnvExample $EnvFile
        Write-WarnLine "Created deploy\env\.env from example - edit change_me_* secrets"
    }
    else {
        Write-Ok "Using $EnvFile"
    }
}

function Get-EnvMap {
    $map = @{}
    Get-Content -LiteralPath $EnvFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $i = $line.IndexOf("=")
        if ($i -lt 1) { return }
        $k = $line.Substring(0, $i).Trim()
        $v = $line.Substring($i + 1).Trim()
        if (($v.StartsWith('"') -and $v.EndsWith('"')) -or ($v.StartsWith("'") -and $v.EndsWith("'"))) {
            $v = $v.Substring(1, $v.Length - 2)
        }
        $map[$k] = $v
    }
    return $map
}

function Set-EnvFileValue([string] $Key, [string] $Value) {
    $lines = Get-Content -LiteralPath $EnvFile -Encoding UTF8
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*#") { $line; continue }
        if ($line -match "^\s*$Key\s*=") {
            $found = $true
            "$Key=$Value"
        }
        else {
            $line
        }
    }
    if (-not $found) {
        $out += "$Key=$Value"
    }
    Set-Content -LiteralPath $EnvFile -Value $out -Encoding UTF8
}

function Ensure-DockerDesktop {
    Write-Step "Check Docker Engine"
    $dockerOk = $false
    try {
        docker info 1>$null 2>$null
        if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
    }
    catch { }

    if ($dockerOk) {
        Write-Ok "Docker Engine ready"
        return
    }

    $desktop = @(
        "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $desktop) {
        throw "Docker Desktop not found. Install: https://www.docker.com/products/docker-desktop/"
    }

    Write-WarnLine "Starting Docker Desktop..."
    Start-Process -FilePath $desktop | Out-Null

    $deadline = (Get-Date).AddSeconds($DockerWaitSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        try {
            docker info 1>$null 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "Docker Engine ready"
                return
            }
        }
        catch { }
        Write-Host "    ...waiting for Docker Engine" -ForegroundColor DarkGray
    }
    throw "Docker Engine timeout (${DockerWaitSeconds}s). Open Docker Desktop and retry."
}


function Invoke-DockerCompose {
    param([string[]] $ComposeArgs, [string] $FailMessage)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & docker compose @ComposeArgs 2>&1
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prev
    }
    foreach ($line in $output) {
        Write-Host ("    " + [string]$line)
    }
    if ($code -ne 0) {
        throw "$FailMessage (exit $code)"
    }
}

function Start-ComposeFull {
    Write-Step ("Start Docker Compose Full; profiles: " + ($Profiles -join ","))
    Push-Location $ComposeDir
    try {
        $composeArgs = @("--env-file", $EnvFile)
        foreach ($p in $Profiles) {
            if ($p) { $composeArgs += @("--profile", $p) }
        }
        $composeArgs += @("up", "-d")
        if (-not $NoBuild) { $composeArgs += "--build" }
        Invoke-DockerCompose -ComposeArgs $composeArgs -FailMessage "docker compose up failed"
        Write-Ok "Compose started"
    }
    finally {
        Pop-Location
    }
}

function Start-ComposeDataPlane {
    Write-Step "Start Docker data-plane (Hybrid: no gateway/frontend containers)"
    Push-Location $ComposeDir
    try {
        $services = @("postgres", "redis", "minio", "qdrant", "neo4j", "litellm")
        $composeArgs = @("--env-file", $EnvFile, "up", "-d")
        if (-not $NoBuild) { $composeArgs += "--build" }
        $composeArgs += $services
        Invoke-DockerCompose -ComposeArgs $composeArgs -FailMessage "docker compose up (data) failed"
        $stopOut = & docker compose --env-file $EnvFile stop gateway frontend 2>&1
        $null = $LASTEXITCODE
        foreach ($line in $stopOut) { Write-Host ("    " + $line) }
        Write-Ok "Data-plane up; stopped container gateway/frontend if present"
    }
    finally {
        Pop-Location
    }
}

function Find-OpennessExe {
    foreach ($c in $OpennessExeCandidates) {
        if (Test-Path $c) { return $c }
    }
    $override = (Get-EnvMap)["RESEARCHOS_TIA_OPENNESS_EXE"]
    if ($override -and (Test-Path $override)) { return $override }
    return $null
}

function Ensure-Openness {
    Write-Step "Prepare Windows TIA Openness"
    if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
        throw "dotnet not found. Install .NET 8 SDK + .NET Framework 4.8.1 targeting pack."
    }
    if (-not (Test-Path $OpennessProj)) {
        throw "Openness solution missing: $OpennessProj"
    }

    $exe = Find-OpennessExe
    if (-not $exe) {
        Write-WarnLine "Building Openness Release..."
        & dotnet build $OpennessProj -c Release
        if ($LASTEXITCODE -ne 0) { throw "Openness build failed" }
        $exe = Find-OpennessExe
        if (-not $exe) { throw "Build finished but TiaOpenness.Server.exe not found" }
    }
    else {
        Write-Ok "Found $exe"
    }

    $exeUnix = ($exe -replace "\\", "/")
    Set-EnvFileValue "RESEARCHOS_TIA_OPENNESS_EXE" $exeUnix
    if ($Mode -eq "Hybrid") {
        Set-EnvFileValue "RESEARCHOS_TIA_OPENNESS" "cli"
    }

    Write-Step "Openness CLI status"
    $statusLog = Join-Path $LogDir "openness-status.json"
    $errLog = Join-Path $LogDir "openness-status.err.log"
    $proc = Start-Process -FilePath $exe -ArgumentList @("--cli", "status") `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $statusLog `
        -RedirectStandardError $errLog
    if (Test-Path $statusLog) {
        Get-Content -LiteralPath $statusLog -Raw -ErrorAction SilentlyContinue | Write-Host
    }
    if ($proc.ExitCode -ne 0) {
        Write-WarnLine "status exit $($proc.ExitCode) (license / Openness group / Portal). EXE is ready."
    }
    else {
        Write-Ok "Openness CLI responded"
    }

    @{
        exe       = $exe
        readyAt   = (Get-Date).ToString("o")
        mode      = $Mode
        statusLog = $statusLog
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RunDir "openness.json") -Encoding UTF8

    return $exe
}

function Import-DotEnvToProcess {
    $map = Get-EnvMap
    foreach ($k in $map.Keys) {
        [Environment]::SetEnvironmentVariable($k, [string]$map[$k], "Process")
    }
    if ($Mode -eq "Hybrid") {
        $exe = Find-OpennessExe
        if ($exe) {
            [Environment]::SetEnvironmentVariable("RESEARCHOS_TIA_OPENNESS", "cli", "Process")
            [Environment]::SetEnvironmentVariable("RESEARCHOS_TIA_OPENNESS_EXE", $exe, "Process")
        }
    }
}

function Start-HostGateway {
    Write-Step "Start host Gateway (Hybrid)"
    Import-DotEnvToProcess
    $py = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) {
        throw "Missing .venv\Scripts\python.exe - create venv and install deps first."
    }
    $gwLog = Join-Path $LogDir "gateway.out.log"
    $gwErr = Join-Path $LogDir "gateway.err.log"
    $uvicornArgs = @(
        "-m", "uvicorn", "gateway.app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000"
    )
    $proc = Start-Process -FilePath $py -ArgumentList $uvicornArgs `
        -WorkingDirectory $Root `
        -WindowStyle Hidden `
        -RedirectStandardOutput $gwLog `
        -RedirectStandardError $gwErr `
        -PassThru
    $proc.Id | Set-Content -LiteralPath (Join-Path $RunDir "gateway.pid") -Encoding ascii
    Write-Ok "Gateway PID $($proc.Id)  log $gwLog"
}

function Start-HostFrontend {
    Write-Step "Start host Frontend (Hybrid)"
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        Write-WarnLine "npm not found; skip frontend. Later: cd frontend; npm run dev"
        return
    }
    $feLog = Join-Path $LogDir "frontend.out.log"
    $feErr = Join-Path $LogDir "frontend.err.log"
    $feDir = Join-Path $Root "frontend"
    $proc = Start-Process -FilePath $npm.Source -ArgumentList @("run", "dev", "--", "--host", "0.0.0.0") `
        -WorkingDirectory $feDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $feLog `
        -RedirectStandardError $feErr `
        -PassThru
    $proc.Id | Set-Content -LiteralPath (Join-Path $RunDir "frontend.pid") -Encoding ascii
    Write-Ok "Frontend PID $($proc.Id)  log $feLog"
}

function Wait-Http([string] $Url, [int] $Seconds = 90) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        }
        catch { }
        Start-Sleep -Seconds 2
    }
    return $false
}

Write-Host "ResearchOS one-click start  Mode=$Mode  Root=$Root" -ForegroundColor White
Ensure-EnvFile

if (-not $SkipDocker) {
    Ensure-DockerDesktop
    if ($Mode -eq "Hybrid") {
        Start-ComposeDataPlane
    }
    else {
        Start-ComposeFull
    }
}
else {
    Write-WarnLine "Skipped Docker"
}

$opennessExe = $null
if (-not $SkipOpenness) {
    $opennessExe = Ensure-Openness
}
else {
    Write-WarnLine "Skipped Openness"
}

if ($Mode -eq "Hybrid") {
    Start-HostGateway
    Start-HostFrontend
}

Write-Step "Health check"
$gw = "http://localhost:8000/api/v1/health/live"
if (Wait-Http $gw 120) {
    Write-Ok "Gateway $gw"
}
else {
    Write-WarnLine "Gateway not ready yet: $gw (see Docker logs or .researchos\logs)"
}

Write-Host ""
Write-Host "---------- URLs ----------" -ForegroundColor White
Write-Host "  Frontend   http://localhost:5173"
Write-Host "  Gateway    http://localhost:8000/api/v1/health/live"
Write-Host "  Neo4j      http://localhost:7474"
Write-Host "  MinIO      http://localhost:9001"
if ($opennessExe) {
    Write-Host "  Openness   $opennessExe"
    Write-Host "             (on-demand CLI; Hybrid host Gateway uses RESEARCHOS_TIA_OPENNESS=cli)"
}
Write-Host ""
Write-Host "Stop: Stop-ResearchOS.cmd  or  .\scripts\Stop-ResearchOS.ps1" -ForegroundColor DarkGray
if ($Mode -eq "Full") {
    Write-Host "Tip: for .ap19 ingest / writeback, restart with -Mode Hybrid." -ForegroundColor DarkGray
}
Write-Host "Done." -ForegroundColor Green