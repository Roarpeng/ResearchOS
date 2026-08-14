#Requires -Version 5.1
<#
.SYNOPSIS
  ResearchOS one-click start: Docker Compose (all services) + Windows TIA Openness CLI ready.

.PARAMETER Mode
  Full    = Docker stack including nginx frontend + gateway + data plane (default)
  Hybrid  = Same as Full (kept for compatibility). Prefer Full.

.PARAMETER HostGateway
  Extra: stop container gateway and run host Gateway so Openness CLI can process .ap19.
  Frontend stays Docker nginx. Use only when you need Windows Openness from Gateway.

.PARAMETER SkipDocker
  Skip Docker Desktop / Compose.

.PARAMETER SkipOpenness
  Skip Openness build and status check.

.PARAMETER Build
  Force docker compose --build for the whole stack (needs Docker Hub DNS).

.PARAMETER NoBuild
  Skip the automatic frontend image rebuild on Full start.

.PARAMETER Profiles
  Extra compose profiles (default includes plc).
#>
[CmdletBinding()]
param(
    [ValidateSet("Full", "Hybrid")]
    [string] $Mode = "Full",

    [switch] $HostGateway,
    [switch] $SkipDocker,
    [switch] $SkipOpenness,
    [switch] $Build,
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

function Rebuild-FrontendImage {
    Write-Step "Rebuild frontend Docker image from frontend/ sources"
    $feDir = Join-Path $Root "frontend"
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        throw "npm not found; cannot build frontend for Docker overlay"
    }

    Write-WarnLine "Host build: npm run build (frontend/)"
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        Push-Location $feDir
        try {
            & npm.cmd run build 2>&1 | ForEach-Object { Write-Host ("    " + $_) }
            if ($LASTEXITCODE -ne 0) {
                throw "npm run build failed (exit $LASTEXITCODE)"
            }
        }
        finally {
            Pop-Location
        }
    }
    finally {
        $ErrorActionPreference = $prev
    }
    $distIndex = Join-Path $feDir "dist\index.html"
    if (-not (Test-Path $distIndex)) {
        throw "frontend/dist/index.html missing after build"
    }

    # Prefer overlay onto existing researchos-frontend (no Hub pull). Fall back to full Dockerfile.
    $hasFe = $false
    try {
        $null = & docker image inspect researchos-frontend:latest 2>$null
        if ($LASTEXITCODE -eq 0) { $hasFe = $true }
    }
    catch { $hasFe = $false }

    Push-Location $Root
    try {
        if ($hasFe) {
            Write-WarnLine "docker build overlay (FROM researchos-frontend:latest) — no Hub required"
            $prev2 = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            try {
                $out = & docker build -f "frontend\Dockerfile.overlay" -t researchos-frontend:latest . 2>&1
                $code = $LASTEXITCODE
                foreach ($line in $out) { Write-Host ("    " + [string]$line) }
                if ($code -ne 0) {
                    throw "frontend overlay build failed (exit $code)"
                }
            }
            finally {
                $ErrorActionPreference = $prev2
            }
        }
        else {
            Write-WarnLine "No local researchos-frontend image; trying full Dockerfile (needs node/nginx bases)"
            Push-Location $ComposeDir
            try {
                Invoke-DockerCompose -ComposeArgs @(
                    "--env-file", $EnvFile, "build", "frontend"
                ) -FailMessage "frontend image build failed"
            }
            finally {
                Pop-Location
            }
        }
        Write-Ok "Frontend image rebuilt from current sources"
    }
    finally {
        Pop-Location
    }
}

function Start-ComposeWithOptionalBuild {
    param(
        [string[]] $BaseArgs,
        [string] $Label
    )
    $wantBuild = $Build -and -not $NoBuild
    if ($wantBuild) {
        Write-WarnLine "Trying compose --build (requires registry DNS)..."
        try {
            Invoke-DockerCompose -ComposeArgs ($BaseArgs + @("--build")) -FailMessage "$Label with --build failed"
            return
        }
        catch {
            Write-WarnLine "Build failed (often auth.docker.io / Hub DNS). Falling back to existing images..."
        }
    }
    Invoke-DockerCompose -ComposeArgs $BaseArgs -FailMessage "$Label failed (no local images? fix DNS then: Start-ResearchOS.cmd Build)"
}

