@echo off
echo ====== DEBUG STARTUP ======
echo Current directory: %CD%
echo.

echo Changing to project directory...
cd /d "E:\report generator\SERVER"
echo New directory: %CD%
echo.

echo Checking if app.py exists...
if exist app.py (
    echo ✅ Found app.py
) else (
    echo ❌ app.py NOT FOUND!
    echo Files in current directory:
    dir *.py
)
echo.

echo Checking Python...
python --version
echo.

echo Environment variables:
echo PORT=%PORT%
echo FLASK_ENV=%FLASK_ENV%
echo.

echo Press any key to continue with Flask startup...
pause

echo Starting Flask...
python app.py

echo.
echo Flask stopped. Press any key to close...
pause