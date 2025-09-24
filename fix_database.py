#!/usr/bin/env python3
"""
Fix the database by creating the missing cully_statistics table
"""
from flask import Flask
from models import db, CullyStatistics
import os

def fix_database():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Revanth%4012@localhost:5432/SAT_Report_Generator'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    with app.app_context():
        db.init_app(app)
        
        print("🔧 Creating missing database tables...")
        
        # Create all tables including cully_statistics
        db.create_all()
        
        # Initialize with default values if no record exists
        if not CullyStatistics.query.first():
            initial_stats = CullyStatistics()
            db.session.add(initial_stats)
            db.session.commit()
            print('✅ Created cully_statistics table and initialized with default values')
        else:
            print('✅ cully_statistics table already exists')

if __name__ == "__main__":
    fix_database()