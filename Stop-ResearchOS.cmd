@echo off
setlocal
cd /d "%~dp0"
title ResearchOS Stop
echo.
echo  正在停止 ResearchOS…
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Stop-ResearchOS.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if %ERR% neq 0 (
  echo 停止过程有错误，退出码 %ERR%。
  pause
  exit /b %ERR%
)
echo 按任意键关闭…
pause >nul
endlocal
