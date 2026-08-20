@echo off
REM ===================================================================
REM  Double-click this when Vesper says she can't answer.
REM
REM  It prints what she can actually reach: which keys are set, which
REM  providers are configured, and what happens when each one is asked
REM  a real question. Changes nothing.
REM
REM  Keys are shown with the middle hidden, so this is safe to
REM  screenshot and send.
REM ===================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0_whereami.bat"
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m vesper.launch --doctor

pause
