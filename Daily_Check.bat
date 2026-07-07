@echo off
rem Trendrail — the daily 15-minute routine, double-clickable (Windows).
rem Shows your paper account, then a DRY RUN of position management
rem (what the rules would do today — it changes nothing by itself).
cd /d "%~dp0"
echo ============================================
echo  Trendrail daily check  (paper account)
echo ============================================
echo.
echo --- Account and open positions ---
python -m trendrail.cli account
echo.
echo --- What the rules say about open positions (DRY RUN) ---
python -m trendrail.cli manage
echo.
echo ============================================
echo  To ACT on the above (paper account):
echo    python -m trendrail.cli manage --confirm
echo  For the watchlist scan, use Start_Dashboard.bat
echo  Then log one row in your paper_log.md
echo ============================================
pause
