"""
Comprehensive task monitoring and analytics system.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import defaultdict
from .celery_app import get_celery_app
from .result_cache import get_task_result_cache, TaskResult
from .failure_handler import get_failure_handler

logger = logging.getLogger(__name__)


@dataclass
class TaskMetrics:
    """Task execution metrics."""
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    pending_tasks: int = 0
    in_progress_tasks: int = 0
    avg_execution_time: float = 0.0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_tasks': self.total_tasks,
            'successful_tasks': self.successful_tasks,
            'failed_tasks': self.failed_tasks,
            'pending_tasks': self.pending_tasks,
            'in_progress_tasks': self.in_progress_tasks,
            'avg_execution_time': self.avg_execution_time,
            'success_rate': self.success_rate,
            'failure_rate': self.failure_rate
        }


@dataclass
class WorkerMetrics:
    """Worker performance metrics."""
    worker_name: str
    status: str
    active_tasks: int = 0
    processed_tasks: int = 0
    failed_tasks: int = 0
    avg_task_time: float = 0.0
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'worker_name': self.worker_name,
            'status': self.status,
            'active_tasks': self.active_tasks,
            'processed_tasks': self.processed_tasks,
            'failed_tasks': self.failed_tasks,
            'avg_task_time': self.avg_task_time,
            'memory_usage': self.memory_usage,
            'cpu_usage': self.cpu_usage
        }


class TaskMonitor:
    """Comprehensive task monitoring system."""
    
    def __init__(self):
        self.celery_app = get_celery_app()
        self.result_cache = get_task_result_cache()
        self.failure_handler = get_failure_handler()
    
    def get_overall_metrics(self, hours: int = 24) -> TaskMetrics:
        """
        Get overall task metrics for the specified time period.
        
        Args:
            hours: Number of hours to analyze
        
        Returns:
            TaskMetrics with overall statistics
        """
        try:
            # Get recent task results from cache
            recent_results = self.result_cache.get_recent_results(limit=10000)
            
            # Filter by time period
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            filtered_results = [
                r for r in recent_results 
                if r.started_at and r.started_at >= cutoff_time
            ]
            
            metrics = TaskMetrics()
            metrics.total_tasks = len(filtered_results)
            
            if metrics.total_tasks == 0:
                return metrics
            
            # Calculate status counts
            status_counts = defaultdict(int)
            execution_times = []
            
            for result in filtered_results:
                status_counts[result.status] += 1
                
                # Calculate execution time if available
                if result.started_at and result.completed_at:
                    execution_time = (result.completed_at - result.started_at).total_seconds()
                    execution_times.append(execution_time)
            
            metrics.successful_tasks = status_counts['SUCCESS']
            metrics.failed_tasks = status_counts['FAILURE']
            metrics.pending_tasks = status_counts['PENDING']
            metrics.in_progress_tasks = status_counts['PROGRESS']
            
            # Calculate rates
            if metrics.total_tasks > 0:
                metrics.success_rate = (metrics.successful_tasks / metrics.total_tasks) * 100
                metrics.failure_rate = (metrics.failed_tasks / metrics.total_tasks) * 100
            
            # Calculate average execution time
            if execution_times:
                metrics.avg_execution_time = sum(execution_times) / len(execution_times)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get overall metrics: {e}")
            return TaskMetrics()
    
    def get_task_type_metrics(self, hours: int = 24) -> Dict[str, TaskMetrics]:
        """
        Get metrics broken down by task type.
        
        Args:
            hours: Number of hours to analyze
        
        Returns:
            Dictionary mapping task names to their metrics
        """
        try:
            # Get recent task results from cache
            recent_results = self.result_cache.get_recent_results(limit=10000)
            
            # Filter by time period
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            filtered_results = [
                r for r in recent_results 
                if r.started_at and r.started_at >= cutoff_time
            ]
            
            # Group by task name
            task_groups = defaultdict(list)
            for result in filtered_results:
                task_groups[result.task_name].append(result)
            
            # Calculate metrics for each task type
            task_metrics = {}
            for task_name, results in task_groups.items():
                metrics = TaskMetrics()
                metrics.total_tasks = len(results)
                
                status_counts = defaultdict(int)
                execution_times = []
                
                for result in results:
                    status_counts[result.status] += 1
                    
                    if result.started_at and result.completed_at:
                        execution_time = (result.completed_at - result.started_at).total_seconds()
                        execution_times.append(execution_time)
                
                metrics.successful_tasks = status_counts['SUCCESS']
                metrics.failed_tasks = status_counts['FAILURE']
                metrics.pending_tasks = status_counts['PENDING']
                metrics.in_progress_tasks = status_counts['PROGRESS']
                
                if metrics.total_tasks > 0:
                    metrics.success_rate = (metrics.successful_tasks / metrics.total_tasks) * 100
                    metrics.failure_rate = (metrics.failed_tasks / metrics.total_tasks) * 100
                
                if execution_times:
                    metrics.avg_execution_time = sum(execution_times) / len(execution_times)
                
                task_metrics[task_name] = metrics
            
            return task_metrics
            
        except Exception as e:
            logger.error(f"Failed to get task type metrics: {e}")
            return {}
    
    def get_worker_metrics(self) -> List[WorkerMetrics]:
        """
        Get metrics for all active workers.
        
        Returns:
            List of WorkerMetrics for each worker
        """
        try:
            if not self.celery_app:
                return []
            
            inspect = self.celery_app.control.inspect()
            
            # Get worker stats
            stats = inspect.stats()
            active_tasks = inspect.active()
            
            if not stats:
                return []
            
            worker_metrics = []
            
            for worker_name, worker_stats in stats.items():
                metrics = WorkerMetrics(
                    worker_name=worker_name,
                    status='online'
                )
                
                # Get active task count
                if active_tasks and worker_name in active_tasks:
                    metrics.active_tasks = len(active_tasks[worker_name])
                
                # Get processed task count
                total_stats = worker_stats.get('total', {})
                metrics.processed_tasks = sum(total_stats.values()) if total_stats else 0
                
                # Get resource usage if available
                rusage = worker_stats.get('rusage', {})
                if rusage:
                    # These would be system-specific and might not be available
                    metrics.memory_usage = rusage.get('maxrss')  # Max resident set size
                    metrics.cpu_usage = rusage.get('utime', 0) + rusage.get('stime', 0)  # User + system time
                
                worker_metrics.append(metrics)
            
            return worker_metrics
            
        except Exception as e:
            logger.error(f"Failed to get worker metrics: {e}")
            return []
    
    def get_queue_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for task queues.
        
        Returns:
            Dictionary with queue metrics
        """
        try:
            if not self.celery_app:
                return {}
            
            inspect = self.celery_app.control.inspect()
            
            # Get reserved tasks (queued tasks)
            reserved = inspect.reserved()
            
            if not reserved:
                return {}
            
            queue_metrics = {}
            
            # Count tasks by queue
            for worker_name, tasks in reserved.items():
                for task in tasks:
                    queue_name = task.get('delivery_info', {}).get('routing_key', 'default')
                    
                    if queue_name not in queue_metrics:
                        queue_metrics[queue_name] = {
                            'pending_tasks': 0,
                            'workers': set(),
                            'task_types': defaultdict(int)
                        }
                    
                    queue_metrics[queue_name]['pending_tasks'] += 1
                    queue_metrics[queue_name]['workers'].add(worker_name)
                    queue_metrics[queue_name]['task_types'][task['name']] += 1
            
            # Convert sets to lists for JSON serialization
            for queue_name, metrics in queue_metrics.items():
                metrics['workers'] = list(metrics['workers'])
                metrics['worker_count'] = len(metrics['workers'])
                metrics['task_types'] = dict(metrics['task_types'])
            
            return queue_metrics
            
        except Exception as e:
            logger.error(f"Failed to get queue metrics: {e}")
            return {}
    
    def get_performance_trends(self, hours: int = 24, 
                             interval_minutes: int = 60) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get performance trends over time.
        
        Args:
            hours: Number of hours to analyze
            interval_minutes: Interval for trend data points
        
        Returns:
            Dictionary with trend data
        """
        try:
            # Get recent task results
            recent_results = self.result_cache.get_recent_results(limit=10000)
            
            # Filter by time period
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            filtered_results = [
                r for r in recent_results 
                if r.started_at and r.started_at >= cutoff_time
            ]
            
            # Create time intervals
            interval_delta = timedelta(minutes=interval_minutes)
            intervals = []
            current_time = cutoff_time
            
            while current_time < datetime.utcnow():
                intervals.append(current_time)
                current_time += interval_delta
            
            # Group results by interval
            trend_data = {
                'timestamps': [],
                'total_tasks': [],
                'successful_tasks': [],
                'failed_tasks': [],
                'avg_execution_time': []
            }
            
            for i, interval_start in enumerate(intervals):
                interval_end = interval_start + interval_delta
                
                # Filter results for this interval
                interval_results = [
                    r for r in filtered_results
                    if interval_start <= r.started_at < interval_end
                ]
                
                # Calculate metrics for this interval
                total_tasks = len(interval_results)
                successful_tasks = len([r for r in interval_results if r.status == 'SUCCESS'])
                failed_tasks = len([r for r in interval_results if r.status == 'FAILURE'])
                
                # Calculate average execution time
                execution_times = []
                for result in interval_results:
                    if result.started_at and result.completed_at:
                        execution_time = (result.completed_at - result.started_at).total_seconds()
                        execution_times.append(execution_time)
                
                avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0
                
                # Add to trend data
                trend_data['timestamps'].append(interval_start.isoformat())
                trend_data['total_tasks'].append(total_tasks)
                trend_data['successful_tasks'].append(successful_tasks)
                trend_data['failed_tasks'].append(failed_tasks)
                trend_data['avg_execution_time'].append(avg_execution_time)
            
            return trend_data
            
        except Exception as e:
            logger.error(f"Failed to get performance trends: {e}")
            return {}
    
    def get_comprehensive_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get comprehensive monitoring report.
        
        Args:
            hours: Number of hours to analyze
        
        Returns:
            Comprehensive monitoring report
        """
        try:
            report = {
                'generated_at': datetime.utcnow().isoformat(),
                'analysis_period_hours': hours,
                'overall_metrics': self.get_overall_metrics(hours).to_dict(),
                'task_type_metrics': {
                    name: metrics.to_dict() 
                    for name, metrics in self.get_task_type_metrics(hours).items()
                },
                'worker_metrics': [
                    metrics.to_dict() for metrics in self.get_worker_metrics()
                ],
                'queue_metrics': self.get_queue_metrics(),
                'performance_trends': self.get_performance_trends(hours),
                'failure_statistics': self.failure_handler.get_failure_statistics(hours),
                'cache_statistics': self.result_cache.get_cache_stats()
            }
            
            # Add summary insights
            overall = report['overall_metrics']
            report['insights'] = self._generate_insights(overall, report)
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate comprehensive report: {e}")
            return {
                'generated_at': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    def _generate_insights(self, overall_metrics: Dict[str, Any], 
                          full_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate insights from monitoring data."""
        insights = []
        
        try:
            # Success rate insights
            success_rate = overall_metrics.get('success_rate', 0)
            if success_rate < 90:
                insights.append({
                    'type': 'warning',
                    'category': 'reliability',
                    'title': 'Low Task Success Rate',
                    'description': f'Task success rate is {success_rate:.1f}%, below recommended 90%',
                    'recommendation': 'Review failed tasks and improve error handling'
                })
            elif success_rate >= 95:
                insights.append({
                    'type': 'positive',
                    'category': 'reliability',
                    'title': 'Excellent Task Success Rate',
                    'description': f'Task success rate is {success_rate:.1f}%',
                    'recommendation': 'Maintain current practices'
                })
            
            # Performance insights
            avg_time = overall_metrics.get('avg_execution_time', 0)
            if avg_time > 300:  # 5 minutes
                insights.append({
                    'type': 'warning',
                    'category': 'performance',
                    'title': 'High Average Execution Time',
                    'description': f'Average task execution time is {avg_time:.1f} seconds',
                    'recommendation': 'Optimize slow tasks or increase worker resources'
                })
            
            # Worker insights
            worker_metrics = full_report.get('worker_metrics', [])
            active_workers = len([w for w in worker_metrics if w['status'] == 'online'])
            if active_workers == 0:
                insights.append({
                    'type': 'critical',
                    'category': 'availability',
                    'title': 'No Active Workers',
                    'description': 'No Celery workers are currently active',
                    'recommendation': 'Start Celery workers immediately'
                })
            elif active_workers < 2:
                insights.append({
                    'type': 'warning',
                    'category': 'availability',
                    'title': 'Low Worker Count',
                    'description': f'Only {active_workers} worker(s) active',
                    'recommendation': 'Consider adding more workers for redundancy'
                })
            
            # Failure pattern insights
            failure_stats = full_report.get('failure_statistics', {})
            if failure_stats.get('available'):
                failure_rate = failure_stats.get('failure_rate', 0)
                if failure_rate > 5:  # More than 5 failures per hour
                    insights.append({
                        'type': 'warning',
                        'category': 'reliability',
                        'title': 'High Failure Rate',
                        'description': f'Failure rate is {failure_rate:.1f} failures per hour',
                        'recommendation': 'Investigate common failure patterns'
                    })
            
        except Exception as e:
            logger.error(f"Failed to generate insights: {e}")
            insights.append({
                'type': 'error',
                'category': 'monitoring',
                'title': 'Insight Generation Failed',
                'description': f'Failed to generate insights: {str(e)}',
                'recommendation': 'Check monitoring system logs'
            })
        
        return insights


# Global monitor instance
_task_monitor = None


def get_task_monitor() -> TaskMonitor:
    """Get global task monitor instance."""
    global _task_monitor
    if _task_monitor is None:
        _task_monitor = TaskMonitor()
    return _task_monitor