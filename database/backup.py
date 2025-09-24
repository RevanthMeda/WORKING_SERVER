"""
Database backup and recovery system for SAT Report Generator.
"""
import os
import shutil
import gzip
import json
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from flask import current_app
from models import db
import threading
import schedule
import time

logger = logging.getLogger(__name__)


class DatabaseBackupManager:
    """Manage database backups and recovery operations."""
    
    def __init__(self):
        self.backup_dir = None
        self.retention_days = 30
        self.max_backups = 50
        self.compression_enabled = True
        self.backup_scheduler = None
        
    def init_app(self, app):
        """Initialize backup manager with Flask app."""
        self.backup_dir = app.config.get('BACKUP_DIR', 'backups')
        self.retention_days = app.config.get('BACKUP_RETENTION_DAYS', 30)
        self.max_backups = app.config.get('MAX_BACKUPS', 50)
        self.compression_enabled = app.config.get('BACKUP_COMPRESSION', True)
        
        # Ensure backup directory exists
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Set up automatic backups if configured
        backup_schedule = app.config.get('BACKUP_SCHEDULE')
        if backup_schedule:
            self.setup_automatic_backups(backup_schedule)
    
    def create_backup(self, backup_name=None, include_files=True):
        """Create a complete database backup."""
        try:
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f'backup_{timestamp}'
            
            backup_path = os.path.join(self.backup_dir, backup_name)
            os.makedirs(backup_path, exist_ok=True)
            
            # Get database URI
            db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
            if not db_uri:
                raise ValueError("Database URI not configured")
            
            # Create database backup based on type
            db_backup_file = self._create_database_backup(db_uri, backup_path)
            
            # Create metadata file
            metadata = self._create_backup_metadata(backup_name, db_backup_file, include_files)
            metadata_file = os.path.join(backup_path, 'metadata.json')
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            # Backup application files if requested
            if include_files:
                self._backup_application_files(backup_path)
            
            # Compress backup if enabled
            if self.compression_enabled:
                compressed_file = self._compress_backup(backup_path)
                # Remove uncompressed directory
                shutil.rmtree(backup_path)
                backup_path = compressed_file
            
            # Clean up old backups
            self._cleanup_old_backups()
            
            logger.info(f"Backup created successfully: {backup_path}")
            
            return {
                'success': True,
                'backup_path': backup_path,
                'backup_name': backup_name,
                'size': self._get_backup_size(backup_path),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_database_backup(self, db_uri, backup_path):
        """Create database backup based on database type."""
        parsed_uri = urlparse(db_uri)
        db_type = parsed_uri.scheme
        
        if db_type == 'sqlite':
            return self._backup_sqlite(db_uri, backup_path)
        elif db_type == 'postgresql':
            return self._backup_postgresql(parsed_uri, backup_path)
        elif db_type == 'mysql':
            return self._backup_mysql(parsed_uri, backup_path)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def _backup_sqlite(self, db_uri, backup_path):
        """Backup SQLite database."""
        # Extract database file path
        db_file = db_uri.replace('sqlite:///', '')
        
        if not os.path.exists(db_file):
            raise FileNotFoundError(f"SQLite database file not found: {db_file}")
        
        # Copy database file
        backup_file = os.path.join(backup_path, 'database.db')
        shutil.copy2(db_file, backup_file)
        
        # Create SQL dump as well
        sql_file = os.path.join(backup_path, 'database.sql')
        try:
            # Use sqlite3 command line tool if available
            subprocess.run([
                'sqlite3', db_file, '.dump'
            ], stdout=open(sql_file, 'w'), check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to Python sqlite3 module
            import sqlite3
            
            conn = sqlite3.connect(db_file)
            with open(sql_file, 'w') as f:
                for line in conn.iterdump():
                    f.write(f'{line}\n')
            conn.close()
        
        return backup_file
    
    def _backup_postgresql(self, parsed_uri, backup_path):
        """Backup PostgreSQL database."""
        # Extract connection parameters
        host = parsed_uri.hostname or 'localhost'
        port = parsed_uri.port or 5432
        database = parsed_uri.path.lstrip('/')
        username = parsed_uri.username
        password = parsed_uri.password
        
        # Create environment for pg_dump
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password
        
        # Create SQL dump
        sql_file = os.path.join(backup_path, 'database.sql')
        
        cmd = [
            'pg_dump',
            '-h', host,
            '-p', str(port),
            '-U', username,
            '-d', database,
            '--no-password',
            '--verbose',
            '--clean',
            '--if-exists',
            '--create',
            '-f', sql_file
        ]
        
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
            logger.info(f"PostgreSQL backup completed: {result.stderr}")
        except subprocess.CalledProcessError as e:
            logger.error(f"PostgreSQL backup failed: {e.stderr}")
            raise
        
        # Create custom format backup as well
        custom_file = os.path.join(backup_path, 'database.backup')
        
        cmd_custom = [
            'pg_dump',
            '-h', host,
            '-p', str(port),
            '-U', username,
            '-d', database,
            '--no-password',
            '--format=custom',
            '--compress=9',
            '-f', custom_file
        ]
        
        try:
            subprocess.run(cmd_custom, env=env, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            # Custom format backup failed, but SQL dump succeeded
            pass
        
        return sql_file
    
    def _backup_mysql(self, parsed_uri, backup_path):
        """Backup MySQL database."""
        # Extract connection parameters
        host = parsed_uri.hostname or 'localhost'
        port = parsed_uri.port or 3306
        database = parsed_uri.path.lstrip('/')
        username = parsed_uri.username
        password = parsed_uri.password
        
        # Create SQL dump
        sql_file = os.path.join(backup_path, 'database.sql')
        
        cmd = ['mysqldump']
        
        if host:
            cmd.extend(['-h', host])
        if port:
            cmd.extend(['-P', str(port)])
        if username:
            cmd.extend(['-u', username])
        if password:
            cmd.append(f'-p{password}')
        
        cmd.extend([
            '--single-transaction',
            '--routines',
            '--triggers',
            '--add-drop-database',
            '--create-options',
            database
        ])
        
        try:
            with open(sql_file, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, check=True)
            logger.info("MySQL backup completed")
        except subprocess.CalledProcessError as e:
            logger.error(f"MySQL backup failed: {e.stderr}")
            raise
        
        return sql_file
    
    def _backup_application_files(self, backup_path):
        """Backup application files (uploads, templates, etc.)."""
        files_backup_dir = os.path.join(backup_path, 'files')
        os.makedirs(files_backup_dir, exist_ok=True)
        
        # Directories to backup
        backup_dirs = [
            ('static/uploads', 'uploads'),
            ('static/signatures', 'signatures'),
            ('templates', 'templates'),
            ('instance', 'instance')
        ]
        
        for src_dir, dest_name in backup_dirs:
            src_path = os.path.join(current_app.root_path, src_dir)
            dest_path = os.path.join(files_backup_dir, dest_name)
            
            if os.path.exists(src_path):
                try:
                    shutil.copytree(src_path, dest_path, ignore=shutil.ignore_patterns('*.pyc', '__pycache__'))
                    logger.info(f"Backed up {src_dir} to {dest_name}")
                except Exception as e:
                    logger.warning(f"Failed to backup {src_dir}: {e}")
    
    def _create_backup_metadata(self, backup_name, db_backup_file, include_files):
        """Create backup metadata."""
        return {
            'backup_name': backup_name,
            'created_at': datetime.now(),
            'database_file': os.path.basename(db_backup_file),
            'database_uri': current_app.config.get('SQLALCHEMY_DATABASE_URI', '').split('@')[-1],  # Hide credentials
            'include_files': include_files,
            'app_version': current_app.config.get('VERSION', 'unknown'),
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'backup_type': 'full' if include_files else 'database_only'
        }
    
    def _compress_backup(self, backup_path):
        """Compress backup directory."""
        compressed_file = f"{backup_path}.tar.gz"
        
        import tarfile
        
        with tarfile.open(compressed_file, 'w:gz') as tar:
            tar.add(backup_path, arcname=os.path.basename(backup_path))
        
        return compressed_file
    
    def _get_backup_size(self, backup_path):
        """Get backup size in bytes."""
        if os.path.isfile(backup_path):
            return os.path.getsize(backup_path)
        elif os.path.isdir(backup_path):
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(backup_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            return total_size
        return 0
    
    def list_backups(self):
        """List available backups."""
        backups = []
        
        if not os.path.exists(self.backup_dir):
            return backups
        
        for item in os.listdir(self.backup_dir):
            item_path = os.path.join(self.backup_dir, item)
            
            # Check if it's a backup (directory or compressed file)
            if os.path.isdir(item_path) or item.endswith('.tar.gz'):
                backup_info = {
                    'name': item,
                    'path': item_path,
                    'size': self._get_backup_size(item_path),
                    'created_at': datetime.fromtimestamp(os.path.getctime(item_path)),
                    'type': 'compressed' if item.endswith('.tar.gz') else 'directory'
                }
                
                # Try to read metadata
                metadata_file = None
                if os.path.isdir(item_path):
                    metadata_file = os.path.join(item_path, 'metadata.json')
                elif item.endswith('.tar.gz'):
                    # Extract metadata from compressed file
                    try:
                        import tarfile
                        with tarfile.open(item_path, 'r:gz') as tar:
                            try:
                                metadata_member = tar.getmember(f"{item.replace('.tar.gz', '')}/metadata.json")
                                metadata_content = tar.extractfile(metadata_member).read()
                                backup_info['metadata'] = json.loads(metadata_content)
                            except KeyError:
                                pass
                    except Exception:
                        pass
                
                if metadata_file and os.path.exists(metadata_file):
                    try:
                        with open(metadata_file, 'r') as f:
                            backup_info['metadata'] = json.load(f)
                    except Exception:
                        pass
                
                backups.append(backup_info)
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        
        return backups
    
    def restore_backup(self, backup_name, restore_files=True):
        """Restore database from backup."""
        try:
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Backup not found: {backup_name}")
            
            # Extract compressed backup if needed
            temp_dir = None
            if backup_name.endswith('.tar.gz'):
                temp_dir = os.path.join(self.backup_dir, f"temp_{int(time.time())}")
                os.makedirs(temp_dir, exist_ok=True)
                
                import tarfile
                with tarfile.open(backup_path, 'r:gz') as tar:
                    tar.extractall(temp_dir)
                
                # Find the extracted directory
                extracted_items = os.listdir(temp_dir)
                if len(extracted_items) == 1:
                    backup_path = os.path.join(temp_dir, extracted_items[0])
                else:
                    backup_path = temp_dir
            
            # Read metadata
            metadata_file = os.path.join(backup_path, 'metadata.json')
            metadata = {}
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            
            # Restore database
            db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
            self._restore_database(db_uri, backup_path, metadata)
            
            # Restore files if requested
            if restore_files and metadata.get('include_files', False):
                self._restore_application_files(backup_path)
            
            # Clean up temporary directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            logger.info(f"Backup restored successfully: {backup_name}")
            
            return {
                'success': True,
                'backup_name': backup_name,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Backup restoration failed: {e}")
            
            # Clean up temporary directory on error
            if 'temp_dir' in locals() and temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def _restore_database(self, db_uri, backup_path, metadata):
        """Restore database from backup."""
        parsed_uri = urlparse(db_uri)
        db_type = parsed_uri.scheme
        
        if db_type == 'sqlite':
            self._restore_sqlite(db_uri, backup_path)
        elif db_type == 'postgresql':
            self._restore_postgresql(parsed_uri, backup_path)
        elif db_type == 'mysql':
            self._restore_mysql(parsed_uri, backup_path)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
    
    def _restore_sqlite(self, db_uri, backup_path):
        """Restore SQLite database."""
        db_file = db_uri.replace('sqlite:///', '')
        backup_db_file = os.path.join(backup_path, 'database.db')
        backup_sql_file = os.path.join(backup_path, 'database.sql')
        
        # Create backup of current database
        if os.path.exists(db_file):
            backup_current = f"{db_file}.backup_{int(time.time())}"
            shutil.copy2(db_file, backup_current)
            logger.info(f"Current database backed up to: {backup_current}")
        
        # Restore from database file if available
        if os.path.exists(backup_db_file):
            shutil.copy2(backup_db_file, db_file)
            logger.info("SQLite database restored from database file")
        elif os.path.exists(backup_sql_file):
            # Restore from SQL dump
            if os.path.exists(db_file):
                os.remove(db_file)
            
            try:
                subprocess.run([
                    'sqlite3', db_file, f'.read {backup_sql_file}'
                ], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to Python sqlite3 module
                import sqlite3
                
                conn = sqlite3.connect(db_file)
                with open(backup_sql_file, 'r') as f:
                    conn.executescript(f.read())
                conn.close()
            
            logger.info("SQLite database restored from SQL dump")
        else:
            raise FileNotFoundError("No database backup file found")
    
    def _restore_postgresql(self, parsed_uri, backup_path):
        """Restore PostgreSQL database."""
        # Extract connection parameters
        host = parsed_uri.hostname or 'localhost'
        port = parsed_uri.port or 5432
        database = parsed_uri.path.lstrip('/')
        username = parsed_uri.username
        password = parsed_uri.password
        
        # Create environment for psql
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password
        
        # Try custom format first
        custom_file = os.path.join(backup_path, 'database.backup')
        sql_file = os.path.join(backup_path, 'database.sql')
        
        if os.path.exists(custom_file):
            # Restore from custom format
            cmd = [
                'pg_restore',
                '-h', host,
                '-p', str(port),
                '-U', username,
                '-d', database,
                '--no-password',
                '--clean',
                '--if-exists',
                '--verbose',
                custom_file
            ]
            
            try:
                result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
                logger.info(f"PostgreSQL restored from custom format: {result.stderr}")
                return
            except subprocess.CalledProcessError as e:
                logger.warning(f"Custom format restore failed, trying SQL: {e.stderr}")
        
        if os.path.exists(sql_file):
            # Restore from SQL dump
            cmd = [
                'psql',
                '-h', host,
                '-p', str(port),
                '-U', username,
                '-d', database,
                '--no-password',
                '-f', sql_file
            ]
            
            try:
                result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
                logger.info("PostgreSQL restored from SQL dump")
            except subprocess.CalledProcessError as e:
                logger.error(f"PostgreSQL restore failed: {e.stderr}")
                raise
        else:
            raise FileNotFoundError("No PostgreSQL backup file found")
    
    def _restore_mysql(self, parsed_uri, backup_path):
        """Restore MySQL database."""
        # Extract connection parameters
        host = parsed_uri.hostname or 'localhost'
        port = parsed_uri.port or 3306
        database = parsed_uri.path.lstrip('/')
        username = parsed_uri.username
        password = parsed_uri.password
        
        sql_file = os.path.join(backup_path, 'database.sql')
        
        if not os.path.exists(sql_file):
            raise FileNotFoundError("No MySQL backup file found")
        
        cmd = ['mysql']
        
        if host:
            cmd.extend(['-h', host])
        if port:
            cmd.extend(['-P', str(port)])
        if username:
            cmd.extend(['-u', username])
        if password:
            cmd.append(f'-p{password}')
        
        cmd.append(database)
        
        try:
            with open(sql_file, 'r') as f:
                result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True, check=True)
            logger.info("MySQL database restored")
        except subprocess.CalledProcessError as e:
            logger.error(f"MySQL restore failed: {e.stderr}")
            raise
    
    def _restore_application_files(self, backup_path):
        """Restore application files."""
        files_backup_dir = os.path.join(backup_path, 'files')
        
        if not os.path.exists(files_backup_dir):
            logger.info("No application files to restore")
            return
        
        # Directories to restore
        restore_dirs = [
            ('uploads', 'static/uploads'),
            ('signatures', 'static/signatures'),
            ('templates', 'templates'),
            ('instance', 'instance')
        ]
        
        for src_name, dest_dir in restore_dirs:
            src_path = os.path.join(files_backup_dir, src_name)
            dest_path = os.path.join(current_app.root_path, dest_dir)
            
            if os.path.exists(src_path):
                try:
                    # Create backup of current directory
                    if os.path.exists(dest_path):
                        backup_current = f"{dest_path}.backup_{int(time.time())}"
                        shutil.move(dest_path, backup_current)
                        logger.info(f"Current {dest_dir} backed up to: {backup_current}")
                    
                    # Restore from backup
                    shutil.copytree(src_path, dest_path)
                    logger.info(f"Restored {src_name} to {dest_dir}")
                    
                except Exception as e:
                    logger.warning(f"Failed to restore {src_name}: {e}")
    
    def delete_backup(self, backup_name):
        """Delete a backup."""
        try:
            backup_path = os.path.join(self.backup_dir, backup_name)
            
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Backup not found: {backup_name}")
            
            if os.path.isdir(backup_path):
                shutil.rmtree(backup_path)
            else:
                os.remove(backup_path)
            
            logger.info(f"Backup deleted: {backup_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete backup {backup_name}: {e}")
            return False
    
    def _cleanup_old_backups(self):
        """Clean up old backups based on retention policy."""
        try:
            backups = self.list_backups()
            
            # Remove backups older than retention period
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            old_backups = [b for b in backups if b['created_at'] < cutoff_date]
            
            for backup in old_backups:
                self.delete_backup(backup['name'])
                logger.info(f"Deleted old backup: {backup['name']}")
            
            # Remove excess backups if we have too many
            if len(backups) > self.max_backups:
                excess_backups = backups[self.max_backups:]
                for backup in excess_backups:
                    self.delete_backup(backup['name'])
                    logger.info(f"Deleted excess backup: {backup['name']}")
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
    
    def setup_automatic_backups(self, schedule_config):
        """Set up automatic backup scheduling."""
        try:
            # Parse schedule configuration
            if schedule_config == 'daily':
                schedule.every().day.at("02:00").do(self._scheduled_backup)
            elif schedule_config == 'weekly':
                schedule.every().sunday.at("02:00").do(self._scheduled_backup)
            elif schedule_config == 'hourly':
                schedule.every().hour.do(self._scheduled_backup)
            elif isinstance(schedule_config, dict):
                # Custom schedule
                frequency = schedule_config.get('frequency', 'daily')
                time_str = schedule_config.get('time', '02:00')
                
                if frequency == 'daily':
                    schedule.every().day.at(time_str).do(self._scheduled_backup)
                elif frequency == 'weekly':
                    day = schedule_config.get('day', 'sunday')
                    getattr(schedule.every(), day.lower()).at(time_str).do(self._scheduled_backup)
            
            # Start scheduler thread
            self.backup_scheduler = threading.Thread(target=self._run_scheduler, daemon=True)
            self.backup_scheduler.start()
            
            logger.info(f"Automatic backups scheduled: {schedule_config}")
            
        except Exception as e:
            logger.error(f"Failed to setup automatic backups: {e}")
    
    def _scheduled_backup(self):
        """Perform scheduled backup."""
        try:
            result = self.create_backup(include_files=True)
            if result['success']:
                logger.info(f"Scheduled backup completed: {result['backup_name']}")
            else:
                logger.error(f"Scheduled backup failed: {result['error']}")
        except Exception as e:
            logger.error(f"Scheduled backup error: {e}")
    
    def _run_scheduler(self):
        """Run the backup scheduler."""
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def get_backup_status(self):
        """Get backup system status."""
        try:
            backups = self.list_backups()
            
            total_size = sum(b['size'] for b in backups)
            latest_backup = backups[0] if backups else None
            
            return {
                'total_backups': len(backups),
                'total_size': total_size,
                'latest_backup': latest_backup,
                'backup_dir': self.backup_dir,
                'retention_days': self.retention_days,
                'max_backups': self.max_backups,
                'compression_enabled': self.compression_enabled,
                'scheduler_running': self.backup_scheduler is not None and self.backup_scheduler.is_alive()
            }
            
        except Exception as e:
            logger.error(f"Failed to get backup status: {e}")
            return {'error': str(e)}


# Global backup manager instance
backup_manager = DatabaseBackupManager()


def init_backup_system(app):
    """Initialize database backup system."""
    backup_manager.init_app(app)
    logger.info("Database backup system initialized")