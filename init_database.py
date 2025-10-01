#!/usr/bin/env python3
"""
Database initialization script for SAT Report Generator
This script creates the database and adds essential indexes for performance.
"""

import os
import sys
from flask import Flask
from models import db, User, Report, SATReport, SystemSettings

def create_app_for_db():
    """Create minimal Flask app for database operations"""
    app = Flask(__name__)
    
    # Use environment config or default to SQLite
    base_dir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(base_dir, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(instance_dir, "sat_reports.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'temp-key-for-init'
    
    # Initialize database
    db.init_app(app)
    
    return app

def create_indexes():
    """Create essential database indexes for performance"""
    try:
        from sqlalchemy import text
        
        # Report indexes for common queries
        with db.engine.connect() as conn:
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status)'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_reports_user_email ON reports(user_email)'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at)'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_reports_type ON reports(type)'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_reports_status_user ON reports(status, user_email)'))
            
            # User indexes
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_users_role_status ON users(role, status)'))
            
            # SAT Report indexes
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_sat_reports_report_id ON sat_reports(report_id)'))
            conn.commit()
        
        print("✅ Database indexes created successfully")
        return True
    except Exception as e:
        print(f"⚠️  Warning: Could not create some indexes: {e}")
        return False

def create_admin_user():
    """Create default admin user if none exists"""
    try:
        admin_exists = User.query.filter_by(role='Admin').first()
        if admin_exists:
            print(f"✅ Admin user already exists: {admin_exists.email}")
            return True
            
        # Create default admin user
        admin = User(
            full_name='System Administrator',
            email='admin@cullyautomation.com',
            role='Admin',
            status='Active'
        )
        admin.set_password('admin123')  # Change this in production!
        
        db.session.add(admin)
        db.session.commit()
        
        print("✅ Default admin user created:")
        print("   Email: admin@cullyautomation.com")
        print("   Password: admin123")
        print("   ⚠️  Please change this password immediately!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create admin user: {e}")
        db.session.rollback()
        return False

def init_system_settings():
    """Initialize default system settings"""
    try:
        settings = [
            ('app_name', 'SAT Report Generator'),
            ('version', '2.0.0'),
            ('company_name', 'Cully Automation'),
            ('default_approvers_configured', 'false')
        ]
        
        for key, default_value in settings:
            existing = SystemSettings.query.filter_by(key=key).first()
            if not existing:
                setting = SystemSettings(key=key, value=default_value)
                db.session.add(setting)
        
        db.session.commit()
        print("✅ System settings initialized")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize system settings: {e}")
        db.session.rollback()
        return False

def main():
    """Main initialization function"""
    print("🚀 SAT Report Generator - Database Initialization")
    print("=" * 50)
    
    app = create_app_for_db()
    
    with app.app_context():
        try:
            # Test database connection
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            print("✅ Database connection successful")
            
            # Create all tables
            print("📋 Creating database tables...")
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Create indexes for performance
            print("🔍 Creating database indexes...")
            create_indexes()
            
            # Create default admin user
            print("👤 Setting up admin user...")
            create_admin_user()
            
            # Initialize system settings
            print("⚙️  Initializing system settings...")
            init_system_settings()
            
            print("\n" + "=" * 50)
            print("✅ Database initialization completed successfully!")
            print("\n🔗 Database location:")
            print(f"   {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            print("\n🚀 You can now start the application:")
            print("   python app.py")
            
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            print(f"Error details: {type(e).__name__}: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    main()