function Start-ComposeFull {
    Write-Step ("Start Docker Compose Full; profiles: " + ($Profiles -join ","))
    # Frontend is a baked nginx image — rebuild from frontend/ so UI matches repo.
    if (-not $NoBuild) {
        Rebuild-FrontendImage
    }
    else {
        Write-WarnLine "Skipped frontend rebuild (-NoBuild)"
    }
    Push-Location $ComposeDir
    try {
        $composeArgs = @("--env-file", $EnvFile)
        foreach ($p in $Profiles) {
            if ($p) { $composeArgs += @("--profile", $p) }
        }
        $composeArgs += @("up", "-d")
        Start-ComposeWithOptionalBuild -BaseArgs $composeArgs -Label "docker compose up"
        Recreate-FrontendContainer
        Write-Ok "Compose started (frontend recreated from current image)"
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
        $composeArgs = @("--env-file", $EnvFile, "up", "-d") + $services
        Start-ComposeWithOptionalBuild -BaseArgs $composeArgs -Label "docker compose up (data)"
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $stopOut = & docker compose --env-file $EnvFile stop gateway frontend 2>&1
            $null = $LASTEXITCODE
            foreach ($line in $stopOut) { Write-Host ("    " + [string]$line) }
        }
        finally {
            $ErrorActionPreference = $prev
        }
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

    Write-Step "Siemens Openness firewall whitelist"
    $whitelistScript = Join-Path $PSScriptRoot "Register-TiaOpennessWhitelist.ps1"
    if (Test-Path -LiteralPath $whitelistScript) {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $whitelistScript -Exe $exe
            $wlCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $prev
        }
        if ($wlCode -eq 0) {
            Write-Ok "Openness firewall whitelist matches current exe (no Siemens Yes/No dialog)"
        }
        else {
            Write-WarnLine "Whitelist not updated (exit $wlCode). Either run scripts\Register-TiaOpennessWhitelist.ps1 as Administrator, or click 'Yes to all' (not Yes) on the Openness prompt once."
        }
    }
    else {
        Write-WarnLine "Whitelist script missing: $whitelistScript"
    }

    $exeUnix = ($exe -replace "\\", "/")
    Set-EnvFileValue "RESEARCHOS_TIA_OPENNESS_EXE" $exeUnix
    # Docker Linux Gateway cannot exec Windows Openness — keep off in .env for compose.
    # HostGateway process gets RESEARCHOS_TIA_OPENNESS=cli via Import-DotEnvToProcess override.
    if ($HostGateway) {
        Set-EnvFileValue "RESEARCHOS_TIA_OPENNESS" "cli"
    }
    else {
        Set-EnvFileValue "RESEARCHOS_TIA_OPENNESS" "off"
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

function Stop-HostAppPids {
    Write-Step "Stop leftover host Gateway/Frontend (ports 8000/5173 for Docker)"
    foreach ($name in @("gateway", "frontend")) {
        $pidFile = Join-Path $RunDir "$name.pid"
        if (-not (Test-Path $pidFile)) { continue }
        $procId = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
        if ($procId -match "^\d+$") {
            $p = Get-Process -Id ([int]$procId) -ErrorAction SilentlyContinue
            if ($p) {
                Write-WarnLine "Stopping host $name PID $procId"
                Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
                Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                    Where-Object { $_.ParentProcessId -eq [int]$procId } |
                    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            }
        }
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    }
}

function Recreate-FrontendContainer {
    param([switch] $HostGatewayOverride)
    Write-Step "Recreate frontend container (stop/rm/up --no-deps; avoid Windows force-recreate hang)"
    Push-Location $ComposeDir
    try {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $files = @("-f", "docker-compose.yml")
            if ($HostGatewayOverride) {
                $override = Join-Path $ComposeDir "docker-compose.hostgateway.yml"
                if (Test-Path $override) { $files += @("-f", $override) }
            }
            $base = @("--env-file", $EnvFile) + $files
            foreach ($line in (& docker compose @base stop frontend 2>&1)) {
                Write-Host ("    " + [string]$line)
            }
            foreach ($line in (& docker compose @base rm -f frontend 2>&1)) {
                Write-Host ("    " + [string]$line)
            }
            # Compose v5 on Windows can hang forever on "Starting"; create then docker start.
            foreach ($line in (& docker compose @base up -d --no-deps --no-build --no-start --pull never frontend 2>&1)) {
                Write-Host ("    " + [string]$line)
            }
            $started = & docker start researchos-frontend-1 2>&1
            foreach ($line in $started) { Write-Host ("    " + [string]$line) }
        }
        finally {
            $ErrorActionPreference = $prev
        }
    }
    finally {
        Pop-Location
    }
}

