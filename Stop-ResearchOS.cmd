@echo off
setlocal
cd /d "%~dp0"
title ResearchOS Stop
echo.
echo  Stopping ResearchOS...
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Stop-ResearchOS.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if %ERR% neq 0 (
  echo Stop reported errors, exit code %ERR%.
  pause
  exit /b %ERR%
)
echo Press any key to close...
pause >nul
endlocal
