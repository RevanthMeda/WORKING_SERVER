"""
Database performance monitoring API endpoints.
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from database.performance import (
    query_monitor, pool_monitor, QueryOptimizer,
    DatabaseIndexManager, DatabaseMaintenanceManager
)
from database.pooling import pool_manager
from database.query_cache import get_cache_manager
from models import db
from security.audit import log_audit_event

logger = logging.getLogger(__name__)

db_performance_bp = Blueprint('db_performance', __name__, url_prefix='/api/v1/database')


def require_admin():
    """Decorator to require admin role."""
    def decorator(f):
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != 'Admin':
                return jsonify({'error': 'Admin access required'}), 403
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


@db_performance_bp.route('/performance/overview', methods=['GET'])
@login_required
@require_admin()
def get_performance_overview():
    """Get database performance overview."""
    try:
        # Query performance metrics
        query_stats = query_monitor.get_query_stats(10)
        slow_queries = query_monitor.get_slow_queries(5)
        
        # Connection pool metrics
        pool_stats = pool_monitor.get_stats()
        pool_status = pool_manager.get_pool_status(db.engine)
        pool_health = pool_manager.health_check(db.engine)
        
        # Cache metrics
        cache_manager = get_cache_manager()
        cache_stats = cache_manager.get_cache_stats() if cache_manager else {}
        
        overview = {
            'timestamp': datetime.utcnow().isoformat(),
            'query_performance': {
                'total_queries_monitored': len(query_stats),
                'slow_queries_count': len(slow_queries),
                'average_query_time': sum(stats['avg_time'] for _, stats in query_stats) / len(query_stats) if query_stats else 0,
                'slowest_query_time': max((stats['max_time'] for _, stats in query_stats), default=0),
                'top_slow_queries': [
                    {
                        'query_hash': query[:50] + '...' if len(query) > 50 else query,
                        'avg_time': stats['avg_time'],
                        'max_time': stats['max_time'],
                        'count': stats['count'],
                        'total_time': stats['total_time']
                    }
                    for query, stats in query_stats[:5]
                ]
            },
            'connection_pool': {
                'status': pool_health['status'],
                'pool_size': pool_status.get('pool_size', 0),
                'active_connections': pool_status.get('checked_out', 0),
                'idle_connections': pool_status.get('checked_in', 0),
                'utilization': pool_status.get('utilization', 0),
                'overflow_count': pool_status.get('overflow', 0),
                'total_created': pool_stats.get('connections_created', 0),
                'total_errors': pool_stats.get('connection_errors', 0),
                'issues': pool_health.get('issues', [])
            },
            'query_cache': {
                'enabled': cache_stats.get('enabled', False),
                'available': cache_stats.get('available', False),
                'hit_rate': cache_stats.get('hit_rate', 0),
                'total_requests': cache_stats.get('total_requests', 0),
                'cached_queries': cache_stats.get('cached_queries', 0)
            }
        }
        
        log_audit_event(
            user_email=current_user.email,
            action='view_db_performance',
            entity_type='database',
            details={'endpoint': 'performance_overview'}
        )
        
        return jsonify(overview)
        
    except Exception as e:
        logger.error(f"Error getting performance overview: {e}")
        return jsonify({'error': 'Failed to get performance overview'}), 500


@db_performance_bp.route('/performance/queries', methods=['GET'])
@login_required
@require_admin()
def get_query_performance():
    """Get detailed query performance metrics."""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        query_stats = query_monitor.get_query_stats(limit)
        slow_queries = query_monitor.get_slow_queries(limit)
        
        # Generate optimization recommendations
        optimizer = QueryOptimizer()
        optimizations = optimizer.optimize_common_queries()
        
        response = {
            'timestamp': datetime.utcnow().isoformat(),
            'query_statistics': [
                {
                    'query_hash': query[:100] + '...' if len(query) > 100 else query,
                    'count': stats['count'],
                    'avg_time': round(stats['avg_time'], 3),
                    'max_time': round(stats['max_time'], 3),
                    'min_time': round(stats['min_time'], 3),
                    'total_time': round(stats['total_time'], 3)
                }
                for query, stats in query_stats
            ],
            'slow_queries': [
                {
                    'query': query['query'][:200] + '...' if len(query['query']) > 200 else query['query'],
                    'duration': round(query['duration'], 3),
                    'timestamp': query['timestamp'].isoformat() if query['timestamp'] else None,
                    'endpoint': query.get('endpoint')
                }
                for query in slow_queries
            ],
            'optimizations': [
                {
                    'query': opt['query'],
                    'avg_time': round(opt['avg_time'], 3),
                    'count': opt['count'],
                    'priority': opt['priority'],
                    'suggestions': opt['suggestions']
                }
                for opt in optimizations[:10]  # Top 10 optimizations
            ]
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting query performance: {e}")
        return jsonify({'error': 'Failed to get query performance'}), 500


@db_performance_bp.route('/performance/pool', methods=['GET'])
@login_required
@require_admin()
def get_pool_performance():
    """Get connection pool performance metrics."""
    try:
        pool_status = pool_manager.get_pool_status(db.engine)
        pool_health = pool_manager.health_check(db.engine)
        pool_stats = pool_monitor.get_stats()
        
        # Get optimization recommendations
        recommendations = pool_manager.optimize_pool_settings(db.engine)
        
        response = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': {
                'health': pool_health['status'],
                'pool_size': pool_status.get('pool_size', 0),
                'checked_out': pool_status.get('checked_out', 0),
                'checked_in': pool_status.get('checked_in', 0),
                'overflow': pool_status.get('overflow', 0),
                'invalid': pool_status.get('invalid', 0),
                'utilization': round(pool_status.get('utilization', 0), 2)
            },
            'statistics': {
                'connections_created': pool_stats.get('connections_created', 0),
                'connections_closed': pool_stats.get('connections_closed', 0),
                'connections_checked_out': pool_stats.get('connections_checked_out', 0),
                'connections_checked_in': pool_stats.get('connections_checked_in', 0),
                'pool_overflows': pool_stats.get('pool_overflows', 0),
                'connection_errors': pool_stats.get('connection_errors', 0)
            },
            'issues': pool_health.get('issues', []),
            'recommendations': recommendations
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting pool performance: {e}")
        return jsonify({'error': 'Failed to get pool performance'}), 500


@db_performance_bp.route('/performance/cache', methods=['GET'])
@login_required
@require_admin()
def get_cache_performance():
    """Get query cache performance metrics."""
    try:
        cache_manager = get_cache_manager()
        
        if not cache_manager:
            return jsonify({
                'enabled': False,
                'available': False,
                'message': 'Query cache not initialized'
            })
        
        stats = cache_manager.get_cache_stats()
        
        response = {
            'timestamp': datetime.utcnow().isoformat(),
            'enabled': stats.get('enabled', False),
            'available': stats.get('available', False),
            'statistics': {
                'hit_count': stats.get('hit_count', 0),
                'miss_count': stats.get('miss_count', 0),
                'total_requests': stats.get('total_requests', 0),
                'hit_rate': stats.get('hit_rate', 0),
                'cached_queries': stats.get('cached_queries', 0),
                'default_ttl': stats.get('default_ttl', 0)
            },
            'sample_entries': stats.get('sample_entries', [])
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting cache performance: {e}")
        return jsonify({'error': 'Failed to get cache performance'}), 500


@db_performance_bp.route('/optimization/report', methods=['GET'])
@login_required
@require_admin()
def get_optimization_report():
    """Generate comprehensive optimization report."""
    try:
        optimizer = QueryOptimizer()
        report = optimizer.generate_optimization_report()
        
        log_audit_event(
            user_email=current_user.email,
            action='generate_optimization_report',
            entity_type='database',
            details={'report_type': 'comprehensive'}
        )
        
        return jsonify(report)
        
    except Exception as e:
        logger.error(f"Error generating optimization report: {e}")
        return jsonify({'error': 'Failed to generate optimization report'}), 500


@db_performance_bp.route('/indexes/analyze', methods=['GET'])
@login_required
@require_admin()
def analyze_indexes():
    """Analyze database indexes and provide recommendations."""
    try:
        suggestions = DatabaseIndexManager.analyze_missing_indexes()
        
        response = {
            'timestamp': datetime.utcnow().isoformat(),
            'suggestions': suggestions,
            'total_suggestions': len(suggestions)
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error analyzing indexes: {e}")
        return jsonify({'error': 'Failed to analyze indexes'}), 500


@db_performance_bp.route('/indexes/create', methods=['POST'])
@login_required
@require_admin()
def create_recommended_indexes():
    """Create recommended database indexes."""
    try:
        created, failed = DatabaseIndexManager.create_recommended_indexes()
        
        log_audit_event(
            user_email=current_user.email,
            action='create_database_indexes',
            entity_type='database',
            details={
                'created_count': len(created),
                'failed_count': len(failed),
                'created_indexes': created,
                'failed_indexes': [name for name, _ in failed]
            }
        )
        
        response = {
            'timestamp': datetime.utcnow().isoformat(),
            'created': created,
            'failed': failed,
            'summary': {
                'created_count': len(created),
                'failed_count': len(failed)
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        return jsonify({'error': 'Failed to create indexes'}), 500


@db_performance_bp.route('/maintenance/vacuum', methods=['POST'])
@login_required
@require_admin()
def vacuum_database():
    """Vacuum database to reclaim space and update statistics."""
    try:
        success = DatabaseMaintenanceManager.vacuum_database()
        
        log_audit_event(
            user_email=current_user.email,
            action='vacuum_database',
            entity_type='database',
            details={'success': success}
        )
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'success': success,
            'message': 'Database vacuum completed' if success else 'Database vacuum failed'
        })
        
    except Exception as e:
        logger.error(f"Error vacuuming database: {e}")
        return jsonify({'error': 'Failed to vacuum database'}), 500


@db_performance_bp.route('/maintenance/update-stats', methods=['POST'])
@login_required
@require_admin()
def update_database_statistics():
    """Update database statistics for query optimization."""
    try:
        success = DatabaseMaintenanceManager.update_statistics()
        
        log_audit_event(
            user_email=current_user.email,
            action='update_database_statistics',
            entity_type='database',
            details={'success': success}
        )
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'success': success,
            'message': 'Database statistics updated' if success else 'Statistics update failed'
        })
        
    except Exception as e:
        logger.error(f"Error updating database statistics: {e}")
        return jsonify({'error': 'Failed to update database statistics'}), 500


@db_performance_bp.route('/maintenance/cleanup', methods=['POST'])
@login_required
@require_admin()
def cleanup_old_records():
    """Clean up old records based on retention policies."""
    try:
        cleaned_count = DatabaseMaintenanceManager.cleanup_old_records()
        
        log_audit_event(
            user_email=current_user.email,
            action='cleanup_old_records',
            entity_type='database',
            details={'cleaned_count': cleaned_count}
        )
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'cleaned_count': cleaned_count,
            'message': f'Cleaned up {cleaned_count} old records'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up old records: {e}")
        return jsonify({'error': 'Failed to clean up old records'}), 500


@db_performance_bp.route('/cache/clear', methods=['POST'])
@login_required
@require_admin()
def clear_query_cache():
    """Clear all cached queries."""
    try:
        cache_manager = get_cache_manager()
        
        if not cache_manager:
            return jsonify({'error': 'Query cache not available'}), 400
        
        cleared_count = cache_manager.clear_all_cache()
        
        log_audit_event(
            user_email=current_user.email,
            action='clear_query_cache',
            entity_type='database',
            details={'cleared_count': cleared_count}
        )
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'cleared_count': cleared_count,
            'message': f'Cleared {cleared_count} cached queries'
        })
        
    except Exception as e:
        logger.error(f"Error clearing query cache: {e}")
        return jsonify({'error': 'Failed to clear query cache'}), 500


@db_performance_bp.route('/cache/invalidate', methods=['POST'])
@login_required
@require_admin()
def invalidate_cache():
    """Invalidate specific cache patterns."""
    try:
        data = request.get_json() or {}
        pattern = data.get('pattern')
        table_name = data.get('table_name')
        
        cache_manager = get_cache_manager()
        
        if not cache_manager:
            return jsonify({'error': 'Query cache not available'}), 400
        
        if pattern:
            invalidated_count = cache_manager.query_cache.invalidate(pattern=pattern)
        elif table_name:
            invalidated_count = cache_manager.query_cache.invalidate(table_name=table_name)
        else:
            return jsonify({'error': 'Either pattern or table_name must be provided'}), 400
        
        log_audit_event(
            user_email=current_user.email,
            action='invalidate_cache',
            entity_type='database',
            details={
                'pattern': pattern,
                'table_name': table_name,
                'invalidated_count': invalidated_count
            }
        )
        
        return jsonify({
            'timestamp': datetime.utcnow().isoformat(),
            'invalidated_count': invalidated_count,
            'message': f'Invalidated {invalidated_count} cache entries'
        })
        
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        return jsonify({'error': 'Failed to invalidate cache'}), 500


@db_performance_bp.route('/health', methods=['GET'])
@login_required
@require_admin()
def get_database_health():
    """Get overall database health status."""
    try:
        # Connection pool health
        pool_health = pool_manager.health_check(db.engine)
        
        # Query performance health
        query_stats = query_monitor.get_query_stats(10)
        slow_query_count = len(query_monitor.get_slow_queries(50))
        avg_query_time = sum(stats['avg_time'] for _, stats in query_stats) / len(query_stats) if query_stats else 0
        
        # Cache health
        cache_manager = get_cache_manager()
        cache_available = cache_manager.query_cache.is_available() if cache_manager else False
        cache_hit_rate = cache_manager.get_cache_stats().get('hit_rate', 0) if cache_manager else 0
        
        # Overall health assessment
        health_issues = []
        health_score = 100
        
        # Pool health issues
        if pool_health['status'] == 'critical':
            health_issues.extend(pool_health['issues'])
            health_score -= 30
        elif pool_health['status'] == 'warning':
            health_issues.extend(pool_health['issues'])
            health_score -= 15
        
        # Query performance issues
        if avg_query_time > 2.0:
            health_issues.append(f"High average query time: {avg_query_time:.2f}s")
            health_score -= 20
        
        if slow_query_count > 20:
            health_issues.append(f"High number of slow queries: {slow_query_count}")
            health_score -= 15
        
        # Cache issues
        if not cache_available:
            health_issues.append("Query cache is not available")
            health_score -= 10
        elif cache_hit_rate < 50:
            health_issues.append(f"Low cache hit rate: {cache_hit_rate:.1f}%")
            health_score -= 5
        
        # Determine overall status
        if health_score >= 90:
            overall_status = 'healthy'
        elif health_score >= 70:
            overall_status = 'warning'
        else:
            overall_status = 'critical'
        
        response = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': overall_status,
            'health_score': max(0, health_score),
            'issues': health_issues,
            'components': {
                'connection_pool': {
                    'status': pool_health['status'],
                    'issues': pool_health['issues']
                },
                'query_performance': {
                    'status': 'healthy' if avg_query_time < 1.0 else 'warning' if avg_query_time < 2.0 else 'critical',
                    'avg_query_time': round(avg_query_time, 3),
                    'slow_query_count': slow_query_count
                },
                'query_cache': {
                    'status': 'healthy' if cache_available and cache_hit_rate > 70 else 'warning' if cache_available else 'critical',
                    'available': cache_available,
                    'hit_rate': cache_hit_rate
                }
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting database health: {e}")
        return jsonify({'error': 'Failed to get database health'}), 500
