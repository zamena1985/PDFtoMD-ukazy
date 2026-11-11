@echo off
cd /d "%~dp0"
where py >nul 2>&1 && (py -3 -X utf8 start.py) || (python -X utf8 start.py)
if errorlevel 1 (
  echo.
  echo Python not found or script failed. See GUIDE: doc\guide_ru.pdf
)
pause
