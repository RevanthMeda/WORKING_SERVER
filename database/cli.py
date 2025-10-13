"""
Flask CLI commands for database management.
"""
import click
from flask import current_app
from flask.cli import with_appcontext
from models import db, User
from .migrations import migration_manager


@click.group()
def db_cli():
    """Database management commands."""
    pass


@db_cli.command('init')
@with_appcontext
def init_db_command():
    """Initialize the database with migrations."""
    try:
        migration_manager.init_migrations()
        click.echo('[+] Database migration system initialized')
    except Exception as e:
        click.echo(f'[-] Failed to initialize migrations: {e}')


@db_cli.command('migrate')
@click.option('--message', '-m', help='Migration message')
@with_appcontext
def migrate_command(message):
    """Create a new migration."""
    try:
        migration_manager.create_migration(message)
        click.echo(f'[+] Migration created: {message or "Auto migration"}')
    except Exception as e:
        click.echo(f'[-] Failed to create migration: {e}')


@db_cli.command('upgrade')
@click.option('--revision', '-r', help='Target revision')
@with_appcontext
def upgrade_command(revision):
    """Upgrade database to latest or specified revision."""
    try:
        # Create backup before upgrade
        backup_file = migration_manager.backup_database()
        if backup_file:
            click.echo(f'[B] Backup created: {backup_file}')
        
        migration_manager.upgrade_database(revision)
        click.echo('[+] Database upgraded successfully')
    except Exception as e:
        click.echo(f'[-] Failed to upgrade database: {e}')


@db_cli.command('downgrade')
@click.option('--revision', '-r', required=True, help='Target revision')
@with_appcontext
def downgrade_command(revision):
    """Downgrade database to specified revision."""
    try:
        if click.confirm(f'Downgrade to revision {revision}? This may cause data loss.'):
            migration_manager.downgrade_database(revision)
            click.echo(f'[+] Database downgraded to: {revision}')
    except Exception as e:
        click.echo(f'[-] Failed to downgrade database: {e}')


@db_cli.command('current')
@with_appcontext
def current_command():
    """Show current database revision."""
    try:
        migration_manager.show_current_revision()
    except Exception as e:
        click.echo(f'[-] Failed to show current revision: {e}')


@db_cli.command('history')
@with_appcontext
def history_command():
    """Show migration history."""
    try:
        migration_manager.show_migration_history()
    except Exception as e:
        click.echo(f'[-] Failed to show migration history: {e}')


@db_cli.command('status')
@with_appcontext
def status_command():
    """Show database status."""
    try:
        # Test connection
        db.engine.connect().close()
        click.echo('[+] Database connection: OK')
        
        # Show table counts
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        click.echo(f'[T] Tables: {len(tables)}')
        
        # Show record counts
        try:
            user_count = User.query.count()
            click.echo(f'[U] Users: {user_count}')
        except:
            pass
        
        # Show current revision
        migration_manager.show_current_revision()
        
    except Exception as e:
        click.echo(f'[-] Database status check failed: {e}')


@db_cli.command('backup')
@with_appcontext
def backup_command():
    """Create database backup."""
    try:
        backup_file = migration_manager.backup_database()
        if backup_file:
            click.echo(f'[+] Backup created: {backup_file}')
        else:
            click.echo('[!]  Backup not supported for this database type')
    except Exception as e:
        click.echo(f'[-] Failed to create backup: {e}')


@db_cli.command('create-admin')
@click.option('--email', default='admin@cullyautomation.com', help='Admin email')
@click.option('--password', default='admin123', help='Admin password')
@click.option('--name', default='System Administrator', help='Admin name')
@with_appcontext
def create_admin_command(email, password, name):
    """Create admin user."""
    try:
        existing = User.query.filter_by(email=email).first()
        if existing:
            click.echo(f'[!]  Admin {email} already exists')
            return
        
        admin = User(
            email=email,
            full_name=name,
            role='Admin',
            status='Active'
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        
        click.echo(f'[+] Admin created: {email}')
        click.echo(f'   Password: {password}')
        click.echo('   [!]  Change password after first login!')
        
    except Exception as e:
        click.echo(f'[-] Failed to create admin: {e}')
        db.session.rollback()


def register_db_commands(app):
    """Register database CLI commands with Flask app."""
    app.cli.add_command(db_cli, name='db')