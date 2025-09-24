@echo off
echo ================================================
echo SAT Report Generator - Test Mode (No Security Blocking)
echo ================================================

cd /d "E:\report generator\SERVER"

echo Testing on port 8080 with security disabled...
echo This will allow both IP and domain access for testing.
echo.

python test_no_blocking.py

pause