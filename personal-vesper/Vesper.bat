@echo off
REM ===================================================================
REM  Double-click to start Vesper.
REM
REM  This window IS Vesper -- it listens, thinks and talks. Closing it
REM  stops her. The map opens in your browser a moment after start, and
REM  is served BY this window: the app and the browser page are the same
REM  program, not two ways of doing it.
REM ===================================================================
setlocal
cd /d "%~dp0"
title Vesper

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Vesper is not set up yet.
  echo   Double-click "Install Vesper.bat" first.
  echo.
  pause
  exit /b 1
)

echo.
echo   Starting Vesper. The map will open in your browser shortly.
echo   Close this window to stop her.
echo.

".venv\Scripts\python.exe" -m vesper.launch %*

REM Only reached once she exits. If that was a crash, the message is
REM above -- so hold the window open rather than blinking out of
REM existence with the reason on it.
echo.
pause
