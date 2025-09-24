#!/usr/bin/env python3
"""
Production deployment script for SAT Report Generator
Run this on your server (172.16.18.21) for domain-only access on port 80
"""

import os
import sys
import subprocess
from config import config
from app import create_app

def setup_environment():
    """Set up production environment variables"""
    
    # Check if PORT is already set, preserve it
    existing_port = os.environ.get('PORT')
    
    # Set required environment variables for production
    env_vars = {
        'FLASK_ENV': 'production',
        'DEBUG': 'False',
        'ALLOWED_DOMAINS': 'automation-reports.mobilehmi.org',
        'SERVER_IP': '172.16.18.21',
        'BLOCK_IP_ACCESS': 'True',
        'SECRET_KEY': 'your-production-secret-key-change-this-immediately',
        
        # Email configuration - update with your details
        'SMTP_SERVER': 'smtp.gmail.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'meda.revanth@gmail.com',
        'SMTP_PASSWORD': 'rleg tbhv rwvb kdus',
        'DEFAULT_SENDER': 'meda.revanth@gmail.com',
        'ENABLE_EMAIL_NOTIFICATIONS': 'True',
        
        # Security settings
        'SESSION_COOKIE_SECURE': 'True',
        'WTF_CSRF_ENABLED': 'True',
        'PERMANENT_SESSION_LIFETIME': '7200',
        
        # Database (will use SQLite by default, change to PostgreSQL if needed)
        # 'DATABASE_URL': 'postgresql://username:password@localhost/sat_reports'
    }
    
    # Set environment variables (but preserve existing PORT if set)
    for key, value in env_vars.items():
        os.environ[key] = value
    
    # Restore PORT if it was previously set
    if existing_port:
        os.environ['PORT'] = existing_port
        print(f"✅ Environment variables configured for production (using PORT={existing_port})")
    else:
        os.environ['PORT'] = '80'
        print("✅ Environment variables configured for production (using default PORT=80)")

def check_dependencies():
    """Check if all required dependencies are installed"""
    try:
        import flask
        import flask_login
        import flask_wtf
        import flask_sqlalchemy
        import docxtpl
        import PIL
        print("✅ All required dependencies are available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False

def create_directories():
    """Create required directories"""
    directories = [
        'static/uploads',
        'static/signatures', 
        'outputs',
        'instance',
        'logs',
        'data'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    print("✅ Required directories created")

def main():
    """Main deployment function"""
    print("🚀 SAT Report Generator - Production Deployment")
    print("=" * 50)
    print(f"Target Server: 172.16.18.21")
    print(f"Domain: automation-reports.mobilehmi.org")
    print(f"Port: {os.environ.get('PORT', '80')}")
    print("=" * 50)
    
    # Setup environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Create Flask app with production config
    app = create_app('production')
    
    # Verify configuration
    print(f"🌐 Allowed Domains: {app.config.get('ALLOWED_DOMAINS')}")
    print(f"🛡️  IP Blocking: {app.config.get('BLOCK_IP_ACCESS')}")
    print(f"🔒 Debug Mode: {app.config.get('DEBUG')}")
    print(f"🚪 Port: {app.config.get('PORT')}")
    print()
    
    # Initialize database
    with app.app_context():
        from models import db
        try:
            db.create_all()
            print("✅ Database initialized successfully")
        except Exception as e:
            print(f"⚠️  Database warning: {e}")
    
    # Security status
    print("\n🔐 SECURITY STATUS:")
    if app.config.get('BLOCK_IP_ACCESS'):
        print("✅ Domain-only access: ENABLED")
        print("   - automation-reports.mobilehmi.org ✅ ALLOWED")
        print("   - 172.16.18.21 ❌ BLOCKED")
    else:
        print("⚠️  Domain-only access: DISABLED")
    
    if not app.config.get('DEBUG'):
        print("✅ Production mode: ENABLED")
    else:
        print("⚠️  Production mode: DISABLED")
    
    print("\n" + "=" * 50)
    print("🚀 Starting production server...")
    print("🌐 Access your application at: http://automation-reports.mobilehmi.org")
    print("🚫 Direct IP access will be blocked")
    print("=" * 50)
    
    # Start the server
    port = int(os.environ.get('PORT', '80'))
    try:
        print(f"🌐 Starting server on port {port}...")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True,
            use_reloader=False
        )
    except PermissionError:
        if port == 80:
            print("❌ Permission denied! Port 80 requires administrator privileges.")
            print("Solution: Run as administrator or use a different port.")
            print("To run on port 8080 instead:")
            print("  Set PORT environment variable: set PORT=8080")
            print("  Then configure your web server to forward port 80 to 8080")
        else:
            print(f"❌ Permission denied for port {port}!")
            print("Try a different port number.")
    except Exception as e:
        print(f"❌ Server startup failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()