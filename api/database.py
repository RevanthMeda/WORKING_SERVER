"""
Database monitoring and management API endpoints.
"""
from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
from flask_login import current_user

from security.authentication import enhanced_login_required, role_required_api
from database import (
    query_monitor, pool_manager, cache_manager,
    DatabaseIndexManager, QueryOptimizer, DatabaseMaintenanceManager,
    get_pool_metrics, get_query_analyzer
)
from database.backup import backup_manager
from api.errors import APIError

# Create namespace
db_ns = Namespace('database', description='Database monitoring and management')

# Response models
query_stats_model = db_ns.model('QueryStats', {
    'query': fields.String(description='SQL query (normalized)'),
    'count': fields.Integer(description='Number of executions'),
    'total_time': fields.Float(description='Total execution time'),
    'avg_time': fields.Float(description='Average execution time'),
    'max_time': fields.Float(description='Maximum execution time'),
    'min_time': fields.Float(description='Minimum execution time')
})

slow_query_model = db_ns.model('SlowQuery', {
    'query': fields.String(description='SQL query'),
    'duration': fields.Float(description='Execution duration in seconds'),
    'timestamp': fields.DateTime(description='Execution timestamp'),
    'endpoint': fields.String(description='API endpoint that triggered the query')
})

pool_status_model = db_ns.model('PoolStatus', {
    'pool_size': fields.Integer(description='Pool size'),
    'checked_in': fields.Integer(description='Checked in connections'),
    'checked_out': fields.Integer(description='Checked out connections'),
    'overflow': fields.Integer(description='Overflow connections'),
    'utilization': fields.Float(description='Pool utilization percentage'),
    'stats': fields.Raw(description='Additional pool statistics')
})

cache_stats_model = db_ns.model('CacheStats', {
    'size': fields.Integer(description='Current cache size'),
    'max_size': fields.Integer(description='Maximum cache size'),
    'hit_rate': fields.Float(description='Cache hit rate'),
    'entries': fields.List(fields.String, description='Sample cache keys')
})

index_suggestion_model = db_ns.model('IndexSuggestion', {
    'table': fields.String(description='Table name'),
    'column': fields.String(description='Column name'),
    'type': fields.String(description='Suggestion type'),
    'reason': fields.String(description='Reason for suggestion')
})

optimization_model = db_ns.model('QueryOptimization', {
    'query': fields.String(description='Query text'),
    'avg_time': fields.Float(description='Average execution time'),
    'count': fields.Integer(description='Execution count'),
    'suggestions': fields.List(fields.String, description='Optimization suggestions')
})

