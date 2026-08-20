@echo off
REM ===================================================================
REM  Shared by Vesper.bat and "Tune up Vesper.bat".
REM
REM  Called when the folder we were double-clicked in has no .venv. The
REM  overwhelmingly likely reason is not "never installed" -- it is a
REM  fresh unzip sitting in Downloads while the real install, with the
REM  .venv and the .env full of keys, is somewhere else entirely.
REM  Saying "not installed" there sends someone off to reinstall on top
REM  of a folder that will never be the one they run.
REM
REM  So: go and find it, and say where it is.
REM ===================================================================
setlocal enabledelayedexpansion
set "FOUND="
for %%R in ("%USERPROFILE%\Documents" "%USERPROFILE%\Desktop" "%USERPROFILE%\Downloads" "%USERPROFILE%") do (
  if not defined FOUND (
    if exist "%%~R" (
      for /f "delims=" %%P in ('dir /s /b "%%~R\python.exe" 2^>nul ^| findstr /i "\\.venv\\Scripts\\python.exe"') do (
        if not defined FOUND (
          set "CAND=%%~dpP"
          set "CAND=!CAND:\.venv\Scripts\=!"
          if exist "!CAND!\vesper\launch.py" set "FOUND=!CAND!"
        )
      )
    )
  )
)

echo.
if defined FOUND (
  echo   This folder is a fresh copy of the files -- it has no .venv, so
  echo   there is nothing here to run.
  echo.
  echo   Your actual install is here:
  echo.
  echo       !FOUND!
  echo.
  echo   Copy the files from THIS folder into that one, replacing when
  echo   asked, then run it from there. Your settings and your map stay
  echo   where they are -- they are not in the download.
  echo.
  echo   One line that does it, in PowerShell from this folder:
  echo.
  echo       Copy-Item .\* "!FOUND!" -Recurse -Force
  echo.
) else (
  echo   Vesper isn't installed in this folder, and I couldn't find an
  echo   install anywhere else under your user folder either.
  echo.
  echo   If this is your first time: double-click "Install Vesper.bat".
  echo.
)
endlocal
