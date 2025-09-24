"""
Monitoring and metrics collection background tasks.
"""
import logging
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta
from celery import current_task
from flask import current_app
from sqlalchemy import text
from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def collect_metrics_task(self) -> Dict[str, Any]:
    """
    Collect system and application metrics.
    
    Returns:
        Dict with collected metrics
    """
    try:
        logger.debug("Collecting system metrics")
        
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'system_metrics': {},
            'application_metrics': {},
            'database_metrics': {},
            'cache_metrics': {}
        }
        
        # Collect system metrics
        try:
            import psutil
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            metrics['system_metrics'] = {
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'memory_total': memory.total,
                'memory_used': memory.used,
                'memory_percent': memory.percent,
                'disk_total': disk.total,
                'disk_used': disk.used,
                'disk_percent': (disk.used / disk.total) * 100
            }
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            metrics['system_metrics']['error'] = str(e)
        
        # Collect application metrics
        try:
            from models import db, Report, User
            
            # Count active reports
            active_reports = Report.query.filter(
                Report.status.in_(['DRAFT', 'PENDING', 'IN_REVIEW'])
            ).count()
            
            # Count total reports
            total_reports = Report.query.count()
            
            # Count active users (logged in within last 24 hours)
            # This would require session tracking - simplified for now
            total_users = User.query.filter_by(status='Active').count()
            
            metrics['application_metrics'] = {
                'active_reports': active_reports,
                'total_reports': total_reports,
                'active_users': total_users,
                'reports_created_today': Report.query.filter(
                    Report.created_at >= datetime.utcnow().date()
                ).count()
            }
            
        except Exception as e:
            logger.error(f"Failed to collect application metrics: {e}")
            metrics['application_metrics']['error'] = str(e)
        
        # Collect database metrics
        try:
            from database.pooling import get_pool_metrics
            from database.query_analyzer import get_query_analyzer
            
            # Pool metrics
            pool_metrics = get_pool_metrics()
            metrics['database_metrics']['pool'] = pool_metrics
            
            # Query performance metrics
            analyzer = get_query_analyzer()
            performance_summary = analyzer.get_performance_summary()
            metrics['database_metrics']['performance'] = performance_summary
            
        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")
            metrics['database_metrics']['error'] = str(e)
        
        # Collect cache metrics
        try:
            from database.query_cache import get_cache_manager
            from cache.redis_client import get_redis_client
            
            # Query cache metrics
            cache_manager = get_cache_manager()
            if cache_manager:
                cache_stats = cache_manager.get_cache_stats()
                metrics['cache_metrics']['query_cache'] = cache_stats
            
            # Redis metrics
            redis_client = get_redis_client()
            if redis_client and redis_client.is_available():
                redis_info = redis_client.get_info()
                metrics['cache_metrics']['redis'] = {
                    'connected_clients': redis_info.get('connected_clients', 0),
                    'used_memory': redis_info.get('used_memory', 0),
                    'keyspace_hits': redis_info.get('keyspace_hits', 0),
                    'keyspace_misses': redis_info.get('keyspace_misses', 0)
                }
            
        except Exception as e:
            logger.error(f"Failed to collect cache metrics: {e}")
            metrics['cache_metrics']['error'] = str(e)
        
        # Store metrics (in production, send to monitoring system)
        try:
            from monitoring.metrics import metrics_collector
            metrics_collector.record_metrics(metrics)
        except Exception as e:
            logger.debug(f"Failed to store metrics: {e}")
        
        return {
            'status': 'success',
            'metrics': metrics,
            'collected_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'collected_at': datetime.utcnow().isoformat()
        }