backup_model = db_ns.model('Backup', {
    'name': fields.String(description='Backup name'),
    'path': fields.String(description='Backup path'),
    'size': fields.Integer(description='Backup size in bytes'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'type': fields.String(description='Backup type'),
    'metadata': fields.Raw(description='Backup metadata')
})

backup_status_model = db_ns.model('BackupStatus', {
    'total_backups': fields.Integer(description='Total number of backups'),
    'total_size': fields.Integer(description='Total size of all backups'),
    'latest_backup': fields.Nested(backup_model, description='Latest backup info'),
    'backup_dir': fields.String(description='Backup directory'),
    'retention_days': fields.Integer(description='Backup retention period'),
    'max_backups': fields.Integer(description='Maximum number of backups'),
    'compression_enabled': fields.Boolean(description='Whether compression is enabled'),
    'scheduler_running': fields.Boolean(description='Whether automatic backups are running')
})


@db_ns.route('/performance')
class DatabasePerformanceResource(Resource):
    """Database performance overview."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get database performance overview."""
        try:
            # Get enhanced query analysis
            analyzer = get_query_analyzer()
            performance_summary = analyzer.get_performance_summary()
            
            # Get legacy query statistics for compatibility
            query_stats = query_monitor.get_query_stats(10)
            slow_queries = query_monitor.get_slow_queries(10)
            
            # Get pool metrics
            pool_metrics = get_pool_metrics()
            
            # Get cache statistics
            cache_stats = cache_manager.get_stats()
            
            return {
                'query_performance': {
                    'summary': performance_summary,
                    'top_queries': [
                        {
                            'query': query[:200] + '...' if len(query) > 200 else query,
                            'count': stats['count'],
                            'total_time': stats['total_time'],
                            'avg_time': stats['avg_time'],
                            'max_time': stats['max_time'],
                            'min_time': stats['min_time']
                        }
                        for query, stats in query_stats
                    ],
                    'slow_queries': [
                        {
                            'query': sq['query'][:200] + '...' if len(sq['query']) > 200 else sq['query'],
                            'duration': sq['duration'],
                            'timestamp': sq['timestamp'].isoformat(),
                            'endpoint': sq['endpoint']
                        }
                        for sq in slow_queries
                    ]
                },
                'connection_pool': pool_metrics,
                'cache': cache_stats
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get performance data: {str(e)}", 500)


@db_ns.route('/queries/slow')
class SlowQueriesResource(Resource):
    """Slow queries analysis."""
    
    @db_ns.marshal_list_with(slow_query_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get slow queries."""
        try:
            limit = request.args.get('limit', 50, type=int)
            slow_queries = query_monitor.get_slow_queries(limit)
            
            return [
                {
                    'query': sq['query'],
                    'duration': sq['duration'],
                    'timestamp': sq['timestamp'],
                    'endpoint': sq['endpoint']
                }
                for sq in slow_queries
            ], 200
            
        except Exception as e:
            raise APIError(f"Failed to get slow queries: {str(e)}", 500)


@db_ns.route('/queries/stats')
class QueryStatsResource(Resource):
    """Query statistics."""
    
    @db_ns.marshal_list_with(query_stats_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get query execution statistics."""
        try:
            limit = request.args.get('limit', 20, type=int)
            query_stats = query_monitor.get_query_stats(limit)
            
            return [
                {
                    'query': query,
                    'count': stats['count'],
                    'total_time': stats['total_time'],
                    'avg_time': stats['avg_time'],
                    'max_time': stats['max_time'],
                    'min_time': stats['min_time']
                }
                for query, stats in query_stats
            ], 200
            
        except Exception as e:
            raise APIError(f"Failed to get query stats: {str(e)}", 500)


@db_ns.route('/pool/status')
class PoolStatusResource(Resource):
    """Connection pool status."""
    
    @db_ns.marshal_with(pool_status_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get connection pool status."""
        try:
            pool_metrics = get_pool_metrics()
            return pool_metrics.get('pool_status', {}), 200
            
        except Exception as e:
            raise APIError(f"Failed to get pool status: {str(e)}", 500)


@db_ns.route('/cache/stats')
class CacheStatsResource(Resource):
    """Cache statistics."""
    
    @db_ns.marshal_with(cache_stats_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get cache statistics."""
        try:
            return cache_manager.get_stats(), 200
            
        except Exception as e:
            raise APIError(f"Failed to get cache stats: {str(e)}", 500)


@db_ns.route('/cache/clear')
class CacheClearResource(Resource):
    """Clear cache."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Clear database cache."""
        try:
            pattern = request.json.get('pattern') if request.is_json else None
            cache_manager.invalidate(pattern)
            
            return {'message': 'Cache cleared successfully'}, 200
            
        except Exception as e:
            raise APIError(f"Failed to clear cache: {str(e)}", 500)


@db_ns.route('/indexes/suggestions')
class IndexSuggestionsResource(Resource):
    """Index optimization suggestions."""
    
    @db_ns.marshal_list_with(index_suggestion_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get index optimization suggestions."""
        try:
            suggestions = DatabaseIndexManager.analyze_missing_indexes()
            return suggestions, 200
            
        except Exception as e:
            raise APIError(f"Failed to get index suggestions: {str(e)}", 500)


@db_ns.route('/indexes/create')
class CreateIndexesResource(Resource):
    """Create recommended indexes."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Create recommended database indexes."""
        try:
            created, failed = DatabaseIndexManager.create_recommended_indexes()
            
            return {
                'created_indexes': created,
                'failed_indexes': [{'name': name, 'error': error} for name, error in failed],
                'message': f'Created {len(created)} indexes, {len(failed)} failed'
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to create indexes: {str(e)}", 500)


@db_ns.route('/optimize/queries')
class QueryOptimizationResource(Resource):
    """Query optimization suggestions."""
    
    @db_ns.marshal_list_with(optimization_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get query optimization suggestions."""
        try:
            optimizations = QueryOptimizer.optimize_common_queries()
            return optimizations, 200
            
        except Exception as e:
            raise APIError(f"Failed to get query optimizations: {str(e)}", 500)


@db_ns.route('/maintenance/vacuum')
class VacuumResource(Resource):
    """Database vacuum operation."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Vacuum database to reclaim space and update statistics."""
        try:
            success = DatabaseMaintenanceManager.vacuum_database()
            
            if success:
                return {'message': 'Database vacuum completed successfully'}, 200
            else:
                return {'message': 'Database vacuum failed'}, 500
                
        except Exception as e:
            raise APIError(f"Failed to vacuum database: {str(e)}", 500)


@db_ns.route('/maintenance/analyze')
class AnalyzeResource(Resource):
    """Database statistics update."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Update database statistics for query optimization."""
        try:
            success = DatabaseMaintenanceManager.update_statistics()
            
            if success:
                return {'message': 'Database statistics updated successfully'}, 200
            else:
                return {'message': 'Statistics update failed'}, 500
                
        except Exception as e:
            raise APIError(f"Failed to update statistics: {str(e)}", 500)


@db_ns.route('/maintenance/cleanup')
class CleanupResource(Resource):
    """Database cleanup operation."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Clean up old records based on retention policies."""
        try:
            cleanup_count = DatabaseMaintenanceManager.cleanup_old_records()
            
            return {
                'message': f'Cleanup completed successfully',
                'records_cleaned': cleanup_count
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to cleanup database: {str(e)}", 500)


@db_ns.route('/health')
class DatabaseHealthResource(Resource):
    """Database health check."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get comprehensive database health status."""
        try:
            from models import db
            
            # Basic connectivity test
            try:
                db.engine.connect().close()
                connectivity = 'healthy'
            except Exception as e:
                connectivity = f'failed: {str(e)}'
            
            # Pool health
            pool_metrics = get_pool_metrics()
            pool_health = pool_metrics.get('health', {})
            
            # Query performance health
            slow_queries = query_monitor.get_slow_queries(10)
            query_health = 'healthy' if len(slow_queries) < 5 else 'warning' if len(slow_queries) < 20 else 'critical'
            
            # Cache health
            cache_stats = cache_manager.get_stats()
            cache_health = 'healthy' if cache_stats['size'] < cache_stats['max_size'] * 0.9 else 'warning'
            
            overall_status = 'healthy'
            if connectivity != 'healthy' or pool_health.get('status') == 'critical':
                overall_status = 'critical'
            elif (query_health in ['warning', 'critical'] or 
                  cache_health == 'warning' or 
                  pool_health.get('status') == 'warning'):
                overall_status = 'warning'
            
            return {
                'overall_status': overall_status,
                'connectivity': connectivity,
                'pool_health': pool_health,
                'query_performance': query_health,
                'cache_health': cache_health,
                'slow_queries_count': len(slow_queries),
                'recommendations': pool_health.get('recommendations', [])
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get database health: {str(e)}", 500)


@db_ns.route('/backup/status')
class BackupStatusResource(Resource):
    """Backup system status."""
    
    @db_ns.marshal_with(backup_status_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get backup system status."""
        try:
            return backup_manager.get_backup_status(), 200
            
        except Exception as e:
            raise APIError(f"Failed to get backup status: {str(e)}", 500)


@db_ns.route('/backup/list')
class BackupListResource(Resource):
    """List available backups."""
    
    @db_ns.marshal_list_with(backup_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """List all available backups."""
        try:
            backups = backup_manager.list_backups()
            return backups, 200
            
        except Exception as e:
            raise APIError(f"Failed to list backups: {str(e)}", 500)


@db_ns.route('/backup/create')
class BackupCreateResource(Resource):
    """Create database backup."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Create a new database backup."""
        try:
            data = request.get_json() or {}
            backup_name = data.get('backup_name')
            include_files = data.get('include_files', True)
            
            result = backup_manager.create_backup(backup_name, include_files)
            
            if result['success']:
                return {
                    'message': 'Backup created successfully',
                    'backup_name': result['backup_name'],
                    'backup_path': result['backup_path'],
                    'size': result['size']
                }, 201
            else:
                return {
                    'message': 'Backup creation failed',
                    'error': result['error']
                }, 500
                
        except Exception as e:
            raise APIError(f"Failed to create backup: {str(e)}", 500)


@db_ns.route('/backup/restore/<string:backup_name>')
class BackupRestoreResource(Resource):
    """Restore database from backup."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self, backup_name):
        """Restore database from specified backup."""
        try:
            data = request.get_json() or {}
            restore_files = data.get('restore_files', True)
            
            result = backup_manager.restore_backup(backup_name, restore_files)
            
            if result['success']:
                return {
                    'message': 'Backup restored successfully',
                    'backup_name': result['backup_name'],
                    'metadata': result['metadata']
                }, 200
            else:
                return {
                    'message': 'Backup restoration failed',
                    'error': result['error']
                }, 500
                
        except Exception as e:
            raise APIError(f"Failed to restore backup: {str(e)}", 500)


@db_ns.route('/backup/delete/<string:backup_name>')
class BackupDeleteResource(Resource):
    """Delete backup."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def delete(self, backup_name):
        """Delete specified backup."""
        try:
            success = backup_manager.delete_backup(backup_name)
            
            if success:
                return {'message': f'Backup {backup_name} deleted successfully'}, 200
            else:
                return {'message': f'Failed to delete backup {backup_name}'}, 500
                
        except Exception as e:
            raise APIError(f"Failed to delete backup: {str(e)}", 500)


@db_ns.route('/analysis/summary')
class QueryAnalysisSummaryResource(Resource):
    """Enhanced query analysis summary."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get comprehensive query performance summary."""
        try:
            analyzer = get_query_analyzer()
            summary = analyzer.get_performance_summary()
            
            return summary, 200
            
        except Exception as e:
            raise APIError(f"Failed to get query analysis summary: {str(e)}", 500)


@db_ns.route('/analysis/slow-queries')
class SlowQueryAnalysisResource(Resource):
    """Enhanced slow query analysis."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get detailed slow query analysis."""
        try:
            limit = request.args.get('limit', 20, type=int)
            analyzer = get_query_analyzer()
            slow_queries = analyzer.get_slow_queries(limit)
            
            return slow_queries, 200
            
        except Exception as e:
            raise APIError(f"Failed to get slow query analysis: {str(e)}", 500)


@db_ns.route('/analysis/trends')
class QueryTrendsResource(Resource):
    """Query performance trends."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get query performance trends over time."""
        try:
            hours = request.args.get('hours', 24, type=int)
            analyzer = get_query_analyzer()
            trends = analyzer.get_query_trends(hours)
            
            return trends, 200
            
        except Exception as e:
            raise APIError(f"Failed to get query trends: {str(e)}", 500)


@db_ns.route('/analysis/tables')
class TablePerformanceResource(Resource):
    """Table performance analysis."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get performance analysis by table."""
        try:
            analyzer = get_query_analyzer()
            table_performance = analyzer.get_table_performance()
            
            return table_performance, 200
            
        except Exception as e:
            raise APIError(f"Failed to get table performance: {str(e)}", 500)


@db_ns.route('/analysis/recommendations')
class OptimizationRecommendationsResource(Resource):
    """Database optimization recommendations."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get comprehensive optimization recommendations."""
        try:
            analyzer = get_query_analyzer()
            recommendations = analyzer.generate_optimization_recommendations()
            
            return recommendations, 200
            
        except Exception as e:
            raise APIError(f"Failed to get optimization recommendations: {str(e)}", 500)


@db_ns.route('/analysis/reset')
class ResetAnalysisResource(Resource):
    """Reset query analysis metrics."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Reset all query analysis metrics."""
        try:
            analyzer = get_query_analyzer()
            analyzer.reset_metrics()
            
            return {'message': 'Query analysis metrics reset successfully'}, 200
            
        except Exception as e:
            raise APIError(f"Failed to reset analysis metrics: {str(e)}", 500)