function Stop-ComposeGatewayKeepFrontend {
    Write-Step "Stop Docker gateway only (host Gateway will own :8000; frontend stays nginx)"
    Push-Location $ComposeDir
    try {
        $prev = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $out = & docker compose --env-file $EnvFile stop gateway 2>&1
            foreach ($line in $out) { Write-Host ("    " + [string]$line) }
            $override = Join-Path $ComposeDir "docker-compose.hostgateway.yml"
            if (Test-Path $override) {
                Write-WarnLine "Recreate frontend so nginx /api reaches host Gateway (gateway:host-gateway)"
                Recreate-FrontendContainer -HostGatewayOverride
            }
        }
        finally {
            $ErrorActionPreference = $prev
        }
    }
    finally {
        Pop-Location
    }
}

function Import-DotEnvToProcess {
    $map = Get-EnvMap
    foreach ($k in $map.Keys) {
        [Environment]::SetEnvironmentVariable($k, [string]$map[$k], "Process")
    }
    # Host Gateway path always needs CLI Openness when used
    $exe = Find-OpennessExe
    if ($exe) {
        [Environment]::SetEnvironmentVariable("RESEARCHOS_TIA_OPENNESS", "cli", "Process")
        [Environment]::SetEnvironmentVariable("RESEARCHOS_TIA_OPENNESS_EXE", $exe, "Process")
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
if ($Mode -eq "Hybrid" -and -not $HostGateway) {
    Write-WarnLine "Hybrid is now an alias of Full (all Docker + nginx FE). Use -HostGateway only for .ap19 Openness."
}
Ensure-EnvFile
Stop-HostAppPids

if (-not $SkipDocker) {
    Ensure-DockerDesktop
    # Always bring up full stack (frontend=nginx). Openness stays on Windows host.
    Start-ComposeFull
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

if ($HostGateway) {
    Stop-ComposeGatewayKeepFrontend
    Start-HostGateway
    Write-Ok "Host Gateway + Docker nginx frontend (Openness CLI enabled on host)"
}
else {
    Write-Ok "Topology: Docker (frontend nginx + gateway + data). Openness = Windows CLI only."
}

Write-Step "Health check"
$gw = "http://localhost:8000/api/v1/health/live"
$fe = "http://localhost:5173/"
if (Wait-Http $gw 120) {
    Write-Ok "Gateway $gw"
}
else {
    Write-WarnLine "Gateway not ready yet: $gw (see Docker logs or .researchos\logs)"
}
if (Wait-Http $fe 60) {
    Write-Ok "Frontend $fe (Docker nginx)"
}
else {
    Write-WarnLine "Frontend not ready yet: $fe"
}

Write-Host ""
Write-Host "---------- URLs ----------" -ForegroundColor White
Write-Host "  Frontend   http://localhost:5173   (Docker nginx)"
Write-Host "  Gateway    http://localhost:8000/api/v1/health/live"
Write-Host "  Neo4j      http://localhost:7474"
Write-Host "  MinIO      http://localhost:9001"
if ($opennessExe) {
    Write-Host "  Openness   $opennessExe"
    Write-Host "             (Windows-only CLI; Linux container cannot run it)"
}
Write-Host ""
Write-Host "Stop: Stop-ResearchOS.cmd  or  .\scripts\Stop-ResearchOS.ps1" -ForegroundColor DarkGray
if (-not $HostGateway) {
    Write-Host "Tip: .ap19 Openness from Gateway → Start-ResearchOS.cmd HostGateway" -ForegroundColor DarkGray
    Write-Host "     (or upload .zap / SimaticML XML; those work fully in Docker Gateway)." -ForegroundColor DarkGray
}
Write-Host "Done." -ForegroundColor Green
