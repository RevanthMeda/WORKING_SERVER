#!/usr/bin/env python3
"""
Database management CLI for SAT Report Generator.
"""
import os
import sys
import click
from flask import Flask
from flask.cli import with_appcontext
from datetime import datetime
from sqlalchemy import text

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User, Report, SATReport
from database import migration_manager


@click.group()
def cli():
    """Database management commands for SAT Report Generator."""
    pass


@cli.command()
@click.option('--env', default='development', help='Environment (development/production)')
def init_migrations(env):
    """Initialize the database migration system."""
    app = create_app(env)
    
    with app.app_context():
        try:
            migration_manager.init_migrations()
            click.echo("✅ Database migration system initialized successfully")
        except Exception as e:
            click.echo(f"❌ Failed to initialize migrations: {e}")
            sys.exit(1)


@cli.command()
@click.option('--message', '-m', required=True, help='Migration message')
@click.option('--env', default='development', help='Environment (development/production)')
def create_migration(message, env):
    """Create a new database migration."""
    app = create_app(env)
    
    with app.app_context():
        try:
            migration_manager.create_migration(message)
            click.echo(f"✅ Migration created: {message}")
        except Exception as e:
            click.echo(f"❌ Failed to create migration: {e}")
            sys.exit(1)


@cli.command()
@click.option('--revision', '-r', help='Target revision (default: latest)')
@click.option('--env', default='development', help='Environment (development/production)')
@click.option('--backup/--no-backup', default=True, help='Create backup before upgrade')
def upgrade(revision, env, backup):
    """Upgrade database to latest or specified revision."""
    app = create_app(env)
    
    with app.app_context():
        try:
            # Create backup if requested
            if backup:
                backup_file = migration_manager.backup_database()
                if backup_file:
                    click.echo(f"📦 Database backup created: {backup_file}")
            
            # Validate migration
            if migration_manager.validate_migration(revision):
                click.echo("✅ Migration validation passed")
            else:
                click.echo("⚠️  Migration validation failed, proceeding anyway...")
            
            # Perform upgrade
            migration_manager.upgrade_database(revision)
            click.echo("✅ Database upgraded successfully")
            
        except Exception as e:
            click.echo(f"❌ Failed to upgrade database: {e}")
            sys.exit(1)


@cli.command()
@click.option('--revision', '-r', required=True, help='Target revision')
@click.option('--env', default='development', help='Environment (development/production)')
@click.option('--backup/--no-backup', default=True, help='Create backup before downgrade')
def downgrade(revision, env, backup):
    """Downgrade database to specified revision."""
    app = create_app(env)
    
    with app.app_context():
        try:
            # Create backup if requested
            if backup:
                backup_file = migration_manager.backup_database()
                if backup_file:
                    click.echo(f"📦 Database backup created: {backup_file}")
            
            # Confirm downgrade
            click.confirm(
                f"Are you sure you want to downgrade to revision {revision}? "
                "This may result in data loss.",
                abort=True
            )
            
            # Perform downgrade
            migration_manager.downgrade_database(revision)
            click.echo(f"✅ Database downgraded to revision: {revision}")
            
        except Exception as e:
            click.echo(f"❌ Failed to downgrade database: {e}")
            sys.exit(1)


@cli.command()
@click.option('--env', default='development', help='Environment (development/production)')
def current(env):
    """Show current database revision."""
    app = create_app(env)
    
    with app.app_context():
        try:
            migration_manager.show_current_revision()
        except Exception as e:
            click.echo(f"❌ Failed to show current revision: {e}")
            sys.exit(1)


@cli.command()
@click.option('--env', default='development', help='Environment (development/production)')
def history(env):
    """Show migration history."""
    app = create_app(env)
    
    with app.app_context():
        try:
            migration_manager.show_migration_history()
        except Exception as e:
            click.echo(f"❌ Failed to show migration history: {e}")
            sys.exit(1)


@cli.command()
@click.option('--env', default='development', help='Environment (development/production)')
def status(env):
    """Show database and migration status."""
    app = create_app(env)
    
    with app.app_context():
        try:
            # Database connection status
            try:
                db.engine.connect().close()
                click.echo("✅ Database connection: OK")
            except Exception as e:
                click.echo(f"❌ Database connection: FAILED - {e}")
                return
            
            # Table counts
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            click.echo(f"📊 Database tables: {len(tables)}")
            
            # Record counts for main tables
            try:
                user_count = User.query.count()
                report_count = Report.query.count()
                sat_count = SATReport.query.count()
                
                click.echo(f"👥 Users: {user_count}")
                click.echo(f"📄 Reports: {report_count}")
                click.echo(f"🔧 SAT Reports: {sat_count}")
            except Exception as e:
                click.echo(f"⚠️  Could not count records: {e}")
            
            # Migration status
            click.echo("\n📋 Migration Status:")
            migration_manager.show_current_revision()
            
        except Exception as e:
            click.echo(f"❌ Failed to show status: {e}")
            sys.exit(1)


@cli.command()
@click.option('--env', default='development', help='Environment (development/production)')
def backup(env):
    """Create database backup."""
    app = create_app(env)
    
    with app.app_context():
        try:
            backup_file = migration_manager.backup_database()
            if backup_file:
                click.echo(f"✅ Database backup created: {backup_file}")
            else:
                click.echo("⚠️  Backup not created (may not be supported for this database type)")
        except Exception as e:
            click.echo(f"❌ Failed to create backup: {e}")
            sys.exit(1)