@celery_app.task(bind=True)
def health_check_task(self) -> Dict[str, Any]:
    """
    Perform comprehensive system health check.
    
    Returns:
        Dict with health check results
    """
    try:
        logger.debug("Performing system health check")
        
        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'healthy',
            'components': {},
            'alerts': []
        }
        
        # Check database health
        try:
            from models import db
            from database.pooling import get_pool_metrics
            
            # Test database connection
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            
            # Check pool health
            pool_metrics = get_pool_metrics()
            pool_health = pool_metrics.get('health', {})
            
            health_status['components']['database'] = {
                'status': pool_health.get('status', 'unknown'),
                'connection_test': 'passed',
                'pool_utilization': pool_metrics.get('pool_status', {}).get('utilization', 0)
            }
            
            # Add alerts for database issues
            if pool_health.get('status') == 'critical':
                health_status['alerts'].append({
                    'component': 'database',
                    'severity': 'critical',
                    'message': 'Database connection pool in critical state'
                })
                health_status['overall_status'] = 'critical'
            elif pool_health.get('status') == 'warning':
                health_status['alerts'].append({
                    'component': 'database',
                    'severity': 'warning',
                    'message': 'Database connection pool issues detected'
                })
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status['components']['database'] = {
                'status': 'critical',
                'error': str(e)
            }
            health_status['alerts'].append({
                'component': 'database',
                'severity': 'critical',
                'message': f'Database health check failed: {str(e)}'
            })
            health_status['overall_status'] = 'critical'
        
        # Check Redis health
        try:
            from cache.redis_client import get_redis_client
            
            redis_client = get_redis_client()
            if redis_client:
                is_available = redis_client.is_available()
                
                health_status['components']['redis'] = {
                    'status': 'healthy' if is_available else 'critical',
                    'available': is_available
                }
                
                if not is_available:
                    health_status['alerts'].append({
                        'component': 'redis',
                        'severity': 'warning',
                        'message': 'Redis connection unavailable'
                    })
                    if health_status['overall_status'] == 'healthy':
                        health_status['overall_status'] = 'warning'
            else:
                health_status['components']['redis'] = {
                    'status': 'not_configured',
                    'available': False
                }
                
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            health_status['components']['redis'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Check disk space
        try:
            import psutil
            disk_usage = psutil.disk_usage('/')
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            
            disk_status = 'healthy'
            if disk_percent > 95:
                disk_status = 'critical'
                health_status['alerts'].append({
                    'component': 'disk',
                    'severity': 'critical',
                    'message': f'Disk usage critical: {disk_percent:.1f}%'
                })
                health_status['overall_status'] = 'critical'
            elif disk_percent > 85:
                disk_status = 'warning'
                health_status['alerts'].append({
                    'component': 'disk',
                    'severity': 'warning',
                    'message': f'Disk usage high: {disk_percent:.1f}%'
                })
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
            
            health_status['components']['disk'] = {
                'status': disk_status,
                'usage_percent': round(disk_percent, 2),
                'free_space_gb': round(disk_usage.free / (1024**3), 2)
            }
            
        except Exception as e:
            logger.error(f"Disk health check failed: {e}")
            health_status['components']['disk'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Check memory usage
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            memory_status = 'healthy'
            if memory_percent > 95:
                memory_status = 'critical'
                health_status['alerts'].append({
                    'component': 'memory',
                    'severity': 'critical',
                    'message': f'Memory usage critical: {memory_percent:.1f}%'
                })
                health_status['overall_status'] = 'critical'
            elif memory_percent > 85:
                memory_status = 'warning'
                health_status['alerts'].append({
                    'component': 'memory',
                    'severity': 'warning',
                    'message': f'Memory usage high: {memory_percent:.1f}%'
                })
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
            
            health_status['components']['memory'] = {
                'status': memory_status,
                'usage_percent': round(memory_percent, 2),
                'available_gb': round(memory.available / (1024**3), 2)
            }
            
        except Exception as e:
            logger.error(f"Memory health check failed: {e}")
            health_status['components']['memory'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Check Celery worker health
        try:
            from .celery_app import get_celery_app
            
            celery_app = get_celery_app()
            if celery_app:
                # Check if workers are active
                inspect = celery_app.control.inspect()
                active_workers = inspect.active()
                
                worker_count = len(active_workers) if active_workers else 0
                
                worker_status = 'healthy' if worker_count > 0 else 'warning'
                
                health_status['components']['celery'] = {
                    'status': worker_status,
                    'active_workers': worker_count,
                    'workers': list(active_workers.keys()) if active_workers else []
                }
                
                if worker_count == 0:
                    health_status['alerts'].append({
                        'component': 'celery',
                        'severity': 'warning',
                        'message': 'No active Celery workers detected'
                    })
                    if health_status['overall_status'] == 'healthy':
                        health_status['overall_status'] = 'warning'
            
        except Exception as e:
            logger.error(f"Celery health check failed: {e}")
            health_status['components']['celery'] = {
                'status': 'error',
                'error': str(e)
            }
        
        # Log health status
        if health_status['overall_status'] == 'critical':
            logger.error(f"System health check: CRITICAL - {len(health_status['alerts'])} alerts")
        elif health_status['overall_status'] == 'warning':
            logger.warning(f"System health check: WARNING - {len(health_status['alerts'])} alerts")
        else:
            logger.debug("System health check: HEALTHY")
        
        return {
            'status': 'success',
            'health_status': health_status
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'health_status': {
                'overall_status': 'critical',
                'timestamp': datetime.utcnow().isoformat(),
                'components': {},
                'alerts': [{
                    'component': 'health_check',
                    'severity': 'critical',
                    'message': f'Health check task failed: {str(e)}'
                }]
            }
        }


@celery_app.task(bind=True)
def performance_analysis_task(self, analysis_period_hours: int = 24) -> Dict[str, Any]:
    """
    Perform comprehensive performance analysis.
    
    Args:
        analysis_period_hours: Period to analyze in hours
    
    Returns:
        Dict with performance analysis results
    """
    try:
        logger.info(f"Starting performance analysis for {analysis_period_hours} hours")
        
        analysis_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'analysis_period_hours': analysis_period_hours,
            'query_performance': {},
            'system_performance': {},
            'recommendations': []
        }
        
        # Analyze query performance
        try:
            from database.query_analyzer import get_query_analyzer
            
            analyzer = get_query_analyzer()
            
            # Get performance summary
            performance_summary = analyzer.get_performance_summary()
            analysis_results['query_performance']['summary'] = performance_summary
            
            # Get slow queries
            slow_queries = analyzer.get_slow_queries(10)
            analysis_results['query_performance']['slow_queries'] = slow_queries
            
            # Get trends
            trends = analyzer.get_query_trends(analysis_period_hours)
            analysis_results['query_performance']['trends'] = trends
            
            # Generate recommendations
            recommendations = analyzer.generate_optimization_recommendations()
            analysis_results['recommendations'].extend(recommendations)
            
        except Exception as e:
            logger.error(f"Query performance analysis failed: {e}")
            analysis_results['query_performance']['error'] = str(e)
        
        # Analyze system performance
        try:
            import psutil
            
            # Get current system metrics
            current_metrics = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': (psutil.disk_usage('/').used / psutil.disk_usage('/').total) * 100
            }
            
            analysis_results['system_performance']['current_metrics'] = current_metrics
            
            # Generate system recommendations
            if current_metrics['cpu_percent'] > 80:
                analysis_results['recommendations'].append({
                    'category': 'system_performance',
                    'priority': 'high',
                    'title': 'High CPU usage detected',
                    'description': f'CPU usage is {current_metrics["cpu_percent"]:.1f}%',
                    'actions': [
                        'Monitor CPU-intensive processes',
                        'Consider scaling up or optimizing application code',
                        'Review database query performance'
                    ]
                })
            
            if current_metrics['memory_percent'] > 80:
                analysis_results['recommendations'].append({
                    'category': 'system_performance',
                    'priority': 'high',
                    'title': 'High memory usage detected',
                    'description': f'Memory usage is {current_metrics["memory_percent"]:.1f}%',
                    'actions': [
                        'Monitor memory-intensive processes',
                        'Consider increasing available memory',
                        'Review application memory leaks'
                    ]
                })
            
            if current_metrics['disk_percent'] > 85:
                analysis_results['recommendations'].append({
                    'category': 'system_performance',
                    'priority': 'medium',
                    'title': 'High disk usage detected',
                    'description': f'Disk usage is {current_metrics["disk_percent"]:.1f}%',
                    'actions': [
                        'Clean up old files and logs',
                        'Archive old data',
                        'Consider increasing disk space'
                    ]
                })
            
        except Exception as e:
            logger.error(f"System performance analysis failed: {e}")
            analysis_results['system_performance']['error'] = str(e)
        
        logger.info(f"Performance analysis completed with {len(analysis_results['recommendations'])} recommendations")
        
        return {
            'status': 'success',
            'analysis_results': analysis_results
        }
        
    except Exception as e:
        logger.error(f"Performance analysis failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'analysis_period_hours': analysis_period_hours
        }


@celery_app.task(bind=True)
def generate_monitoring_report_task(self, report_type: str = 'daily') -> Dict[str, Any]:
    """
    Generate comprehensive monitoring report.
    
    Args:
        report_type: Type of report ('daily', 'weekly', 'monthly')
    
    Returns:
        Dict with monitoring report
    """
    try:
        logger.info(f"Generating {report_type} monitoring report")
        
        # Determine time period
        if report_type == 'daily':
            hours = 24
        elif report_type == 'weekly':
            hours = 24 * 7
        elif report_type == 'monthly':
            hours = 24 * 30
        else:
            hours = 24
        
        report = {
            'report_type': report_type,
            'period_hours': hours,
            'generated_at': datetime.utcnow().isoformat(),
            'summary': {},
            'detailed_metrics': {},
            'alerts_summary': {},
            'recommendations': []
        }
        
        # Collect current metrics
        metrics_result = collect_metrics_task.apply_async()
        metrics_data = metrics_result.get(timeout=60)
        
        if metrics_data.get('status') == 'success':
            report['detailed_metrics'] = metrics_data['metrics']
        
        # Perform health check
        health_result = health_check_task.apply_async()
        health_data = health_result.get(timeout=60)
        
        if health_data.get('status') == 'success':
            health_status = health_data['health_status']
            report['summary']['overall_health'] = health_status['overall_status']
            report['summary']['component_count'] = len(health_status['components'])
            report['summary']['alert_count'] = len(health_status['alerts'])
            report['alerts_summary'] = {
                'critical_alerts': [a for a in health_status['alerts'] if a['severity'] == 'critical'],
                'warning_alerts': [a for a in health_status['alerts'] if a['severity'] == 'warning']
            }
        
        # Perform performance analysis
        performance_result = performance_analysis_task.apply_async(args=[hours])
        performance_data = performance_result.get(timeout=120)
        
        if performance_data.get('status') == 'success':
            analysis_results = performance_data['analysis_results']
            report['recommendations'] = analysis_results['recommendations']
            
            # Add performance summary
            if 'query_performance' in analysis_results:
                query_perf = analysis_results['query_performance']
                if 'summary' in query_perf:
                    report['summary']['total_queries'] = query_perf['summary'].get('total_queries', 0)
                    report['summary']['slow_queries'] = query_perf['summary'].get('slow_queries', 0)
                    report['summary']['avg_response_time'] = query_perf['summary'].get('avg_execution_time', 0)
        
        # Generate executive summary
        report['executive_summary'] = generate_executive_summary(report)
        
        logger.info(f"{report_type.capitalize()} monitoring report generated successfully")
        
        return {
            'status': 'success',
            'report': report
        }
        
    except Exception as e:
        logger.error(f"Monitoring report generation failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'report_type': report_type
        }


def generate_executive_summary(report: Dict[str, Any]) -> Dict[str, Any]:
    """Generate executive summary from monitoring report."""
    summary = report.get('summary', {})
    alerts = report.get('alerts_summary', {})
    recommendations = report.get('recommendations', [])
    
    # Calculate health score
    health_score = 100
    if summary.get('overall_health') == 'critical':
        health_score = 30
    elif summary.get('overall_health') == 'warning':
        health_score = 70
    
    # Adjust score based on alerts
    critical_count = len(alerts.get('critical_alerts', []))
    warning_count = len(alerts.get('warning_alerts', []))
    
    health_score -= (critical_count * 20)
    health_score -= (warning_count * 10)
    health_score = max(0, health_score)
    
    # Categorize recommendations by priority
    high_priority_recs = [r for r in recommendations if r.get('priority') == 'high']
    medium_priority_recs = [r for r in recommendations if r.get('priority') == 'medium']
    
    return {
        'health_score': health_score,
        'health_grade': 'A' if health_score >= 90 else 'B' if health_score >= 70 else 'C' if health_score >= 50 else 'D',
        'critical_issues': critical_count,
        'warnings': warning_count,
        'high_priority_recommendations': len(high_priority_recs),
        'medium_priority_recommendations': len(medium_priority_recs),
        'key_metrics': {
            'total_queries': summary.get('total_queries', 0),
            'slow_queries': summary.get('slow_queries', 0),
            'avg_response_time_ms': round((summary.get('avg_response_time', 0) * 1000), 2)
        },
        'top_recommendations': high_priority_recs[:3]  # Top 3 high priority recommendations
    }