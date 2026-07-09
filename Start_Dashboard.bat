@echo off
rem Trendkept — double-click launcher for the dashboard (Windows).
rem Opens your browser at the dashboard, then starts the engine.
rem Keep this window open while you use the dashboard; close it (or press
rem Ctrl+C) when you're done.
cd /d "%~dp0"
start "" http://127.0.0.1:8181
echo Starting the Trendkept dashboard at http://127.0.0.1:8181 ...
echo (Keep this window open. Close it to stop the dashboard.)
python -m trendkept.web
pause