@cli.command()
@click.option('--backup-file', '-f', required=True, help='Backup file to restore from')
@click.option('--env', default='development', help='Environment (development/production)')
def restore(backup_file, env):
    """Restore database from backup."""
    app = create_app(env)
    
    with app.app_context():
        try:
            # Confirm restore
            click.confirm(
                f"Are you sure you want to restore from {backup_file}? "
                "This will overwrite the current database.",
                abort=True
            )
            
            success = migration_manager.restore_database(backup_file)
            if success:
                click.echo(f"✅ Database restored from: {backup_file}")
            else:
                click.echo("❌ Failed to restore database")
                sys.exit(1)
                
        except Exception as e:
            click.echo(f"❌ Failed to restore database: {e}")
            sys.exit(1)


@cli.command()
@click.option('--email', default='admin@cullyautomation.com', help='Admin email')
@click.option('--password', default='admin123', help='Admin password')
@click.option('--name', default='System Administrator', help='Admin full name')
@click.option('--env', default='development', help='Environment (development/production)')
def create_admin(email, password, name, env):
    """Create admin user."""
    app = create_app(env)
    
    with app.app_context():
        try:
            # Check if admin already exists
            existing_admin = User.query.filter_by(email=email).first()
            if existing_admin:
                click.echo(f"⚠️  Admin user {email} already exists")
                return
            
            # Create new admin user
            admin_user = User(
                email=email,
                full_name=name,
                role='Admin',
                status='Active'
            )
            admin_user.set_password(password)
            db.session.add(admin_user)
            db.session.commit()
            
            click.echo(f"✅ Admin user created successfully: {email}")
            click.echo(f"   Password: {password}")
            click.echo("   ⚠️  Please change the password after first login!")
            
        except Exception as e:
            click.echo(f"❌ Failed to create admin user: {e}")
            db.session.rollback()
            sys.exit(1)


@cli.command()
@click.option('--env', default='development', help='Environment (development/production)')
def validate_schema(env):
    """Validate database schema consistency."""
    app = create_app(env)
    
    with app.app_context():
        try:
            # Check table existence
            inspector = db.inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            
            # Expected tables from models
            expected_tables = {
                'users', 'reports', 'sat_reports', 'fds_reports', 'hds_reports',
                'site_survey_reports', 'sds_reports', 'fat_reports', 'report_templates',
                'user_analytics', 'report_versions', 'report_comments', 'webhooks',
                'saved_searches', 'audit_logs', 'report_archives', 'api_keys',
                'api_usage', 'scheduled_reports', 'system_settings', 'module_specs',
                'notifications'
            }
            
            missing_tables = expected_tables - existing_tables
            extra_tables = existing_tables - expected_tables
            
            if missing_tables:
                click.echo(f"⚠️  Missing tables: {', '.join(missing_tables)}")
            
            if extra_tables:
                click.echo(f"ℹ️  Extra tables: {', '.join(extra_tables)}")
            
            if not missing_tables and not extra_tables:
                click.echo("✅ Database schema is consistent")
            
            # Check for foreign key constraints
            for table_name in existing_tables:
                try:
                    foreign_keys = inspector.get_foreign_keys(table_name)
                    if foreign_keys:
                        click.echo(f"🔗 {table_name}: {len(foreign_keys)} foreign key(s)")
                except Exception as e:
                    click.echo(f"⚠️  Could not check foreign keys for {table_name}: {e}")
            
        except Exception as e:
            click.echo(f"❌ Failed to validate schema: {e}")
            sys.exit(1)


@cli.command()
@click.option('--env', default='development', help='Environment (development/production)')
@click.option('--table', help='Specific table to analyze (optional)')
def analyze_performance(env, table):
    """Analyze database performance and suggest optimizations."""
    app = create_app(env)
    
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)
            
            if table:
                tables_to_analyze = [table] if table in inspector.get_table_names() else []
                if not tables_to_analyze:
                    click.echo(f"❌ Table '{table}' not found")
                    return
            else:
                tables_to_analyze = inspector.get_table_names()
            
            click.echo("🔍 Database Performance Analysis")
            click.echo("=" * 40)
            
            for table_name in tables_to_analyze:
                try:
                    # Get table info
                    columns = inspector.get_columns(table_name)
                    indexes = inspector.get_indexes(table_name)
                    foreign_keys = inspector.get_foreign_keys(table_name)
                    
                    # Count records
                    with db.engine.connect() as conn:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        record_count = result.scalar()
                    
                    click.echo(f"\n📊 Table: {table_name}")
                    click.echo(f"   Records: {record_count:,}")
                    click.echo(f"   Columns: {len(columns)}")
                    click.echo(f"   Indexes: {len(indexes)}")
                    click.echo(f"   Foreign Keys: {len(foreign_keys)}")
                    
                    # Suggest optimizations
                    if record_count > 10000 and len(indexes) < 2:
                        click.echo("   💡 Consider adding indexes for better performance")
                    
                    if len(columns) > 20:
                        click.echo("   💡 Consider table normalization")
                    
                except Exception as e:
                    click.echo(f"   ⚠️  Could not analyze {table_name}: {e}")
            
        except Exception as e:
            click.echo(f"❌ Failed to analyze performance: {e}")
            sys.exit(1)


if __name__ == '__main__':
    cli()