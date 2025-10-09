"""
Critical migration script to add missing columns to the reports table.
This fixes the login/dashboard access issues caused by missing database columns.
"""
import os
import sys
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration(app, db):
    """
    Add missing columns to the reports table and create ReportEdit table if needed.
    This migration is idempotent (safe to run multiple times).
    """
    with app.app_context():
        try:
            logger.info("Starting critical database migration...")
            
            # Get database engine and inspector
            engine = db.engine
            inspector = inspect(engine)
            
            # Check if reports table exists
            if 'reports' not in inspector.get_table_names():
                logger.error("Reports table does not exist! Creating all tables...")
                db.create_all()
                logger.info("All tables created successfully")
                return True
            
            # Get existing columns in reports table
            existing_columns = [col['name'] for col in inspector.get_columns('reports')]
            logger.info(f"Existing columns in reports table: {existing_columns}")
            
            # Define columns to add
            columns_to_add = [
                ('submitted_at', 'TIMESTAMP', None),
                ('approved_at', 'TIMESTAMP', None),
                ('approved_by', 'VARCHAR(120)', None),
                ('edit_count', 'INTEGER', 0)
            ]
            
            # Check database type
            db_uri = str(engine.url)
            is_sqlite = 'sqlite' in db_uri
            is_postgresql = 'postgresql' in db_uri or 'postgres' in db_uri
            
            # Add missing columns
            with engine.begin() as conn:
                for column_name, column_type, default_value in columns_to_add:
                    if column_name not in existing_columns:
                        logger.info(f"Adding missing column: {column_name}")
                        
                        # Build ALTER TABLE statement based on database type
                        if is_sqlite:
                            if default_value is not None:
                                if isinstance(default_value, str):
                                    sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type} DEFAULT '{default_value}'"
                                else:
                                    sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
                            else:
                                sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type}"
                        elif is_postgresql:
                            if default_value is not None:
                                if isinstance(default_value, str):
                                    sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type} DEFAULT '{default_value}'"
                                else:
                                    sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
                            else:
                                sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type}"
                        else:
                            # Generic SQL for other databases
                            if default_value is not None:
                                if isinstance(default_value, str):
                                    sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type} DEFAULT '{default_value}'"
                                else:
                                    sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
                            else:
                                sql = f"ALTER TABLE reports ADD COLUMN {column_name} {column_type}"
                        
                        try:
                            conn.execute(text(sql))
                            logger.info(f"✓ Added column {column_name} successfully")
                        except Exception as col_error:
                            logger.warning(f"Could not add column {column_name}: {col_error}")
                    else:
                        logger.info(f"Column {column_name} already exists")
            
            # Check if report_edits table exists, create if not
            if 'report_edits' not in inspector.get_table_names():
                logger.info("Creating report_edits table...")
                
                create_table_sql = """
                CREATE TABLE report_edits (
                    id INTEGER PRIMARY KEY,
                    report_id VARCHAR(36) NOT NULL,
                    edited_by VARCHAR(120) NOT NULL,
                    edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    field_name VARCHAR(100),
                    old_value TEXT,
                    new_value TEXT,
                    edit_type VARCHAR(20),
                    comments TEXT,
                    FOREIGN KEY (report_id) REFERENCES reports(id)
                )
                """
                
                if is_sqlite:
                    # SQLite uses AUTOINCREMENT differently
                    create_table_sql = create_table_sql.replace("INTEGER PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
                elif is_postgresql:
                    # PostgreSQL uses SERIAL for auto-increment
                    create_table_sql = create_table_sql.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
                
                with engine.begin() as conn:
                    try:
                        conn.execute(text(create_table_sql))
                        logger.info("✓ Created report_edits table successfully")
                    except Exception as table_error:
                        logger.warning(f"Could not create report_edits table: {table_error}")
            else:
                logger.info("report_edits table already exists")

            # Ensure api_keys table schema matches latest expectations
            if 'api_keys' in inspector.get_table_names():
                api_columns = [col['name'] for col in inspector.get_columns('api_keys')]
                existing_indexes = [index['name'] for index in inspector.get_indexes('api_keys')]

                with engine.begin() as conn:
                    if 'key_hash' not in api_columns:
                        logger.info("Adding missing key_hash column to api_keys table")

                        if is_sqlite:
                            conn.execute(text("ALTER TABLE api_keys ADD COLUMN key_hash TEXT"))
                        elif is_postgresql:
                            conn.execute(text("ALTER TABLE api_keys ADD COLUMN key_hash VARCHAR(64)"))
                        else:
                            conn.execute(text("ALTER TABLE api_keys ADD COLUMN key_hash VARCHAR(64)"))

                        if 'key' in api_columns:
                            try:
                                conn.execute(
                                    text(
                                        "UPDATE api_keys SET key_hash = key "
                                        "WHERE key IS NOT NULL AND (key_hash IS NULL OR key_hash = '')"
                                    )
                                )
                                logger.info("Backfilled key_hash values from legacy key column")
                            except Exception as backfill_error:
                                logger.warning(f"Could not backfill key_hash values: {backfill_error}")
                        else:
                            logger.warning("Legacy api_keys.key column not found; manual backfill of key_hash required")
                    else:
                        logger.info("api_keys.key_hash column already present")

                    if 'ux_api_keys_key_hash' not in existing_indexes:
                        try:
                            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_api_keys_key_hash ON api_keys(key_hash)"))
                            logger.info("Ensured unique index on api_keys.key_hash")
                        except Exception as index_error:
                            logger.warning(f"Could not create unique index on api_keys.key_hash: {index_error}")

                    column_type_map = {col['name']: col['type'] for col in inspector.get_columns('api_keys')}

                    if 'user_id' not in api_columns:
                        logger.info("Adding missing user_id column to api_keys table")

                        if is_sqlite:
                            conn.execute(text("ALTER TABLE api_keys ADD COLUMN user_id INTEGER"))
                        elif is_postgresql:
                            conn.execute(text("ALTER TABLE api_keys ADD COLUMN user_id INTEGER"))
                        else:
                            conn.execute(text("ALTER TABLE api_keys ADD COLUMN user_id INTEGER"))

                        if 'user_email' in api_columns:
                            try:
                                if is_postgresql:
                                    conn.execute(
                                        text(
                                            "UPDATE api_keys AS k "
                                             "SET user_id = u.id "
                                             "FROM users AS u "
                                            "WHERE k.user_id IS NULL "
                                            "AND LOWER(k.user_email) = LOWER(u.email)"
                                        )
                                    )
                                else:
                                    conn.execute(
                                        text(
                                            "UPDATE api_keys "
                                            "SET user_id = ("
                                            "SELECT id FROM users WHERE LOWER(users.email) = LOWER(api_keys.user_email)"
                                            ") "
                                            "WHERE user_id IS NULL"
                                        )
                                    )
                                logger.info("Backfilled api_keys.user_id values from user_email")
                            except Exception as backfill_error:
                                logger.warning(f"Could not backfill api_keys.user_id values: {backfill_error}")
                        else:
                            logger.warning("api_keys.user_email column not found; manual user_id backfill may be required")

                        if is_postgresql:
                            try:
                                conn.execute(
                                    text(
                                        "ALTER TABLE api_keys "
                                        "ADD CONSTRAINT IF NOT EXISTS fk_api_keys_user "
                                        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
                                    )
                                )
                                logger.info("Ensured foreign key constraint for api_keys.user_id")
                            except Exception as fk_error:
                                logger.warning(f"Could not create foreign key constraint on api_keys.user_id: {fk_error}")
                    else:
                        logger.info("api_keys.user_id column already present")
                        col_type = str(column_type_map.get('user_id')).lower()
                        if 'integer' not in col_type:
                            try:
                                if is_postgresql:
                                    conn.execute(text(
                                        "ALTER TABLE api_keys "
                                        "ALTER COLUMN user_id TYPE INTEGER USING user_id::INTEGER"
                                    ))
                                    logger.info("Converted api_keys.user_id column to INTEGER")
                                elif is_sqlite:
                                    logger.warning("SQLite migration from TEXT to INTEGER for api_keys.user_id requires manual intervention")
                            except Exception as type_error:
                                logger.warning(f"Could not convert api_keys.user_id column type: {type_error}")

                    if 'ix_api_keys_user_id' not in existing_indexes:
                        try:
                            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys(user_id)"))
                            logger.info("Ensured index on api_keys.user_id")
                        except Exception as index_error:
                            logger.warning(f"Could not create index on api_keys.user_id: {index_error}")
            else:
                logger.info("api_keys table does not exist; skipping API key schema adjustments")
            
            # Verify all columns are present
            updated_columns = [col['name'] for col in inspector.get_columns('reports')]
            missing = []
            for column_name, _, _ in columns_to_add:
                if column_name not in updated_columns:
                    missing.append(column_name)
            
            if missing:
                logger.error(f"Failed to add columns: {missing}")
                return False
            
            logger.info("✅ Database migration completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def ensure_database_ready(app, db):
    """
    Ensure database is ready with all required columns.
    This is called on every app startup.
    """
    try:
        # First ensure tables exist
        with app.app_context():
            try:
                # Try to create all tables if they don't exist
                db.create_all()
            except Exception as e:
                logger.warning(f"Could not create tables (may already exist): {e}")
            
            # Run the migration to add missing columns
            success = run_migration(app, db)
            
            if success:
                logger.info("Database is ready for use")
            else:
                logger.error("Database migration had issues but continuing...")
            
            return success
    except Exception as e:
        logger.error(f"Failed to ensure database readiness: {e}")
        return False


if __name__ == "__main__":
    # For manual execution
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app import create_app
    from models import db
    
    app = create_app()
    success = ensure_database_ready(app, db)
    
    if success:
        print("✅ Migration completed successfully!")
        sys.exit(0)
    else:
        print("❌ Migration failed!")
        sys.exit(1)
