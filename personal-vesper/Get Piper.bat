@echo off
REM ===================================================================
REM  Double-click for a better voice.
REM
REM  Downloads Piper (~20 MB), finds or downloads the en_GB Alan voice
REM  (~60 MB), and writes both paths into .env. No PATH changes, so no
REM  "close the window and open a new one" step.
REM
REM  Your old .env is kept as .env.bak5. To go back to the Windows
REM  voice at any time, set TTS_BACKEND=windows in .env.
REM ===================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0_whereami.bat"
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m vesper.launch --piper

pause
