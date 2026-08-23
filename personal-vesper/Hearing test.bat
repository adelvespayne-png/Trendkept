@echo off
REM ===================================================================
REM  Double-click this if she does not hear you well.
REM
REM  It asks you to say one sentence three times, then reports TWO
REM  things separately:
REM
REM    * how loud you arrive  -- that is the microphone
REM    * what it made of it   -- that is the software
REM
REM  "It doesn't hear me" is two different problems with two different
REM  fixes, and they look identical from the outside. This tells them
REM  apart and says which dial to turn.
REM
REM  Changes nothing.
REM ===================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  call "%~dp0_whereami.bat"
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m vesper.sensors.stt --hearing

pause
