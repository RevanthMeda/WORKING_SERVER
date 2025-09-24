#!/usr/bin/env python3
"""
Production startup script for SAT Report Generator
Ensures proper environment and configuration for domain-only access
"""

import os
import sys
from app_config import config
from app import create_app

def main():
    """Main entry point for production deployment"""
    
    # Set production environment
    os.environ['FLASK_ENV'] = 'production'
    
    # Verify production configuration
    print("🔧 SAT Report Generator - Production Deployment")
    print("=" * 50)
    
    # Check required environment variables
    required_vars = [
        'ALLOWED_DOMAINS',
        'SERVER_IP', 
        'SMTP_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set the following environment variables:")
        print("- ALLOWED_DOMAINS=automation-reports.mobilehmi.org")
        print("- SERVER_IP=172.16.18.21")
        print("- SMTP_PASSWORD=<your-gmail-app-password>")
        print("- BLOCK_IP_ACCESS=True")
        sys.exit(1)
    
    # Create Flask app with production config
    app = create_app('production')
    
    # Verify configuration
    print(f"🌐 Allowed Domains: {app.config.get('ALLOWED_DOMAINS')}")
    print(f"🛡️  IP Blocking: {app.config.get('BLOCK_IP_ACCESS')}")
    print(f"🔒 Debug Mode: {app.config.get('DEBUG')}")
    print(f"🚪 Port: {app.config.get('PORT')}")
    print()
    
    # Security status
    if app.config.get('BLOCK_IP_ACCESS'):
        print("✅ Domain-only access security: ENABLED")
    else:
        print("⚠️  Domain-only access security: DISABLED")
    
    if not app.config.get('DEBUG'):
        print("✅ Production mode: ENABLED")
    else:
        print("⚠️  Production mode: DISABLED (Debug is on)")
    
    print("\n" + "=" * 50)
    print("🚀 Ready for deployment!")
    print("Use: gunicorn --bind 0.0.0.0:80 --workers 4 production_start:app")
    
    return app

# Create app instance for Gunicorn
app = main()

if __name__ == '__main__':
    # Direct execution for testing
    app.run(host='0.0.0.0', port=80, debug=False)