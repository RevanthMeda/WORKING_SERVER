"""
Database performance optimization for SAT Report Generator.
"""
import time
import logging
from functools import wraps
from flask import current_app, g, request
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import Pool
from models import db
from datetime import datetime, timedelta
import threading
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class QueryPerformanceMonitor:
    """Monitor and analyze database query performance."""
    
    def __init__(self):
        self.slow_queries = deque(maxlen=100)  # Keep last 100 slow queries - reduced from 1000
        self.query_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'avg_time': 0,
            'max_time': 0,
            'min_time': float('inf')
        })
        self.lock = threading.Lock()
        self.slow_query_threshold = 2.0  # 2 seconds - increased from 1.0 to reduce noise
    
    def record_query(self, query, duration, params=None):
        """Record query execution statistics."""
        with self.lock:
            # Normalize query for statistics
            normalized_query = self._normalize_query(query)
            
            stats = self.query_stats[normalized_query]
            stats['count'] += 1
            stats['total_time'] += duration
            stats['avg_time'] = stats['total_time'] / stats['count']
            stats['max_time'] = max(stats['max_time'], duration)
            stats['min_time'] = min(stats['min_time'], duration)
            
            # Record slow queries
            if duration > self.slow_query_threshold:
                self.slow_queries.append({
                    'query': query,
                    'duration': duration,
                    'params': params,
                    'timestamp': datetime.utcnow(),
                    'endpoint': getattr(request, 'endpoint', None) if request else None
                })
                
                logger.debug(f"Slow query detected: {duration:.3f}s - {query[:100]}...")  # Changed to debug level
    
    def _normalize_query(self, query):
        """Normalize query for statistics grouping."""
        # Remove parameter values and normalize whitespace
        import re
        
        # Replace parameter placeholders
        normalized = re.sub(r'\$\d+|\?|%\([^)]+\)s', '?', str(query))
        
        # Replace quoted strings and numbers
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        
        # Normalize whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def get_slow_queries(self, limit=50):
        """Get recent slow queries."""
        with self.lock:
            return list(self.slow_queries)[-limit:]
    
    def get_query_stats(self, limit=20):
        """Get query statistics sorted by total time."""
        with self.lock:
            sorted_stats = sorted(
                self.query_stats.items(),
                key=lambda x: x[1]['total_time'],
                reverse=True
            )
            return sorted_stats[:limit]
    
    def reset_stats(self):
        """Reset all statistics."""
        with self.lock:
            self.slow_queries.clear()
            self.query_stats.clear()


class ConnectionPoolMonitor:
    """Monitor database connection pool performance."""
    
    def __init__(self):
        self.pool_stats = {
            'connections_created': 0,
            'connections_closed': 0,
            'connections_checked_out': 0,
            'connections_checked_in': 0,
            'pool_overflows': 0,
            'connection_errors': 0
        }
        self.lock = threading.Lock()
    
    def record_connection_created(self):
        """Record connection creation."""
        with self.lock:
            self.pool_stats['connections_created'] += 1
    
    def record_connection_closed(self):
        """Record connection closure."""
        with self.lock:
            self.pool_stats['connections_closed'] += 1
    
    def record_checkout(self):
        """Record connection checkout."""
        with self.lock:
            self.pool_stats['connections_checked_out'] += 1
    
    def record_checkin(self):
        """Record connection checkin."""
        with self.lock:
            self.pool_stats['connections_checked_in'] += 1
    
    def record_overflow(self):
        """Record pool overflow."""
        with self.lock:
            self.pool_stats['pool_overflows'] += 1
    
    def record_error(self):
        """Record connection error."""
        with self.lock:
            self.pool_stats['connection_errors'] += 1
    
    def get_stats(self):
        """Get current pool statistics."""
        with self.lock:
            return self.pool_stats.copy()


# Global monitors
query_monitor = QueryPerformanceMonitor()
pool_monitor = ConnectionPoolMonitor()


