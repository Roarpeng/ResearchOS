@echo off
setlocal
cd /d "%~dp0"
title ResearchOS Start
echo.
echo  ResearchOS one-click start
echo  Topology: Docker for everything; Openness CLI stays on Windows.
echo  Usage:
echo    Start-ResearchOS.cmd              Full Docker (nginx FE + gateway + data)
echo    Start-ResearchOS.cmd HostGateway  Docker FE/data + host Gateway for .ap19 Openness
echo    Start-ResearchOS.cmd Build        Also rebuild ALL images (needs Docker Hub DNS)
echo.

set "MODE=Full"
set "EXTRA="
if /I "%~1"=="Hybrid" set "MODE=Hybrid"
if /I "%~1"=="hybrid" set "MODE=Hybrid"
if /I "%~1"=="-Hybrid" set "MODE=Hybrid"
if /I "%~1"=="HostGateway" set "EXTRA=-HostGateway"
if /I "%~1"=="hostgateway" set "EXTRA=-HostGateway"
if /I "%~1"=="-HostGateway" set "EXTRA=-HostGateway"
if /I "%~1"=="Build" set "EXTRA=-Build"
if /I "%~1"=="build" set "EXTRA=-Build"
if /I "%~1"=="-Build" set "EXTRA=-Build"
if /I "%~2"=="Build" set "EXTRA=%EXTRA% -Build"
if /I "%~2"=="build" set "EXTRA=%EXTRA% -Build"
if /I "%~2"=="-Build" set "EXTRA=%EXTRA% -Build"
if /I "%~2"=="HostGateway" set "EXTRA=%EXTRA% -HostGateway"
if /I "%~2"=="hostgateway" set "EXTRA=%EXTRA% -HostGateway"
if /I "%~2"=="-HostGateway" set "EXTRA=%EXTRA% -HostGateway"
if /I "%~2"=="Hybrid" set "MODE=Hybrid"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Start-ResearchOS.ps1" -Mode "%MODE%" %EXTRA%
set ERR=%ERRORLEVEL%
echo.
if %ERR% neq 0 (
  echo Start failed, exit code %ERR%.
  pause
  exit /b %ERR%
)
echo Press any key to close this window. Services keep running in the background.
pause >nul
endlocal
