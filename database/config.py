"""
Database configuration for different environments.
"""
import os
from urllib.parse import quote_plus
from sqlalchemy import text


class DatabaseConfig:
    """Base database configuration."""
    
    # Connection pool settings - optimized for performance
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,  # Reduced from 10
        'pool_timeout': 15,  # Reduced from 20
        'pool_recycle': 1800,  # 30 minutes instead of -1
        'max_overflow': 2,  # Allow some overflow connections
        'pool_pre_ping': True,  # Verify connections before use
    }
    
    # Migration settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # Query timeout settings
    SQLALCHEMY_ENGINE_OPTIONS.update({
        'connect_args': {
            'timeout': 30,  # Connection timeout
            'check_same_thread': False,  # For SQLite
        }
    })


class DevelopmentDatabaseConfig(DatabaseConfig):
    """Development database configuration."""
    
    # SQLite for development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'database.db')
    
    # Disable query logging by default for performance
    SQLALCHEMY_ECHO = False  # Changed from True
    SQLALCHEMY_RECORD_QUERIES = False  # Changed from True
    
    # Smaller connection pool for development
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_timeout': 10,
        'pool_recycle': -1,
        'max_overflow': 0,
        'pool_pre_ping': True,
        'connect_args': {
            'timeout': 30,
            'check_same_thread': False,
        }
    }


class TestingDatabaseConfig(DatabaseConfig):
    """Testing database configuration."""
    
    # In-memory SQLite for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable query logging for faster tests
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_RECORD_QUERIES = False
    
    # Minimal connection pool for testing
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 1,
        'pool_timeout': 5,
        'pool_recycle': -1,
        'max_overflow': 0,
        'pool_pre_ping': False,
        'connect_args': {
            'timeout': 10,
            'check_same_thread': False,
        }
    }


class ProductionDatabaseConfig(DatabaseConfig):
    """Production database configuration."""
    
    # PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    if not SQLALCHEMY_DATABASE_URI:
        # Fallback to environment variables
        db_user = os.environ.get('DB_USER', 'postgres')
        db_password = os.environ.get('DB_PASSWORD', '')
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_name = os.environ.get('DB_NAME', 'sat_reports')
        
        # URL encode password to handle special characters
        if db_password:
            db_password = quote_plus(db_password)
        
        SQLALCHEMY_DATABASE_URI = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    
    # Disable query logging in production
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_RECORD_QUERIES = False
    
    # Optimized connection pool for production - reduced for performance
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 8,  # Reduced from 20
        'pool_timeout': 20,  # Reduced from 30
        'pool_recycle': 1800,  # 30 minutes instead of 1 hour
        'max_overflow': 5,  # Reduced from 10
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 30,
            'application_name': 'sat_report_generator',
            'options': '-c timezone=UTC',
        }
    }


class StagingDatabaseConfig(ProductionDatabaseConfig):
    """Staging database configuration (similar to production)."""
    
    # Use staging database
    SQLALCHEMY_DATABASE_URI = os.environ.get('STAGING_DATABASE_URL') or \
        ProductionDatabaseConfig.SQLALCHEMY_DATABASE_URI
    
    # Enable some logging for staging
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_RECORD_QUERIES = True
    
    # Smaller connection pool for staging - optimized
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,  # Reduced from 10
        'pool_timeout': 15,  # Reduced from 20
        'pool_recycle': 1800,  # 30 minutes instead of 1 hour
        'max_overflow': 2,  # Reduced from 5
        'pool_pre_ping': True,
        'connect_args': {
            'connect_timeout': 30,
            'application_name': 'sat_report_generator_staging',
            'options': '-c timezone=UTC',
        }
    }


# Configuration mapping
database_config = {
    'development': DevelopmentDatabaseConfig,
    'testing': TestingDatabaseConfig,
    'staging': StagingDatabaseConfig,
    'production': ProductionDatabaseConfig,
    'default': DevelopmentDatabaseConfig
}


def get_database_config(config_name='default'):
    """Get database configuration for specified environment."""
    return database_config.get(config_name, database_config['default'])


