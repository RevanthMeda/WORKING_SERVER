@echo off
echo ================================================
echo SAT Report Generator - Port 8080 (Confirmed Available)
echo ================================================

cd /d "E:\report generator\SERVER"

set PORT=8080
set FLASK_ENV=production
set DEBUG=False
set ALLOWED_DOMAINS=automation-reports.mobilehmi.org
set SERVER_IP=172.16.18.21
set BLOCK_IP_ACCESS=True

echo Using available port 8080...
echo.

python deploy.py

pause