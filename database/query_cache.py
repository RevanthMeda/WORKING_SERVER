"""
Database query result caching with Redis.
"""

import json
import logging
import time
import hashlib
from functools import wraps
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta

from flask import current_app, g, request
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query

logger = logging.getLogger(__name__)


class QueryCache:
    """Redis-based query result caching system."""
    
    def __init__(self, redis_client=None, default_ttl=300, key_prefix='query_cache:'):
        self.redis_client = redis_client
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.hit_count = 0
        self.miss_count = 0
        self.enabled = True
        
        # Cache invalidation patterns
        self.invalidation_patterns = {
            'reports': ['reports:', 'sat_reports:', 'user_reports:'],
            'users': ['users:', 'user_reports:', 'user_analytics:'],
            'audit_logs': ['audit:', 'user_activity:'],
            'notifications': ['notifications:', 'user_notifications:'],
            'api_usage': ['api_usage:', 'api_stats:'],
            'system_settings': ['settings:', 'config:']
        }
    
    def is_available(self) -> bool:
        """Check if Redis cache is available."""
        if not self.redis_client or not self.enabled:
            return False
        
        try:
            return self.redis_client.is_available()
        except Exception:
            return False
    
    def _generate_cache_key(self, query_hash: str, params_hash: str = '') -> str:
        """Generate cache key for query."""
        key_parts = [self.key_prefix, query_hash]
        if params_hash:
            key_parts.append(params_hash)
        return ''.join(key_parts)
    
    def _hash_query(self, query: Union[str, Query], params: Optional[Dict] = None) -> tuple:
        """Generate hash for query and parameters."""
        # Convert SQLAlchemy Query to string
        if hasattr(query, 'statement'):
            query_str = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
        else:
            query_str = str(query)
        
        # Normalize query string
        normalized_query = ' '.join(query_str.split()).lower()
        query_hash = hashlib.md5(normalized_query.encode()).hexdigest()
        
        # Hash parameters if provided
        params_hash = ''
        if params:
            params_str = json.dumps(params, sort_keys=True, default=str)
            params_hash = hashlib.md5(params_str.encode()).hexdigest()
        
        return query_hash, params_hash
    
    def get(self, query: Union[str, Query], params: Optional[Dict] = None) -> Optional[Any]:
        """Get cached query result."""
        if not self.is_available():
            return None
        
        try:
            query_hash, params_hash = self._hash_query(query, params)
            cache_key = self._generate_cache_key(query_hash, params_hash)
            
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.hit_count += 1
                
                # Deserialize cached data
                if isinstance(cached_data, str):
                    result = json.loads(cached_data)
                else:
                    result = cached_data
                
                logger.debug(f"Cache hit for query: {query_hash[:8]}...")
                return result
            
            self.miss_count += 1
            logger.debug(f"Cache miss for query: {query_hash[:8]}...")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached query result: {e}")
            return None
    
    def set(self, query: Union[str, Query], result: Any, params: Optional[Dict] = None, 
            ttl: Optional[int] = None) -> bool:
        """Cache query result."""
        if not self.is_available():
            return False
        
        try:
            query_hash, params_hash = self._hash_query(query, params)
            cache_key = self._generate_cache_key(query_hash, params_hash)
            
            # Serialize result
            if hasattr(result, '__iter__') and not isinstance(result, (str, bytes)):
                # Handle SQLAlchemy result objects
                if hasattr(result, '_asdict'):
                    serialized_result = [row._asdict() for row in result]
                elif hasattr(result, '__dict__'):
                    serialized_result = [row.__dict__ for row in result if hasattr(row, '__dict__')]
                else:
                    serialized_result = list(result)
            else:
                serialized_result = result
            
            # Set cache with TTL
            cache_ttl = ttl or self.default_ttl
            success = self.redis_client.set(
                cache_key, 
                json.dumps(serialized_result, default=str), 
                cache_ttl
            )
            
            if success:
                logger.debug(f"Cached query result: {query_hash[:8]}... (TTL: {cache_ttl}s)")
            
            return success
            
        except Exception as e:
            logger.error(f"Error caching query result: {e}")
            return False
    
    def invalidate(self, pattern: Optional[str] = None, table_name: Optional[str] = None) -> int:
        """Invalidate cached queries."""
        if not self.is_available():
            return 0
        
        try:
            patterns_to_invalidate = []
            
            if pattern:
                patterns_to_invalidate.append(f"{self.key_prefix}*{pattern}*")
            elif table_name and table_name in self.invalidation_patterns:
                for pattern in self.invalidation_patterns[table_name]:
                    patterns_to_invalidate.append(f"{self.key_prefix}*{pattern}*")
            else:
                # Invalidate all query cache
                patterns_to_invalidate.append(f"{self.key_prefix}*")
            
            deleted_count = 0
            for pattern in patterns_to_invalidate:
                keys = self.redis_client.keys(pattern)
                if keys:
                    deleted_count += self.redis_client.delete(*keys)
            
            logger.info(f"Invalidated {deleted_count} cached queries")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            'enabled': self.enabled,
            'available': self.is_available(),
            'hit_count': self.hit_count,
            'miss_count': self.miss_count,
            'total_requests': total_requests,
            'hit_rate': round(hit_rate, 2),
            'default_ttl': self.default_ttl
        }
        
        if self.is_available():
            try:
                # Get cache size information
                pattern = f"{self.key_prefix}*"
                cache_keys = self.redis_client.keys(pattern)
                stats['cached_queries'] = len(cache_keys)
                
                # Sample some cache entries for analysis
                sample_keys = cache_keys[:10] if cache_keys else []
                sample_info = []
                
                for key in sample_keys:
                    ttl = self.redis_client.ttl(key)
                    size = len(str(self.redis_client.get(key) or ''))
                    sample_info.append({
                        'key': key.replace(self.key_prefix, ''),
                        'ttl': ttl,
                        'size_bytes': size
                    })
                
                stats['sample_entries'] = sample_info
                
            except Exception as e:
                stats['error'] = str(e)
        
        return stats
    
    def clear_all(self) -> int:
        """Clear all cached queries."""
        return self.invalidate()
    
    def enable(self):
        """Enable query caching."""
        self.enabled = True
        logger.info("Query caching enabled")
    
    def disable(self):
        """Disable query caching."""
        self.enabled = False
        logger.info("Query caching disabled")


