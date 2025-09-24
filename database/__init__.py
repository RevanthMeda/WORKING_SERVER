"""
Database management package for SAT Report Generator.
"""
from .migrations import MigrationManager, migration_manager, init_migrations
from .config import (
    database_config, get_database_config, 
    DatabaseHealthCheck, DatabaseOptimizer
)
from .cli import register_db_commands
from .performance import (
    query_monitor, pool_monitor, cache_manager,
    DatabaseIndexManager, QueryOptimizer, DatabaseMaintenanceManager,
    init_database_performance, cached_query
)
from .query_analyzer import query_analyzer, setup_query_analysis, get_query_analyzer
from .pooling import (
    pool_manager, leak_detector, init_connection_pooling, get_pool_metrics
)
from .backup import backup_manager, init_backup_system

__all__ = [
    'MigrationManager', 'migration_manager', 'init_migrations',
    'database_config', 'get_database_config',
    'DatabaseHealthCheck', 'DatabaseOptimizer',
    'register_db_commands',
    'query_monitor', 'pool_monitor', 'cache_manager',
    'DatabaseIndexManager', 'QueryOptimizer', 'DatabaseMaintenanceManager',
    'init_database_performance', 'cached_query',
    'pool_manager', 'leak_detector', 'init_connection_pooling', 'get_pool_metrics',
    'backup_manager', 'init_backup_system',
    'query_analyzer', 'setup_query_analysis', 'get_query_analyzer'
]