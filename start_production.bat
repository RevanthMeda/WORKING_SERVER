@echo off
REM Production startup script for Windows Server
REM SAT Report Generator - Domain Security Enabled

echo ================================================
echo SAT Report Generator - Production Deployment
echo Server: 172.16.18.21
echo Domain: automation-reports.mobilehmi.org
echo Port: 8443 (HTTPS with SSL)
echo ================================================

REM Set production environment variables
set FLASK_ENV=production
set DEBUG=False
set PORT=8443
set ALLOWED_DOMAINS=automation-reports.mobilehmi.org
set SERVER_IP=172.16.18.21
set BLOCK_IP_ACCESS=True

REM Email configuration (update with your details)
set SMTP_SERVER=smtp.gmail.com
set SMTP_PORT=587
set SMTP_USERNAME=meda.revanth@gmail.com
set SMTP_PASSWORD=rleg tbhv rwvb kdus
set DEFAULT_SENDER=meda.revanth@gmail.com
set ENABLE_EMAIL_NOTIFICATIONS=True

REM Security settings
set SECRET_KEY=your-production-secret-key-change-this-immediately
set SESSION_COOKIE_SECURE=True
set WTF_CSRF_ENABLED=True
set PERMANENT_SESSION_LIFETIME=7200

echo Environment variables set for production...
echo.

echo HTTPS enabled on port 8443 - No admin privileges needed!

echo.
echo Starting SAT Report Generator in Production Mode...
echo Direct Flask access - Simple deployment!
echo Access: https://automation-reports.mobilehmi.org:8443
echo.

REM Change to the project directory
cd /d "E:\report generator\SERVER"
if %errorLevel% != 0 (
    echo ERROR: Could not find project directory!
    echo Please make sure the path is correct: E:\report generator\SERVER
    pause
    exit /b 1
)

echo Changed to project directory: %CD%
echo.

echo ✓ Starting Flask with HTTPS on port 8443...

REM Start the application
echo Starting Flask on port 8443...
python app.py

if %errorLevel% != 0 (
    echo.
    echo ❌ Flask failed to start!
    echo Common issues:
    echo - Port 443 already in use
    echo - Administrator privileges needed
    echo - Firewall blocking port 443
    echo.
)

pause