class CachedQuery:
    """Decorator for caching database queries."""
    
    def __init__(self, cache: QueryCache, ttl: Optional[int] = None, 
                 key_func: Optional[callable] = None, 
                 invalidate_on: Optional[List[str]] = None):
        self.cache = cache
        self.ttl = ttl
        self.key_func = key_func
        self.invalidate_on = invalidate_on or []
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.cache.is_available():
                return func(*args, **kwargs)
            
            # Generate cache key
            if self.key_func:
                cache_key = self.key_func(*args, **kwargs)
            else:
                # Use function name and arguments as key
                key_data = {
                    'func': func.__name__,
                    'args': args,
                    'kwargs': kwargs
                }
                cache_key = f"func:{func.__name__}:{hashlib.md5(str(key_data).encode()).hexdigest()}"
            
            # Try to get from cache
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            self.cache.set(cache_key, result, ttl=self.ttl)
            
            return result
        
        return wrapper


class QueryCacheManager:
    """Manage query caching across the application."""
    
    def __init__(self, redis_client=None):
        self.query_cache = QueryCache(redis_client)
        self.auto_invalidation_enabled = True
        
        # Track table modifications for smart invalidation
        self.table_modifications = {}
        
        # Performance metrics
        self.cache_performance = {
            'total_queries': 0,
            'cached_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_query_time_without_cache': 0,
            'avg_query_time_with_cache': 0,
            'time_saved': 0
        }
    
    def setup_auto_invalidation(self, db):
        """Set up automatic cache invalidation on database changes."""
        if not self.auto_invalidation_enabled:
            return
        
        @event.listens_for(db.session, 'after_commit')
        def invalidate_cache_after_commit(session):
            """Invalidate cache after successful database commits."""
            try:
                # Get modified tables from session
                modified_tables = set()
                
                for obj in session.new:
                    modified_tables.add(obj.__tablename__)
                
                for obj in session.dirty:
                    modified_tables.add(obj.__tablename__)
                
                for obj in session.deleted:
                    modified_tables.add(obj.__tablename__)
                
                # Invalidate cache for modified tables
                for table_name in modified_tables:
                    self.query_cache.invalidate(table_name=table_name)
                    logger.debug(f"Invalidated cache for table: {table_name}")
                
            except Exception as e:
                logger.error(f"Error in auto cache invalidation: {e}")
        
        @event.listens_for(db.session, 'after_rollback')
        def handle_rollback(session):
            """Handle cache invalidation after rollback."""
            # No cache invalidation needed on rollback since changes weren't committed
            logger.debug("Database rollback - no cache invalidation needed")
    
    def cached_query(self, ttl: Optional[int] = None, key_func: Optional[callable] = None,
                    invalidate_on: Optional[List[str]] = None):
        """Decorator for caching query results."""
        return CachedQuery(self.query_cache, ttl, key_func, invalidate_on)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        base_stats = self.query_cache.get_stats()
        
        # Add performance metrics
        base_stats.update({
            'performance': self.cache_performance,
            'auto_invalidation_enabled': self.auto_invalidation_enabled,
            'table_modifications': dict(self.table_modifications)
        })
        
        return base_stats
    
    def invalidate_table_cache(self, table_name: str) -> int:
        """Invalidate cache for specific table."""
        return self.query_cache.invalidate(table_name=table_name)
    
    def clear_all_cache(self) -> int:
        """Clear all cached queries."""
        return self.query_cache.clear_all()


