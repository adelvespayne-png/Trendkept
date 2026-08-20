@echo off
REM ===================================================================
REM  Double-click this if Vesper feels thin: barely answering, or a map
REM  with nothing under the branches.
REM
REM  It does two things, and neither of them loses anything:
REM
REM    1. Fills the map in. Your own notes stay exactly where they are;
REM       the old map is kept beside it as map.json.bak.
REM    2. Puts a proper model at the top of the list in .env, if the one
REM       there now is a small one. The old .env is kept as .env.bak3.
REM
REM  Safe to run twice. Safe to run on a fresh install.
REM ===================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   Vesper isn't installed in this folder yet.
  echo   Double-click "Install Vesper.bat" first.
  echo.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m vesper.launch --tuneup

pause
