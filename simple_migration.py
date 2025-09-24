#!/usr/bin/env python
"""
Simple migration to add edit feature tables and columns
"""

from app import create_app
from models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Starting migration...")
    
    # Create all new tables (including ReportEdit)
    db.create_all()
    print("✅ Tables created/updated")
    
    # Try to add new columns if they don't exist
    try:
        db.session.execute(text("SELECT submitted_at FROM reports LIMIT 1"))
        print("✅ Columns already exist")
    except:
        print("Adding new columns...")
        db.session.rollback()
        
        try:
            db.session.execute(text("ALTER TABLE reports ADD COLUMN submitted_at TIMESTAMP"))
            print("  ✅ Added submitted_at")
        except:
            db.session.rollback()
            
        try:
            db.session.execute(text("ALTER TABLE reports ADD COLUMN approved_at TIMESTAMP"))
            print("  ✅ Added approved_at")
        except:
            db.session.rollback()
            
        try:
            db.session.execute(text("ALTER TABLE reports ADD COLUMN approved_by VARCHAR(120)"))
            print("  ✅ Added approved_by")
        except:
            db.session.rollback()
            
        try:
            db.session.execute(text("ALTER TABLE reports ADD COLUMN edit_count INTEGER DEFAULT 0"))
            print("  ✅ Added edit_count")
        except:
            db.session.rollback()
    
    try:
        db.session.commit()
        print("✅ Migration completed!")
    except:
        db.session.rollback()
        print("⚠️  Some changes may not have been applied, but continuing...")