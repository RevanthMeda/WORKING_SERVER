#!/usr/bin/env python3
"""
Test script for Cully statistics synchronization
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from flask import Flask
    from models import db, CullyStatistics, init_db
    
    # Create a minimal Flask app for testing
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test_key_for_statistics'
    app.config['BASE_DIR'] = os.path.dirname(os.path.abspath(__file__))
    
    # Initialize database
    with app.app_context():
        db.init_app(app)
        
        print("🧪 Testing Cully statistics synchronization...")
        
        # Test the fetch function
        print("📡 Fetching data from Cully.ie...")
        result = CullyStatistics.fetch_and_update_from_cully()
        print(f"✅ Fetch result: {result}")
        
        # Get current statistics
        print("📊 Getting current statistics...")
        stats = CullyStatistics.get_current_statistics()
        print(f"📈 Current stats: {stats}")
        
        print("\n🎯 Summary:")
        print(f"   Instruments: {stats['instruments']}")
        print(f"   Engineers: {stats['engineers']}")
        print(f"   Experience: {stats['experience']}")
        print(f"   Water Plants: {stats['plants']}")
        if stats['last_updated']:
            print(f"   Last Updated: {stats['last_updated']}")
        else:
            print("   Last Updated: Never")
        
        print("\n✅ Test completed successfully!")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the correct directory")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()