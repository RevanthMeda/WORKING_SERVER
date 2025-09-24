"""
Database migration management for SAT Report Generator.
"""
import os
import sys
import click
from flask import current_app
from flask_migrate import Migrate, init, migrate, upgrade, downgrade, revision, stamp
from models import db
from datetime import datetime
import logging
from sqlalchemy import text

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MigrationManager:
    """Manage database migrations with Alembic and Flask-Migrate."""
    
    def __init__(self, app=None):
        self.app = app
        self.migrate = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize migration manager with Flask app."""
        self.app = app
        
        # Set up migrations directory
        migrations_dir = os.path.join(app.root_path, 'migrations')
        
        # Initialize Flask-Migrate
        self.migrate = Migrate(
            app, 
            db, 
            directory=migrations_dir,
            compare_type=True,
            compare_server_default=True
        )
        
        # Add CLI commands
        self._register_cli_commands()
    
    def _register_cli_commands(self):
        """Register CLI commands for migration management."""
        
        @self.app.cli.command('init-db')
        def init_db_command():
            """Initialize the database with migrations."""
            try:
                self.init_migrations()
                logger.info("Database migration system initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize database migrations: {e}")
                sys.exit(1)
        
        @self.app.cli.command('create-migration')
        @click.option('--message', '-m', help='Migration message')
        def create_migration_command(message):
            """Create a new migration."""
            try:
                self.create_migration(message)
                logger.info(f"Migration created: {message}")
            except Exception as e:
                logger.error(f"Failed to create migration: {e}")
                sys.exit(1)
        
        @self.app.cli.command('upgrade-db')
        @click.option('--revision', '-r', help='Target revision')
        def upgrade_db_command(revision):
            """Upgrade database to latest or specified revision."""
            try:
                self.upgrade_database(revision)
                logger.info("Database upgraded successfully")
            except Exception as e:
                logger.error(f"Failed to upgrade database: {e}")
                sys.exit(1)
        
        @self.app.cli.command('downgrade-db')
        @click.option('--revision', '-r', help='Target revision')
        def downgrade_db_command(revision):
            """Downgrade database to specified revision."""
            try:
                self.downgrade_database(revision)
                logger.info("Database downgraded successfully")
            except Exception as e:
                logger.error(f"Failed to downgrade database: {e}")
                sys.exit(1)
        
        @self.app.cli.command('migration-history')
        def migration_history_command():
            """Show migration history."""
            try:
                self.show_migration_history()
            except Exception as e:
                logger.error(f"Failed to show migration history: {e}")
                sys.exit(1)
        
        @self.app.cli.command('current-revision')
        def current_revision_command():
            """Show current database revision."""
            try:
                self.show_current_revision()
            except Exception as e:
                logger.error(f"Failed to show current revision: {e}")
                sys.exit(1)
    
    def init_migrations(self):
        """Initialize the migrations directory and create initial migration."""
        migrations_dir = os.path.join(self.app.root_path, 'migrations')
        
        # Check if migrations directory already exists
        if os.path.exists(migrations_dir):
            logger.info("Migrations directory already exists")
            return
        
        # Initialize migrations
        with self.app.app_context():
            init(directory=migrations_dir)
            logger.info("Migrations directory initialized")
            
            # Create initial migration for existing schema
            self.create_initial_migration()
    
    def create_initial_migration(self):
        """Create initial migration for existing database schema."""
        try:
            with self.app.app_context():
                # Check if database has existing tables
                inspector = db.inspect(db.engine)
                existing_tables = inspector.get_table_names()
                
                if existing_tables:
                    logger.info(f"Found {len(existing_tables)} existing tables")
                    
                    # Create initial migration
                    migrate(
                        message='Initial migration with existing schema',
                        directory=os.path.join(self.app.root_path, 'migrations')
                    )
                    
                    # Stamp the database with the initial revision
                    stamp(directory=os.path.join(self.app.root_path, 'migrations'))
                    
                    logger.info("Initial migration created and database stamped")
                else:
                    logger.info("No existing tables found, creating fresh migration")
                    
                    # Create all tables first
                    db.create_all()
                    
                    # Create initial migration
                    migrate(
                        message='Initial database schema',
                        directory=os.path.join(self.app.root_path, 'migrations')
                    )
                    
                    logger.info("Fresh database schema created with initial migration")
                    
        except Exception as e:
            logger.error(f"Failed to create initial migration: {e}")
            raise
    
    def create_migration(self, message=None):
        """Create a new migration."""
        if not message:
            message = f"Auto migration {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        with self.app.app_context():
            migrate(
                message=message,
                directory=os.path.join(self.app.root_path, 'migrations')
            )
            logger.info(f"Migration created: {message}")
    
    def upgrade_database(self, revision=None):
        """Upgrade database to latest or specified revision."""
        with self.app.app_context():
            if revision:
                upgrade(
                    revision=revision,
                    directory=os.path.join(self.app.root_path, 'migrations')
                )
                logger.info(f"Database upgraded to revision: {revision}")
            else:
                upgrade(directory=os.path.join(self.app.root_path, 'migrations'))
                logger.info("Database upgraded to latest revision")
    
    def downgrade_database(self, revision):
        """Downgrade database to specified revision."""
        if not revision:
            raise ValueError("Revision is required for downgrade")
        
        with self.app.app_context():
            downgrade(
                revision=revision,
                directory=os.path.join(self.app.root_path, 'migrations')
            )
            logger.info(f"Database downgraded to revision: {revision}")
    
    def show_migration_history(self):
        """Show migration history."""
        from alembic import command
        from alembic.config import Config
        
        migrations_dir = os.path.join(self.app.root_path, 'migrations')
        alembic_cfg = Config(os.path.join(migrations_dir, 'alembic.ini'))
        
        with self.app.app_context():
            command.history(alembic_cfg)
    
    def show_current_revision(self):
        """Show current database revision."""
        from alembic import command
        from alembic.config import Config
        
        migrations_dir = os.path.join(self.app.root_path, 'migrations')
        alembic_cfg = Config(os.path.join(migrations_dir, 'alembic.ini'))
        
        with self.app.app_context():
            command.current(alembic_cfg)
    
    def validate_migration(self, revision=None):
        """Validate migration before applying."""
        try:
            with self.app.app_context():
                # Check database connectivity
                db.engine.connect().close()
                
                # Validate migration files
                migrations_dir = os.path.join(self.app.root_path, 'migrations')
                if not os.path.exists(migrations_dir):
                    raise ValueError("Migrations directory not found")
                
                # Check for migration conflicts
                from alembic import command
                from alembic.config import Config
                
                alembic_cfg = Config(os.path.join(migrations_dir, 'alembic.ini'))
                
                # This would check for any issues with the migration
                command.check(alembic_cfg)
                
                logger.info("Migration validation passed")
                return True
                
        except Exception as e:
            logger.error(f"Migration validation failed: {e}")
            return False
    
    def backup_database(self):
        """Create database backup before migration."""
        try:
            backup_dir = os.path.join(self.app.root_path, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(backup_dir, f'database_backup_{timestamp}.sql')
            
            # For SQLite databases
            if 'sqlite' in self.app.config.get('SQLALCHEMY_DATABASE_URI', ''):
                import shutil
                db_path = self.app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
                backup_path = os.path.join(backup_dir, f'database_backup_{timestamp}.db')
                shutil.copy2(db_path, backup_path)
                logger.info(f"Database backup created: {backup_path}")
                return backup_path
            
            # For PostgreSQL databases
            elif 'postgresql' in self.app.config.get('SQLALCHEMY_DATABASE_URI', ''):
                import subprocess
                
                # Extract database connection info
                db_uri = self.app.config['SQLALCHEMY_DATABASE_URI']
                # This would need proper parsing of the database URI
                # For now, just log the intent
                logger.info(f"PostgreSQL backup would be created: {backup_file}")
                return backup_file
            
            else:
                logger.warning("Database backup not implemented for this database type")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return None
    
    def restore_database(self, backup_file):
        """Restore database from backup."""
        try:
            if not os.path.exists(backup_file):
                raise FileNotFoundError(f"Backup file not found: {backup_file}")
            
            # For SQLite databases
            if 'sqlite' in self.app.config.get('SQLALCHEMY_DATABASE_URI', ''):
                import shutil
                db_path = self.app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
                shutil.copy2(backup_file, db_path)
                logger.info(f"Database restored from: {backup_file}")
                return True
            
            # For PostgreSQL databases
            elif 'postgresql' in self.app.config.get('SQLALCHEMY_DATABASE_URI', ''):
                # This would implement PostgreSQL restore
                logger.info(f"PostgreSQL restore would be performed from: {backup_file}")
                return True
            
            else:
                logger.error("Database restore not implemented for this database type")
                return False
                
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False


class MigrationValidator:
    """Validate migrations for safety and consistency."""
    
    @staticmethod
    def validate_schema_changes(migration_file):
        """Validate schema changes in migration file."""
        try:
            with open(migration_file, 'r') as f:
                content = f.read()
            
            # Check for potentially dangerous operations
            dangerous_operations = [
                'drop_table',
                'drop_column',
                'alter_column',  # Can be dangerous if changing data types
            ]
            
            warnings = []
            for operation in dangerous_operations:
                if operation in content:
                    warnings.append(f"Potentially dangerous operation found: {operation}")
            
            # Check for missing rollback operations
            if 'def upgrade():' in content and 'def downgrade():' in content:
                upgrade_section = content.split('def upgrade():')[1].split('def downgrade():')[0]
                downgrade_section = content.split('def downgrade():')[1]
                
                if 'pass' in downgrade_section.strip():
                    warnings.append("Downgrade function is empty - rollback may not be possible")
            
            return warnings
            
        except Exception as e:
            logger.error(f"Failed to validate migration file: {e}")
            return [f"Validation error: {e}"]
    
    @staticmethod
    def check_data_integrity(app):
        """Check data integrity before and after migration."""
        try:
            with app.app_context():
                # Count records in each table
                table_counts = {}
                
                inspector = db.inspect(db.engine)
                for table_name in inspector.get_table_names():
                    try:
                        with db.engine.connect() as conn:
                            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                            count = result.scalar()
                        table_counts[table_name] = count
                    except Exception as e:
                        logger.warning(f"Could not count records in table {table_name}: {e}")
                
                return table_counts
                
        except Exception as e:
            logger.error(f"Failed to check data integrity: {e}")
            return {}


# Global migration manager instance
migration_manager = MigrationManager()


def init_migrations(app):
    """Initialize migration system with Flask app."""
    migration_manager.init_app(app)
    return migration_manager