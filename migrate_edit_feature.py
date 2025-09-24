#!/usr/bin/env python
"""
Database migration script to add ReportEdit table and new fields to Report table
for the edit feature implementation.
"""

from app import create_app
from models import db, ReportEdit, Report
from sqlalchemy import text
import sys

def run_migration():
    """Run database migration to add edit feature tables and fields"""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("🔄 Starting database migration for edit feature...")
            
            # Create all new tables (including ReportEdit)
            db.create_all()
            print("✅ Created ReportEdit table")
            
            # Check if new columns exist in Report table
            # If not, add them (SQLite doesn't support ALTER TABLE well)
            try:
                # Test if columns exist by querying them
                result = db.session.execute(text(
                    "SELECT submitted_at, approved_at, approved_by, edit_count FROM reports LIMIT 1"
                ))
                print("✅ Report table already has new columns")
            except Exception as e:
                # Columns don't exist, need to add them
                print("📝 Adding new columns to Report table...")
                
                # Add new columns to Report table
                migrations = [
                    "ALTER TABLE reports ADD COLUMN submitted_at DATETIME",
                    "ALTER TABLE reports ADD COLUMN approved_at DATETIME",
                    "ALTER TABLE reports ADD COLUMN approved_by VARCHAR(120)",
                    "ALTER TABLE reports ADD COLUMN edit_count INTEGER DEFAULT 0"
                ]
                
                for migration in migrations:
                    try:
                        db.session.execute(text(migration))
                        print(f"  ✅ {migration.split('ADD COLUMN')[1].strip()}")
                    except Exception as col_error:
                        # Column might already exist
                        print(f"  ⚠️  Column might already exist: {col_error}")
                
                db.session.commit()
                print("✅ Added new columns to Report table")
            
            # Update existing reports to have edit_count = 0 if NULL
            db.session.execute(text(
                "UPDATE reports SET edit_count = 0 WHERE edit_count IS NULL"
            ))
            db.session.commit()
            
            # Verify ReportEdit table exists
            result = db.session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='report_edits'"
            ))
            if result.fetchone():
                print("✅ ReportEdit table verified")
            else:
                print("❌ ReportEdit table not created!")
                return False
            
            print("\n✅ Database migration completed successfully!")
            print("   - ReportEdit table created for audit trail")
            print("   - Report table updated with edit tracking fields")
            print("   - Database is ready for the edit feature")
            
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)