def setup_performance_monitoring(app):
    """Set up database performance monitoring."""
    
    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Record query start time."""
        context._query_start_time = time.time()
    
    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Record query completion and performance."""
        if hasattr(context, '_query_start_time'):
            duration = time.time() - context._query_start_time
            query_monitor.record_query(statement, duration, parameters)
    
    @event.listens_for(Pool, "connect")
    def pool_connect(dbapi_conn, connection_record):
        """Record pool connection creation."""
        pool_monitor.record_connection_created()
    
    @event.listens_for(Pool, "checkout")
    def pool_checkout(dbapi_conn, connection_record, connection_proxy):
        """Record pool connection checkout."""
        pool_monitor.record_checkout()
    
    @event.listens_for(Pool, "checkin")
    def pool_checkin(dbapi_conn, connection_record):
        """Record pool connection checkin."""
        pool_monitor.record_checkin()
    
    @event.listens_for(Pool, "close")
    def pool_close(dbapi_conn, connection_record):
        """Record pool connection closure."""
        pool_monitor.record_connection_closed()
    
    logger.info("Database performance monitoring enabled")


class DatabaseIndexManager:
    """Manage database indexes for optimal performance."""
    
    @staticmethod
    def create_recommended_indexes():
        """Create recommended indexes for better performance."""
        indexes = [
            # Reports table indexes
            {
                'table': 'reports',
                'name': 'idx_reports_user_status',
                'columns': ['user_email', 'status'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_reports_user_status ON reports(user_email, status)'
            },
            {
                'table': 'reports',
                'name': 'idx_reports_created_at',
                'columns': ['created_at'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC)'
            },
            {
                'table': 'reports',
                'name': 'idx_reports_type_status',
                'columns': ['type', 'status'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_reports_type_status ON reports(type, status)'
            },
            
            # Audit logs indexes
            {
                'table': 'audit_logs',
                'name': 'idx_audit_timestamp_user',
                'columns': ['timestamp', 'user_email'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_audit_timestamp_user ON audit_logs(timestamp DESC, user_email)'
            },
            {
                'table': 'audit_logs',
                'name': 'idx_audit_entity',
                'columns': ['entity_type', 'entity_id'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id)'
            },
            
            # API usage indexes
            {
                'table': 'api_usage',
                'name': 'idx_api_usage_timestamp',
                'columns': ['timestamp'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp DESC)'
            },
            {
                'table': 'api_usage',
                'name': 'idx_api_usage_key_timestamp',
                'columns': ['api_key_id', 'timestamp'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_api_usage_key_timestamp ON api_usage(api_key_id, timestamp DESC)'
            },
            
            # Notifications indexes
            {
                'table': 'notifications',
                'name': 'idx_notifications_user_read',
                'columns': ['user_email', 'read'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_email, read)'
            },
            {
                'table': 'notifications',
                'name': 'idx_notifications_created_at',
                'columns': ['created_at'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC)'
            },
            
            # Users table indexes
            {
                'table': 'users',
                'name': 'idx_users_status_role',
                'columns': ['status', 'role'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_users_status_role ON users(status, role)'
            },
            
            # SAT reports indexes
            {
                'table': 'sat_reports',
                'name': 'idx_sat_reports_report_id',
                'columns': ['report_id'],
                'sql': 'CREATE INDEX IF NOT EXISTS idx_sat_reports_report_id ON sat_reports(report_id)'
            }
        ]
        
        created_indexes = []
        failed_indexes = []
        
        for index in indexes:
            try:
                # Check if table exists
                inspector = db.inspect(db.engine)
                if index['table'] not in inspector.get_table_names():
                    continue
                
                # Check if index already exists
                existing_indexes = inspector.get_indexes(index['table'])
                index_exists = any(
                    idx['name'] == index['name'] for idx in existing_indexes
                )
                
                if not index_exists:
                    with db.engine.connect() as conn:
                        conn.execute(text(index['sql']))
                        conn.commit()
                    created_indexes.append(index['name'])
                    logger.info(f"Created index: {index['name']}")
                else:
                    logger.info(f"Index already exists: {index['name']}")
                    
            except Exception as e:
                failed_indexes.append((index['name'], str(e)))
                logger.error(f"Failed to create index {index['name']}: {e}")
        
        return created_indexes, failed_indexes
    
    @staticmethod
    def analyze_missing_indexes():
        """Analyze database for missing indexes."""
        suggestions = []
        
        try:
            inspector = db.inspect(db.engine)
            
            # Analyze each table
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                indexes = inspector.get_indexes(table_name)
                foreign_keys = inspector.get_foreign_keys(table_name)
                
                indexed_columns = set()
                for index in indexes:
                    indexed_columns.update(index['column_names'])
                
                # Check foreign key columns
                for fk in foreign_keys:
                    for col in fk['constrained_columns']:
                        if col not in indexed_columns:
                            suggestions.append({
                                'table': table_name,
                                'column': col,
                                'type': 'foreign_key',
                                'reason': 'Foreign key column should be indexed'
                            })
                
                # Check common query patterns
                common_patterns = {
                    'reports': ['user_email', 'status', 'created_at', 'type'],
                    'audit_logs': ['timestamp', 'user_email', 'entity_type'],
                    'notifications': ['user_email', 'read', 'created_at'],
                    'api_usage': ['timestamp', 'api_key_id'],
                    'users': ['status', 'role', 'email']
                }
                
                if table_name in common_patterns:
                    for col in common_patterns[table_name]:
                        if col not in indexed_columns:
                            # Check if column exists
                            column_names = [c['name'] for c in columns]
                            if col in column_names:
                                suggestions.append({
                                    'table': table_name,
                                    'column': col,
                                    'type': 'query_pattern',
                                    'reason': f'Frequently queried column: {col}'
                                })
        
        except Exception as e:
            logger.error(f"Failed to analyze missing indexes: {e}")
        
        return suggestions


class QueryOptimizer:
    """Optimize database queries for better performance."""
    
    def __init__(self):
        self.optimization_rules = [
            self._check_missing_where_clause,
            self._check_select_star,
            self._check_order_by_without_limit,
            self._check_subquery_to_join,
            self._check_missing_indexes,
            self._check_inefficient_joins,
            self._check_function_in_where,
            self._check_like_patterns,
            self._check_or_conditions,
            self._check_distinct_usage
        ]
    
    def optimize_common_queries(self):
        """Optimize common query patterns."""
        optimizations = []
        
        try:
            # Analyze query patterns from monitor
            query_stats = query_monitor.get_query_stats(50)
            
            for query, stats in query_stats:
                if stats['avg_time'] > 0.5:  # Queries taking more than 500ms
                    optimization = self._analyze_query(query, stats)
                    if optimization:
                        optimizations.append(optimization)
        
        except Exception as e:
            logger.error(f"Failed to optimize queries: {e}")
        
        return optimizations
    
    def _analyze_query(self, query, stats):
        """Analyze a query and provide optimization suggestions."""
        suggestions = []
        query_lower = query.lower()
        
        # Apply all optimization rules
        for rule in self.optimization_rules:
            try:
                rule_suggestions = rule(query_lower, stats)
                if rule_suggestions:
                    suggestions.extend(rule_suggestions)
            except Exception as e:
                logger.error(f"Error applying optimization rule: {e}")
        
        if suggestions:
            return {
                'query': query[:200] + '...' if len(query) > 200 else query,
                'avg_time': stats['avg_time'],
                'max_time': stats['max_time'],
                'count': stats['count'],
                'total_time': stats['total_time'],
                'suggestions': suggestions,
                'priority': self._calculate_priority(stats, suggestions)
            }
        
        return None
    
    def _calculate_priority(self, stats, suggestions):
        """Calculate optimization priority based on impact."""
        # High priority: slow queries with high frequency
        if stats['avg_time'] > 2.0 and stats['count'] > 100:
            return 'high'
        elif stats['avg_time'] > 1.0 and stats['count'] > 50:
            return 'medium'
        elif stats['total_time'] > 60:  # Total time > 1 minute
            return 'medium'
        else:
            return 'low'
    
    def _check_missing_where_clause(self, query, stats):
        """Check for queries without WHERE clauses."""
        suggestions = []
        
        if 'select' in query and 'where' not in query and 'limit' not in query:
            # Check if it's a simple count or aggregate
            if not any(agg in query for agg in ['count(', 'sum(', 'avg(', 'max(', 'min(']):
                suggestions.append({
                    'type': 'missing_where',
                    'severity': 'high',
                    'description': 'Query lacks WHERE clause and may return excessive data',
                    'recommendation': 'Add WHERE clause to filter results or add LIMIT'
                })
        
        return suggestions
    
    def _check_select_star(self, query, stats):
        """Check for SELECT * usage."""
        suggestions = []
        
        if 'select *' in query:
            suggestions.append({
                'type': 'select_star',
                'severity': 'medium',
                'description': 'Using SELECT * retrieves all columns, potentially unnecessary data',
                'recommendation': 'Select only the columns you need'
            })
        
        return suggestions
    
    def _check_order_by_without_limit(self, query, stats):
        """Check for ORDER BY without LIMIT."""
        suggestions = []
        
        if 'order by' in query and 'limit' not in query:
            suggestions.append({
                'type': 'order_without_limit',
                'severity': 'medium',
                'description': 'ORDER BY without LIMIT sorts entire result set',
                'recommendation': 'Add LIMIT clause if you only need top N results'
            })
        
        return suggestions
    
    def _check_subquery_to_join(self, query, stats):
        """Check for subqueries that could be JOINs."""
        suggestions = []
        
        select_count = query.count('select')
        if select_count > 1:
            # Check for correlated subqueries
            if 'where' in query and ('in (' in query or 'exists (' in query):
                suggestions.append({
                    'type': 'subquery_to_join',
                    'severity': 'medium',
                    'description': 'Subqueries can often be converted to JOINs for better performance',
                    'recommendation': 'Consider rewriting subqueries as JOINs'
                })
        
        return suggestions
    
    def _check_missing_indexes(self, query, stats):
        """Check for potential missing indexes."""
        suggestions = []
        
        # Look for WHERE clauses on unindexed columns
        common_unindexed_patterns = [
            'where user_email =',
            'where status =',
            'where created_at >',
            'where created_at <',
            'where type =',
            'where timestamp >'
        ]
        
        for pattern in common_unindexed_patterns:
            if pattern in query:
                suggestions.append({
                    'type': 'missing_index',
                    'severity': 'high',
                    'description': f'Query may benefit from index on filtered column',
                    'recommendation': f'Consider adding index for pattern: {pattern}'
                })
                break  # Only suggest once per query
        
        return suggestions
    
    def _check_inefficient_joins(self, query, stats):
        """Check for inefficient JOIN patterns."""
        suggestions = []
        
        if 'join' in query:
            # Check for Cartesian products
            if query.count('join') > 1 and 'on' not in query:
                suggestions.append({
                    'type': 'cartesian_product',
                    'severity': 'high',
                    'description': 'Potential Cartesian product in JOIN',
                    'recommendation': 'Ensure all JOINs have proper ON conditions'
                })
            
            # Check for multiple JOINs without proper indexing hints
            join_count = query.count('join')
            if join_count > 3:
                suggestions.append({
                    'type': 'complex_joins',
                    'severity': 'medium',
                    'description': f'Query has {join_count} JOINs which may be complex',
                    'recommendation': 'Ensure all JOIN columns are properly indexed'
                })
        
        return suggestions
    
    def _check_function_in_where(self, query, stats):
        """Check for functions in WHERE clauses."""
        suggestions = []
        
        function_patterns = ['upper(', 'lower(', 'substring(', 'date(', 'year(', 'month(']
        
        for pattern in function_patterns:
            if f'where {pattern}' in query or f'and {pattern}' in query:
                suggestions.append({
                    'type': 'function_in_where',
                    'severity': 'medium',
                    'description': 'Functions in WHERE clause prevent index usage',
                    'recommendation': 'Consider functional indexes or restructure query'
                })
                break
        
        return suggestions
    
    def _check_like_patterns(self, query, stats):
        """Check for inefficient LIKE patterns."""
        suggestions = []
        
        if 'like' in query:
            # Check for leading wildcards
            if "like '%%" in query or "like '%" in query:
                suggestions.append({
                    'type': 'leading_wildcard',
                    'severity': 'high',
                    'description': 'LIKE with leading wildcard prevents index usage',
                    'recommendation': 'Avoid leading wildcards or consider full-text search'
                })
        
        return suggestions
    
    def _check_or_conditions(self, query, stats):
        """Check for OR conditions that might be inefficient."""
        suggestions = []
        
        or_count = query.count(' or ')
        if or_count > 2:
            suggestions.append({
                'type': 'multiple_or',
                'severity': 'medium',
                'description': f'Query has {or_count} OR conditions which may be inefficient',
                'recommendation': 'Consider using UNION or IN clause instead of multiple ORs'
            })
        
        return suggestions
    
    def _check_distinct_usage(self, query, stats):
        """Check for potentially unnecessary DISTINCT usage."""
        suggestions = []
        
        if 'distinct' in query and 'group by' not in query:
            suggestions.append({
                'type': 'distinct_usage',
                'severity': 'low',
                'description': 'DISTINCT may be unnecessary if data is already unique',
                'recommendation': 'Verify if DISTINCT is needed or if proper JOINs can eliminate duplicates'
            })
        
        return suggestions
    
    def generate_optimization_report(self):
        """Generate comprehensive optimization report."""
        try:
            optimizations = self.optimize_common_queries()
            
            # Group by priority
            high_priority = [opt for opt in optimizations if opt['priority'] == 'high']
            medium_priority = [opt for opt in optimizations if opt['priority'] == 'medium']
            low_priority = [opt for opt in optimizations if opt['priority'] == 'low']
            
            # Calculate potential impact
            total_time_saved = sum(opt['total_time'] for opt in high_priority)
            
            report = {
                'generated_at': datetime.utcnow().isoformat(),
                'total_queries_analyzed': len(optimizations),
                'high_priority_optimizations': len(high_priority),
                'medium_priority_optimizations': len(medium_priority),
                'low_priority_optimizations': len(low_priority),
                'estimated_time_savings': f"{total_time_saved:.2f} seconds",
                'optimizations': {
                    'high_priority': high_priority[:10],  # Top 10
                    'medium_priority': medium_priority[:10],
                    'low_priority': low_priority[:5]
                },
                'recommendations': self._generate_general_recommendations(optimizations)
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate optimization report: {e}")
            return {'error': str(e)}
    
    def _generate_general_recommendations(self, optimizations):
        """Generate general database optimization recommendations."""
        recommendations = []
        
        # Analyze common issues
        issue_counts = {}
        for opt in optimizations:
            for suggestion in opt['suggestions']:
                issue_type = suggestion['type']
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        # Generate recommendations based on common issues
        if issue_counts.get('missing_index', 0) > 5:
            recommendations.append({
                'category': 'indexing',
                'priority': 'high',
                'description': 'Multiple queries would benefit from additional indexes',
                'action': 'Run index analysis and create recommended indexes'
            })
        
        if issue_counts.get('select_star', 0) > 3:
            recommendations.append({
                'category': 'query_structure',
                'priority': 'medium',
                'description': 'Many queries use SELECT *, which retrieves unnecessary data',
                'action': 'Review queries and select only needed columns'
            })
        
        if issue_counts.get('missing_where', 0) > 2:
            recommendations.append({
                'category': 'query_structure',
                'priority': 'high',
                'description': 'Queries without WHERE clauses may return excessive data',
                'action': 'Add appropriate WHERE clauses or LIMIT statements'
            })
        
        return recommendations


class DatabaseCacheManager:
    """Manage database query result caching."""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = {}
        self.default_ttl = 300  # 5 minutes
        self.max_cache_size = 1000
        self.lock = threading.Lock()
    
    def get(self, key):
        """Get cached result."""
        with self.lock:
            if key in self.cache:
                # Check TTL
                if key in self.cache_ttl:
                    if time.time() > self.cache_ttl[key]:
                        del self.cache[key]
                        del self.cache_ttl[key]
                        return None
                
                return self.cache[key]
            
            return None
    
    def set(self, key, value, ttl=None):
        """Set cached result."""
        with self.lock:
            # Implement LRU eviction if cache is full
            if len(self.cache) >= self.max_cache_size:
                # Remove oldest entry
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                if oldest_key in self.cache_ttl:
                    del self.cache_ttl[oldest_key]
            
            self.cache[key] = value
            
            if ttl is None:
                ttl = self.default_ttl
            
            self.cache_ttl[key] = time.time() + ttl
    
    def invalidate(self, pattern=None):
        """Invalidate cache entries."""
        with self.lock:
            if pattern is None:
                self.cache.clear()
                self.cache_ttl.clear()
            else:
                # Remove entries matching pattern
                keys_to_remove = [
                    key for key in self.cache.keys()
                    if pattern in key
                ]
                
                for key in keys_to_remove:
                    del self.cache[key]
                    if key in self.cache_ttl:
                        del self.cache_ttl[key]
    
    def get_stats(self):
        """Get cache statistics."""
        with self.lock:
            return {
                'size': len(self.cache),
                'max_size': self.max_cache_size,
                'hit_rate': getattr(self, '_hit_rate', 0),
                'entries': list(self.cache.keys())[:10]  # Show first 10 keys
            }


# Global cache manager
cache_manager = DatabaseCacheManager()


def cached_query(ttl=300, key_func=None):
    """Decorator for caching database query results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute query and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


class DatabaseMaintenanceManager:
    """Manage database maintenance tasks."""
    
    @staticmethod
    def vacuum_database():
        """Vacuum database to reclaim space and update statistics."""
        try:
            db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
            
            if 'sqlite' in db_uri:
                # SQLite VACUUM
                with db.engine.connect() as conn:
                    conn.execute(text('VACUUM'))
                    conn.commit()
                logger.info("SQLite database vacuumed")
                
            elif 'postgresql' in db_uri:
                # PostgreSQL VACUUM ANALYZE
                with db.engine.connect() as conn:
                    conn.execute(text('VACUUM ANALYZE'))
                    conn.commit()
                logger.info("PostgreSQL database vacuumed and analyzed")
                
            return True
            
        except Exception as e:
            logger.error(f"Database vacuum failed: {e}")
            return False
    
    @staticmethod
    def update_statistics():
        """Update database statistics for query optimization."""
        try:
            db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
            
            if 'postgresql' in db_uri:
                # PostgreSQL ANALYZE
                with db.engine.connect() as conn:
                    conn.execute(text('ANALYZE'))
                    conn.commit()
                logger.info("PostgreSQL statistics updated")
                
            elif 'sqlite' in db_uri:
                # SQLite ANALYZE
                with db.engine.connect() as conn:
                    conn.execute(text('ANALYZE'))
                    conn.commit()
                logger.info("SQLite statistics updated")
                
            return True
            
        except Exception as e:
            logger.error(f"Statistics update failed: {e}")
            return False
    
    @staticmethod
    def cleanup_old_records():
        """Clean up old records based on retention policies."""
        try:
            cleanup_count = 0
            
            # Clean up old audit logs (keep 1 year)
            cutoff_date = datetime.utcnow() - timedelta(days=365)
            
            from api.security import APIUsage
            from security.audit import AuditLog
            
            # Clean audit logs
            old_audits = AuditLog.query.filter(AuditLog.timestamp < cutoff_date).count()
            if old_audits > 0:
                AuditLog.query.filter(AuditLog.timestamp < cutoff_date).delete()
                cleanup_count += old_audits
                logger.info(f"Cleaned up {old_audits} old audit log entries")
            
            # Clean API usage logs (keep 90 days)
            api_cutoff = datetime.utcnow() - timedelta(days=90)
            old_api_usage = APIUsage.query.filter(APIUsage.timestamp < api_cutoff).count()
            if old_api_usage > 0:
                APIUsage.query.filter(APIUsage.timestamp < api_cutoff).delete()
                cleanup_count += old_api_usage
                logger.info(f"Cleaned up {old_api_usage} old API usage entries")
            
            db.session.commit()
            
            return cleanup_count
            
        except Exception as e:
            logger.error(f"Record cleanup failed: {e}")
            db.session.rollback()
            return 0


def init_database_performance(app):
    """Initialize database performance optimizations."""
    
    # Set up performance monitoring
    setup_performance_monitoring(app)
    
    # Set up advanced query analysis
    try:
        from .query_analyzer import setup_query_analysis
        setup_query_analysis(app)
        logger.info("Query analysis monitoring enabled")
    except ImportError as e:
        logger.warning(f"Query analyzer not available: {e}")
    
    # Initialize query result caching with Redis
    cache_manager = None

    try:
        from .query_cache import init_query_cache
        from models import db
        
        # Get Redis client from app cache if available
        redis_client = getattr(app, 'cache', None)
        if redis_client and hasattr(redis_client, 'redis_client'):
            cache_manager = init_query_cache(redis_client.redis_client, db)
            logger.info("Query result caching initialized with Redis")
        else:
            logger.debug("Query caching disabled (Redis not available)")
    except ImportError as e:
        logger.warning(f"Query cache not available: {e}")
    
    # Create recommended indexes
    with app.app_context():
        try:
            created, failed = DatabaseIndexManager.create_recommended_indexes()
            if created:
                logger.info(f"Created {len(created)} database indexes")
            if failed:
                logger.warning(f"Failed to create {len(failed)} indexes")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
    
    # Set up cache invalidation hooks
    @event.listens_for(db.session, 'after_commit')
    def invalidate_cache_after_commit(session):
        """Invalidate relevant cache entries after database commits."""
        if cache_manager is not None:
            cache_manager.invalidate()
    
    logger.info("Database performance optimizations initialized")
