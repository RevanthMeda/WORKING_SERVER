#!/usr/bin/env python3
"""
Test deployment script - NO domain blocking
Use this to test if the application works on port 8080
"""

import os
import sys
from config import config
from app import create_app

def setup_test_environment():
    """Set up test environment - domain blocking DISABLED"""
    
    env_vars = {
        'FLASK_ENV': 'production',
        'DEBUG': 'False',
        'PORT': '8080',
        'ALLOWED_DOMAINS': 'automation-reports.mobilehmi.org',
        'SERVER_IP': '172.16.18.21',
        'BLOCK_IP_ACCESS': 'False',  # DISABLED for testing
        'SECRET_KEY': 'test-secret-key',
        
        # Email configuration
        'SMTP_SERVER': 'smtp.gmail.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'meda.revanth@gmail.com',
        'SMTP_PASSWORD': 'rleg tbhv rwvb kdus',
        'DEFAULT_SENDER': 'meda.revanth@gmail.com',
        'ENABLE_EMAIL_NOTIFICATIONS': 'True',
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    print("✅ Test environment configured (domain blocking DISABLED)")

def main():
    """Test deployment - no security blocking"""
    print("🧪 SAT Report Generator - TEST MODE")
    print("=" * 50)
    print("Port: 8080")
    print("Domain blocking: DISABLED (for testing)")
    print("=" * 50)
    
    setup_test_environment()
    
    # Create Flask app
    app = create_app('production')
    
    print(f"🌐 Server starting on port: {app.config.get('PORT')}")
    print(f"🔓 Domain blocking: {app.config.get('BLOCK_IP_ACCESS')}")
    print()
    print("TEST URLS:")
    print("✅ http://172.16.18.21:8080 (should work)")
    print("✅ http://automation-reports.mobilehmi.org:8080 (should work)")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Start server
    try:
        app.run(
            host='0.0.0.0',
            port=8080,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except Exception as e:
        print(f"❌ Server error: {e}")

if __name__ == '__main__':
    main()