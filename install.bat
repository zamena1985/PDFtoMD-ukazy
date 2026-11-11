@echo off
cd /d "%~dp0"
echo Installing PyMuPDF (internet needed once)...
where py >nul 2>&1 && (py -3 -m pip install -r requirements.txt) || (python -m pip install -r requirements.txt)
if errorlevel 1 (
  echo.
  echo Install failed. Is Python installed with "Add python.exe to PATH"? See doc\guide_ru.pdf
) else (
  echo.
  echo Done. Now run start.bat
)
pause
