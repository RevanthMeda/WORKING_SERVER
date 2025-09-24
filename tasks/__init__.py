"""
Background task processing system using Celery.
"""
from .celery_app import celery_app, init_celery, get_celery_app
from .email_tasks import send_email_task, send_bulk_email_task, send_notification_email_task
from .report_tasks import generate_report_task, process_report_approval_task, batch_report_generation_task
from .maintenance_tasks import cleanup_old_files_task, backup_database_task, optimize_database_task
from .monitoring_tasks import collect_metrics_task, health_check_task, performance_analysis_task
from .result_cache import get_task_result_cache, TaskResult, cache_task_result
from .failure_handler import get_failure_handler, handle_task_failure
from .monitoring import get_task_monitor

__all__ = [
    'celery_app',
    'init_celery',
    'get_celery_app',
    'send_email_task',
    'send_bulk_email_task',
    'send_notification_email_task',
    'generate_report_task',
    'process_report_approval_task',
    'batch_report_generation_task',
    'cleanup_old_files_task',
    'backup_database_task',
    'optimize_database_task',
    'collect_metrics_task',
    'health_check_task',
    'performance_analysis_task',
    'get_task_result_cache',
    'TaskResult',
    'cache_task_result',
    'get_failure_handler',
    'handle_task_failure',
    'get_task_monitor'
]