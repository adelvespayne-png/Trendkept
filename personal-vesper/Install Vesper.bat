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
REM Two ways Python arrives on Windows now, and they behave differently:
REM
REM   * the standalone .exe installer, which puts python.exe on PATH if you
REM     ticked the box, and always installs the py launcher;
REM   * the Python install manager (MSIX), python.org's newer default, which
REM     provides `py` and deliberately does NOT touch PATH.
REM
REM Being FOUND is not the same as being USABLE: the install manager ships
REM `py` before any runtime exists, so `where py` succeeds while `py
REM --version` still fails. Check that it actually runs.
set PY=
call :try py
if "%PY%"=="" call :try python
if "%PY%"=="" call :try python3

if "%PY%"=="" (
  echo.
  echo   No working Python found.
  echo.
  echo   Go to https://www.python.org/downloads/
  echo.
  echo   The big yellow button installs the Python INSTALL MANAGER. That
  echo   works, but you must then run this once to get an actual Python:
  echo.
  echo       py install 3.14
  echo.
  echo   Simpler: use the smaller link on that page that says
  echo   "Or get the standalone installer", and TICK
  echo   "Add python.exe to PATH" on the first screen.
  echo.
  echo   Either way, close this window and double-click me again after.
  echo.
  pause
  exit /b 1
)

for /f "tokens=2" %%v in ('%PY% --version 2^>^&1') do echo   Found Python %%v
goto :found

:try
where %1 >nul 2>nul || exit /b
REM It exists. Does it answer?
%1 --version >nul 2>nul || exit /b
set PY=%1
exit /b

:found

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