# Global cache manager instance
cache_manager = None


def init_query_cache(redis_client, db=None):
    """Initialize query caching system."""
    global cache_manager
    
    cache_manager = QueryCacheManager(redis_client)
    
    if db:
        cache_manager.setup_auto_invalidation(db)
    
    logger.info("Query cache system initialized")
    return cache_manager


def get_cache_manager() -> Optional[QueryCacheManager]:
    """Get the global cache manager instance."""
    return cache_manager


# Enhanced convenience functions for common caching patterns
def cache_user_reports(user_email: str, ttl: int = 300):
    """Cache user reports query with performance tracking."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            if cache_manager and cache_manager.query_cache.is_available():
                cache_key = f"user_reports:{user_email}"
                cached_result = cache_manager.query_cache.get(cache_key)
                
                if cached_result is not None:
                    # Track cache hit performance
                    cache_time = time.time() - start_time
                    cache_manager.cache_performance['cache_hits'] += 1
                    cache_manager.cache_performance['cached_queries'] += 1
                    cache_manager.cache_performance['avg_query_time_with_cache'] = (
                        (cache_manager.cache_performance['avg_query_time_with_cache'] * 
                         (cache_manager.cache_performance['cache_hits'] - 1) + cache_time) /
                        cache_manager.cache_performance['cache_hits']
                    )
                    return cached_result
                
                # Cache miss - execute query and cache result
                result = func(*args, **kwargs)
                query_time = time.time() - start_time
                
                cache_manager.query_cache.set(cache_key, result, ttl=ttl)
                
                # Track cache miss performance
                cache_manager.cache_performance['cache_misses'] += 1
                cache_manager.cache_performance['total_queries'] += 1
                cache_manager.cache_performance['avg_query_time_without_cache'] = (
                    (cache_manager.cache_performance['avg_query_time_without_cache'] * 
                     (cache_manager.cache_performance['cache_misses'] - 1) + query_time) /
                    cache_manager.cache_performance['cache_misses']
                )
                
                return result
            
            # No cache available
            result = func(*args, **kwargs)
            query_time = time.time() - start_time
            cache_manager.cache_performance['total_queries'] += 1
            
            return result
        return wrapper
    return decorator


def cache_report_details(report_id: str, ttl: int = 600):
    """Cache report details query."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if cache_manager and cache_manager.query_cache.is_available():
                cache_key = f"report_details:{report_id}"
                cached_result = cache_manager.query_cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                result = func(*args, **kwargs)
                cache_manager.query_cache.set(cache_key, result, ttl=ttl)
                return result
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def cache_system_stats(ttl: int = 120):
    """Cache system statistics queries."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if cache_manager and cache_manager.query_cache.is_available():
                cache_key = f"system_stats:{func.__name__}"
                cached_result = cache_manager.query_cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                result = func(*args, **kwargs)
                cache_manager.query_cache.set(cache_key, result, ttl=ttl)
                return result
            
            return func(*args, **kwargs)
        return wrapper
    return decorator