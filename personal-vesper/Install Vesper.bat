@echo off
REM ===================================================================
REM  Double-click this once. It sets Vesper up in its own folder and
REM  touches nothing else on the laptop.
REM
REM  Everything lands in a .venv beside this file, so uninstalling is
REM  deleting the folder. Nothing is added to PATH, nothing is
REM  registered, no admin rights are needed.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo   Setting up Vesper. First run takes a few minutes.
echo.

REM --- find a Python -------------------------------------------------
REM py.exe is the launcher that ships with python.org installs and is
REM present even when python.exe is not on PATH -- which is the single
REM most common way this goes wrong.
set PY=
where py >nul 2>nul && set PY=py
if "%PY%"=="" ( where python >nul 2>nul && set PY=python )

if "%PY%"=="" (
  echo   Python is not installed.
  echo.
  echo   Get it from https://www.python.org/downloads/
  echo   TICK "Add python.exe to PATH" on the first screen of the installer.
  echo   Then close this window and double-click me again.
  echo.
  pause
  exit /b 1
)

for /f "tokens=2" %%v in ('%PY% --version 2^>^&1') do echo   Found Python %%v

REM --- its own environment -------------------------------------------
if not exist ".venv" (
  echo   Making a private environment...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo.
    echo   Could not create the environment. If Python was only just
    echo   installed, close this window and try again in a new one.
    echo.
    pause
    exit /b 1
  )
)

echo   Installing what Vesper needs. This is the slow part.
echo.
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo   Something failed to install. The line above says which.
  echo   Vesper may still run -- try Vesper.bat and see.
  echo.
  pause
)

REM --- .env, with a real token already in it -------------------------
".venv\Scripts\python.exe" -m vesper.launch --setup

echo.
echo   ================================================
echo    Done. Now double-click  Vesper.bat
echo   ================================================
echo.
pause
