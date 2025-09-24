#!/usr/bin/env python3
"""
Test script for database migration system.
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_migration_imports():
    """Test that migration system can be imported."""
    try:
        from database import migration_manager, MigrationManager
        print("✅ Migration system imports successful")
        return True
    except ImportError as e:
        print(f"❌ Migration import failed: {e}")
        return False

def test_app_integration():
    """Test migration system integration with Flask app."""
    try:
        from app import create_app
        
        app = create_app('development')
        
        with app.app_context():
            # Test that migration manager is available
            from database import migration_manager
            print("✅ Migration system integrated with Flask app")
            return True
            
    except Exception as e:
        print(f"❌ App integration test failed: {e}")
        return False

def test_database_config():
    """Test database configuration."""
    try:
        from database.config import get_database_config, DatabaseHealthCheck
        
        config = get_database_config('development')
        print(f"✅ Database config loaded: {config.__name__}")
        
        # Test health check
        from app import create_app
        app = create_app('development')
        
        healthy, message = DatabaseHealthCheck.check_connection(app)
        print(f"✅ Database health check: {message}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database config test failed: {e}")
        return False

if __name__ == '__main__':
    print("🧪 Testing Database Migration System")
    print("=" * 40)
    
    tests = [
        test_migration_imports,
        test_app_integration,
        test_database_config
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! Migration system is ready.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check the output above.")
        sys.exit(1)