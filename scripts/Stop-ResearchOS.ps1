#Requires -Version 5.1
<#
.SYNOPSIS
  Stop ResearchOS one-click processes and Docker Compose.

.PARAMETER KeepDocker
  Only stop host Gateway/Frontend; leave compose running.

.PARAMETER RemoveVolumes
  compose down -v (destructive).
#>
[CmdletBinding()]
param(
    [switch] $KeepDocker,
    [switch] $RemoveVolumes
)

$ErrorActionPreference = "Continue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RunDir = Join-Path $Root ".researchos\run"
$EnvFile = Join-Path $Root "deploy\env\.env"
$ComposeDir = Join-Path $Root "deploy\compose"

function Stop-PidFile([string] $Name) {
    $pidFile = Join-Path $RunDir "$Name.pid"
    if (-not (Test-Path $pidFile)) { return }
    $procId = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($procId -match "^\d+$") {
        $p = Get-Process -Id ([int]$procId) -ErrorAction SilentlyContinue
        if ($p) {
            Write-Host "==> Stop $Name PID $procId" -ForegroundColor Cyan
            Stop-Process -Id ([int]$procId) -Force -ErrorAction SilentlyContinue
            Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object { $_.ParentProcessId -eq [int]$procId } |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

Write-Host "ResearchOS stop" -ForegroundColor White

Stop-PidFile "frontend"
Stop-PidFile "gateway"

foreach ($port in 8000, 5173) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            $ow = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
            if ($ow -and $ow.ProcessName -match "python|node|uvicorn") {
                Write-Host "==> Free port $port (PID $($ow.Id) $($ow.ProcessName))" -ForegroundColor Cyan
                Stop-Process -Id $ow.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch { }
}

if (-not $KeepDocker) {
    if (Test-Path $ComposeDir) {
        Write-Host "==> docker compose down" -ForegroundColor Cyan
        Push-Location $ComposeDir
        try {
            $composeArgs = @()
            if (Test-Path $EnvFile) { $composeArgs += @("--env-file", $EnvFile) }
            $composeArgs += "down"
            if ($RemoveVolumes) { $composeArgs += "-v" }
            & docker compose @composeArgs 2>&1 | ForEach-Object { Write-Host $_ }
        }
        finally {
            Pop-Location
        }
    }
}
else {
    Write-Host "==> Keeping Docker stack (--KeepDocker)" -ForegroundColor DarkGray
}

Remove-Item -LiteralPath (Join-Path $RunDir "openness.json") -Force -ErrorAction SilentlyContinue
Write-Host "Done." -ForegroundColor Green