
#!/usr/bin/env python3
"""
Script to initialize a new database with admin user and fix missing tables
Run this after updating your DATABASE_URL in .env
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, init_db, create_admin_user, User, CullyStatistics

def initialize_new_database():
    """Initialize new database with tables and admin user"""
    print("🔧 Initializing new database...")
    
    # Create Flask app
    app = create_app()
    
    with app.app_context():
        try:
            # Test database connection
            print("📡 Testing database connection...")
            db.engine.connect().close()
            print("✅ Database connection successful")
            
            # Create all tables including cully_statistics
            print("📋 Creating database tables...")
            db.create_all()
            print("✅ Database tables created")
            
            # Initialize Cully statistics if missing
            print("📊 Initializing Cully statistics...")
            if not CullyStatistics.query.first():
                initial_stats = CullyStatistics()
                db.session.add(initial_stats)
                db.session.commit()
                print('✅ Created cully_statistics table and initialized with default values')
            else:
                print('✅ cully_statistics table already exists')
            
            # Create admin user
            print("👤 Creating admin user...")
            admin_user = create_admin_user(
                email='admin@cullyautomation.com',
                password='admin123',
                full_name='System Administrator'
            )
            
            if admin_user:
                print("\n🎉 Database initialization completed successfully!")
                print("\n📝 Admin Login Details:")
                print("   Email: admin@cullyautomation.com")
                print("   Password: admin123")
                print("\n⚠️  IMPORTANT: Change the admin password after first login!")
                print("\n🚀 You can now start the application with: python app.py")
            else:
                print("❌ Failed to create admin user")
                return False
                
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    print("🔄 New Database Initialization Script")
    print("=====================================")
    
    # Check if .env file exists
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("Please create a .env file with your DATABASE_URL")
        sys.exit(1)
    
    # Check if DATABASE_URL is set
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in .env file!")
        print("Please add DATABASE_URL to your .env file")
        sys.exit(1)
    
    print(f"🗄️  Using database: {database_url[:50]}...")
    
    # Confirm before proceeding
    confirm = input("\n⚠️  This will create tables and admin user in the database. Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Operation cancelled")
        sys.exit(0)
    
    # Initialize database
    success = initialize_new_database()
    
    if success:
        print("\n✅ Setup complete! Your application is ready to use.")
        sys.exit(0)
    else:
        print("\n❌ Setup failed. Please check the errors above.")
        sys.exit(1)