class DatabaseHealthCheck:
    """Database health check utilities."""
    
    @staticmethod
    def check_connection(app):
        """Check database connection health."""
        try:
            with app.app_context():
                from models import db
                
                # Test basic connection
                db.engine.connect().close()
                
                # Test query execution
                with db.engine.connect() as conn:
                    result = conn.execute(text('SELECT 1'))
                
                return True, "Database connection healthy"
                
        except Exception as e:
            return False, f"Database connection failed: {str(e)}"
    
    @staticmethod
    def check_migrations(app):
        """Check if database migrations are up to date."""
        try:
            with app.app_context():
                from alembic import command
                from alembic.config import Config
                from alembic.script import ScriptDirectory
                from alembic.runtime.environment import EnvironmentContext
                from alembic.runtime.migration import MigrationContext
                
                migrations_dir = os.path.join(app.root_path, 'migrations')
                
                if not os.path.exists(migrations_dir):
                    return False, "Migrations directory not found"
                
                alembic_cfg = Config(os.path.join(migrations_dir, 'alembic.ini'))
                script = ScriptDirectory.from_config(alembic_cfg)
                
                with app.app_context():
                    from models import db
                    
                    with db.engine.connect() as connection:
                        context = MigrationContext.configure(connection)
                        current_rev = context.get_current_revision()
                        head_rev = script.get_current_head()
                        
                        if current_rev == head_rev:
                            return True, f"Database is up to date (revision: {current_rev})"
                        else:
                            return False, f"Database needs migration (current: {current_rev}, head: {head_rev})"
                
        except Exception as e:
            return False, f"Migration check failed: {str(e)}"
    
    @staticmethod
    def get_database_info(app):
        """Get database information and statistics."""
        try:
            with app.app_context():
                from models import db
                
                info = {}
                
                # Database URL (sanitized)
                db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
                if '@' in db_url:
                    # Hide password
                    parts = db_url.split('@')
                    user_part = parts[0].split('://')[-1].split(':')[0]
                    host_part = '@'.join(parts[1:])
                    info['database_url'] = f"{db_url.split('://')[0]}://{user_part}:***@{host_part}"
                else:
                    info['database_url'] = db_url
                
                # Connection pool info
                pool = db.engine.pool
                info['pool_size'] = pool.size()
                info['pool_checked_in'] = pool.checkedin()
                info['pool_checked_out'] = pool.checkedout()
                info['pool_overflow'] = pool.overflow()
                
                # Table information
                inspector = db.inspect(db.engine)
                tables = inspector.get_table_names()
                info['table_count'] = len(tables)
                info['tables'] = tables
                
                return True, info
                
        except Exception as e:
            return False, f"Failed to get database info: {str(e)}"


class DatabaseOptimizer:
    """Database optimization utilities."""
    
    @staticmethod
    def analyze_slow_queries(app, limit=10):
        """Analyze slow queries (PostgreSQL specific)."""
        try:
            with app.app_context():
                from models import db
                
                if 'postgresql' not in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
                    return False, "Slow query analysis only available for PostgreSQL"
                
                # Query for slow queries
                query = """
                SELECT 
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows
                FROM pg_stat_statements 
                ORDER BY total_time DESC 
                LIMIT %s
                """
                
                with db.engine.connect() as conn:
                    result = conn.execute(text(query), {'limit': limit})
                    slow_queries = result.fetchall()
                
                return True, slow_queries
                
        except Exception as e:
            return False, f"Slow query analysis failed: {str(e)}"
    
    @staticmethod
    def suggest_indexes(app):
        """Suggest database indexes for optimization."""
        try:
            with app.app_context():
                from models import db
                
                suggestions = []
                
                # Common index suggestions based on model relationships
                index_suggestions = [
                    {
                        'table': 'reports',
                        'columns': ['user_email', 'status'],
                        'reason': 'Frequently filtered by user and status'
                    },
                    {
                        'table': 'reports',
                        'columns': ['created_at'],
                        'reason': 'Frequently ordered by creation date'
                    },
                    {
                        'table': 'audit_logs',
                        'columns': ['timestamp', 'user_email'],
                        'reason': 'Frequently filtered by time and user'
                    },
                    {
                        'table': 'api_usage',
                        'columns': ['timestamp', 'api_key_id'],
                        'reason': 'Frequently filtered for rate limiting'
                    },
                    {
                        'table': 'notifications',
                        'columns': ['user_email', 'read'],
                        'reason': 'Frequently filtered by user and read status'
                    }
                ]
                
                # Check which indexes already exist
                inspector = db.inspect(db.engine)
                
                for suggestion in index_suggestions:
                    table_name = suggestion['table']
                    
                    if table_name not in inspector.get_table_names():
                        continue
                    
                    existing_indexes = inspector.get_indexes(table_name)
                    existing_columns = set()
                    
                    for index in existing_indexes:
                        existing_columns.update(index['column_names'])
                    
                    suggested_columns = suggestion['columns']
                    
                    # Check if any of the suggested columns are already indexed
                    if not any(col in existing_columns for col in suggested_columns):
                        suggestions.append(suggestion)
                
                return True, suggestions
                
        except Exception as e:
            return False, f"Index suggestion failed: {str(e)}"