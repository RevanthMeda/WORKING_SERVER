@echo off
echo ================================================
echo SAT Report Generator - Port 8080 Deployment
echo ================================================

REM Navigate to the correct directory
cd /d "E:\report generator\SERVER"

REM Set environment variables
set PORT=8080
set FLASK_ENV=production
set DEBUG=False
set ALLOWED_DOMAINS=automation-reports.mobilehmi.org
set SERVER_IP=172.16.18.21
set BLOCK_IP_ACCESS=True

echo Starting on port 8080 (no administrator required)...
echo.

python deploy.py

pause