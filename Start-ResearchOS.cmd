@echo off
setlocal
cd /d "%~dp0"
title ResearchOS Start
echo.
echo  ResearchOS 一键启动
echo  用法:
echo    Start-ResearchOS.cmd           全栈 Docker + Openness 就绪
echo    Start-ResearchOS.cmd Hybrid    数据面 Docker + 本机 Gateway/FE + Openness
echo.

set "MODE=Full"
if /I "%~1"=="Hybrid" set "MODE=Hybrid"
if /I "%~1"=="hybrid" set "MODE=Hybrid"
if /I "%~1"=="-Hybrid" set "MODE=Hybrid"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Start-ResearchOS.ps1" -Mode "%MODE%"
set ERR=%ERRORLEVEL%
echo.
if %ERR% neq 0 (
  echo 启动失败，退出码 %ERR%。
  pause
  exit /b %ERR%
)
echo 按任意键关闭此窗口（服务继续在后台运行）…
pause >nul
endlocal
