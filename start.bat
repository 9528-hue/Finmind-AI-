@echo off
setlocal
title FINMIND AI Launcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
if errorlevel 1 (
  echo.
  echo FINMIND AI could not start. Review the error above.
  pause
)
endlocal
