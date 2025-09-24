@echo off
echo ================================================
echo SAT Report Generator - IIS Integration Setup
echo ================================================

cd /d "E:\report generator\SERVER"

echo Starting local Flask application for IIS integration...
echo.
echo Configuration:
echo - Local Flask app: http://127.0.0.1:8080
echo - IIS frontend: https://automation-reports.mobilehmi.org:443
echo - Mode: Iframe embedding (security adjusted)
echo.

echo Starting Flask application...
python run_local_https.py

pause