
#!/usr/bin/env python3
"""
Test script to check if all imports are working correctly
"""

def test_imports():
    print("🔍 Testing imports...")
    
    try:
        print("  ✓ Flask imports...")
        from flask import Flask, request, render_template, jsonify, redirect, url_for
        from flask_wtf.csrf import CSRFProtect, generate_csrf
        from flask_login import current_user
        
        print("  ✓ Config imports...")
        from app_config import Config
        
        print("  ✓ Models imports...")
        from models import db, init_db
        
        print("  ✓ Auth imports...")
        from auth import init_auth
        
        print("  ✓ Route imports...")
        from routes.main import main_bp
        from routes.approval import approval_bp
        from routes.status import status_bp
        from routes.auth import auth_bp
        from routes.dashboard import dashboard_bp
        from routes.reports import reports_bp
        from routes.notifications import notifications_bp
        from routes.io_builder import io_builder_bp
        
        print("✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == '__main__':
    success = test_imports()
    if not success:
        print("\n🔧 Please check your dependencies and file structure.")
        exit(1)
    else:
        print("\n🚀 Ready to start the server!")
