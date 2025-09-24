#!/usr/bin/env python3
"""
Production HTTPS Flask application on port 443
Direct access with SSL/TLS encryption
"""

import os
import sys
from app_config import config
from app import create_app

def setup_https_environment():
    """Set up environment for direct HTTPS on port 443"""
    
    env_vars = {
        'FLASK_ENV': 'production',
        'DEBUG': 'False',
        'PORT': '443',
        'ALLOWED_DOMAINS': 'automation-reports.mobilehmi.org',
        'SERVER_IP': '172.16.18.21',
        'BLOCK_IP_ACCESS': 'True',  # Enable domain-only security
        'SECRET_KEY': 'production-secure-key-change-immediately',
        
        # Email configuration
        'SMTP_SERVER': 'smtp.gmail.com',
        'SMTP_PORT': '587',
        'SMTP_USERNAME': 'meda.revanth@gmail.com',
        'SMTP_PASSWORD': 'rleg tbhv rwvb kdus',
        'DEFAULT_SENDER': 'meda.revanth@gmail.com',
        'ENABLE_EMAIL_NOTIFICATIONS': 'True',
        
        # HTTPS Security settings
        'SESSION_COOKIE_SECURE': 'True',  # Require HTTPS for cookies
        'WTF_CSRF_ENABLED': 'True',
        'PERMANENT_SESSION_LIFETIME': '7200',
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    print("✅ HTTPS environment configured for port 443")

def main():
    """Production HTTPS Flask application"""
    print("🔒 SAT Report Generator - Production HTTPS Server")
    print("=" * 60)
    print("HTTPS Configuration:")
    print("- Server: https://automation-reports.mobilehmi.org:443")
    print("- SSL/TLS: Required (port 443)")
    print("- Domain security: ENABLED")
    print("- IP blocking: ENABLED")
    print("- Certificate: SSL certificate required")
    print("=" * 60)
    
    setup_https_environment()
    
    # Create Flask app
    app = create_app('production')
    
    print(f"🌐 Port: {app.config.get('PORT')}")
    print(f"🛡️  Domain Security: {app.config.get('BLOCK_IP_ACCESS')}")
    print(f"🔒 HTTPS Mode: Required")
    print()
    print("🔐 Security Status:")
    print("✅ Domain-only access: automation-reports.mobilehmi.org")
    print("❌ Direct IP access: 172.16.18.21 (blocked)")
    print("✅ SSL/TLS encryption: Required")
    print()
    print("📋 SSL Certificate Requirements:")
    print("1. Valid SSL certificate for automation-reports.mobilehmi.org")
    print("2. Certificate files: server.crt and server.key")
    print("3. Place certificates in 'ssl' directory")
    print()
    print("🚀 Starting HTTPS server...")
    print("=" * 60)
    
    # Initialize database
    with app.app_context():
        from models import db
        try:
            db.create_all()
            print("✅ Database initialized")
        except Exception as e:
            print(f"⚠️  Database warning: {e}")
    
    # Check for SSL certificates
    ssl_cert_path = 'ssl/server.crt'
    ssl_key_path = 'ssl/server.key'
    
    # Create SSL directory if it doesn't exist
    os.makedirs('ssl', exist_ok=True)
    
    # Start HTTPS server
    try:
        if os.path.exists(ssl_cert_path) and os.path.exists(ssl_key_path):
            print("✅ SSL certificates found - using production certificates")
            ssl_context = (ssl_cert_path, ssl_key_path)
        else:
            print("⚠️  SSL certificates not found - using self-signed certificate")
            print("   For production, place your SSL certificate files in:")
            print("   - ssl/server.crt (certificate)")
            print("   - ssl/server.key (private key)")
            ssl_context = 'adhoc'  # Self-signed for development
        
        print(f"🌐 Starting HTTPS server on port 443...")
        app.run(
            host='0.0.0.0',
            port=443,
            debug=False,
            threaded=True,
            use_reloader=False,
            ssl_context=ssl_context
        )
    except PermissionError:
        print("❌ Permission denied for port 443!")
        print("   Port 443 requires administrator privileges.")
        print("   Solution: Run Command Prompt as Administrator")
    except Exception as e:
        print(f"❌ HTTPS server error: {e}")
        print("   Check SSL certificate configuration")
        sys.exit(1)

if __name__ == '__main__':
    main()