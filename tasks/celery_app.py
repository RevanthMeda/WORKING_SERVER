"""
Celery application configuration and initialization.
"""
import os
import logging
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure, task_success
from flask import Flask
from datetime import timedelta

logger = logging.getLogger(__name__)


def make_celery(app: Flask) -> Celery:
    """Create and configure Celery app with Flask integration."""
    
    # Get broker URL from config or environment
    broker_url = app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    result_backend = app.config.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    
    celery = Celery(
        app.import_name,
        backend=result_backend,
        broker=broker_url,
        include=[
            'tasks.email_tasks',
            'tasks.report_tasks', 
            'tasks.maintenance_tasks',
            'tasks.monitoring_tasks'
        ]
    )
    
    # Configure Celery
    celery.conf.update(
        # Task routing
        task_routes={
            'tasks.email_tasks.*': {'queue': 'email'},
            'tasks.report_tasks.*': {'queue': 'reports'},
            'tasks.maintenance_tasks.*': {'queue': 'maintenance'},
            'tasks.monitoring_tasks.*': {'queue': 'monitoring'}
        },
        
        # Task execution settings
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        
        # Task result settings
        result_expires=3600,  # 1 hour
        task_track_started=True,
        task_time_limit=300,  # 5 minutes
        task_soft_time_limit=240,  # 4 minutes
        
        # Task result caching
        result_cache_max=10000,  # Cache up to 10k results
        result_persistent=True,
        
        # Task failure handling
        task_annotations={
            '*': {
                'rate_limit': '100/m',  # 100 tasks per minute per worker
                'time_limit': 300,
                'soft_time_limit': 240,
                'retry_policy': {
                    'max_retries': 3,
                    'interval_start': 0,
                    'interval_step': 0.2,
                    'interval_max': 0.2,
                }
            },
            'tasks.email_tasks.*': {
                'rate_limit': '50/m',  # Email tasks limited to 50/min
                'retry_policy': {
                    'max_retries': 5,
                    'interval_start': 60,
                    'interval_step': 60,
                    'interval_max': 300,
                }
            },
            'tasks.report_tasks.*': {
                'rate_limit': '20/m',  # Report generation limited to 20/min
                'time_limit': 600,  # 10 minutes for reports
                'soft_time_limit': 540,
                'retry_policy': {
                    'max_retries': 2,
                    'interval_start': 120,
                    'interval_step': 120,
                    'interval_max': 300,
                }
            }
        },
        
        # Worker settings
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        worker_disable_rate_limits=False,
        
        # Retry settings
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        
        # Beat schedule for periodic tasks
        beat_schedule={
            'cleanup-old-files': {
                'task': 'tasks.maintenance_tasks.cleanup_old_files_task',
                'schedule': timedelta(hours=24),  # Daily
                'options': {'queue': 'maintenance'}
            },
            'backup-database': {
                'task': 'tasks.maintenance_tasks.backup_database_task',
                'schedule': timedelta(hours=6),  # Every 6 hours
                'options': {'queue': 'maintenance'}
            },
            'collect-metrics': {
                'task': 'tasks.monitoring_tasks.collect_metrics_task',
                'schedule': timedelta(minutes=5),  # Every 5 minutes
                'options': {'queue': 'monitoring'}
            },
            'health-check': {
                'task': 'tasks.monitoring_tasks.health_check_task',
                'schedule': timedelta(minutes=1),  # Every minute
                'options': {'queue': 'monitoring'}
            }
        },
        beat_schedule_filename='celerybeat-schedule'
    )
    
    # Update task base classes to work with Flask app context
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    
    return celery


def init_celery(app: Flask) -> Celery:
    """Initialize Celery with Flask app."""
    celery = make_celery(app)
    
    # Set up task monitoring
    setup_task_monitoring(celery)
    
    logger.info("Celery initialized successfully")
    return celery


def setup_task_monitoring(celery: Celery):
    """Set up task monitoring and logging."""
    
    @task_prerun.connect
    def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
        """Log task start and cache initial result."""
        logger.info(f"Task {task.name} [{task_id}] started with args={args}, kwargs={kwargs}")
        
        # Cache initial task result
        try:
            from .result_cache import cache_task_result
            cache_task_result(
                task_id=task_id,
                task_name=task.name,
                status='PROGRESS',
                worker=task.request.hostname if hasattr(task, 'request') else None,
                progress=0,
                current_step='Starting task'
            )
        except Exception as e:
            logger.debug(f"Failed to cache initial task result: {e}")
    
    @task_postrun.connect
    def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                           retval=None, state=None, **kwds):
        """Log task completion and update cache."""
        logger.info(f"Task {task.name} [{task_id}] completed with state={state}")
        
        # Update cache with completion
        try:
            from .result_cache import get_task_result_cache
            cache = get_task_result_cache()
            
            if state == 'SUCCESS':
                cache.mark_completed(task_id, retval or {}, 'SUCCESS')
            elif state == 'FAILURE':
                error_msg = str(retval) if retval else 'Unknown error'
                cache.mark_failed(task_id, error_msg)
        except Exception as e:
            logger.debug(f"Failed to update task result cache: {e}")
    
    @task_success.connect
    def task_success_handler(sender=None, result=None, **kwds):
        """Handle successful task completion."""
        logger.info(f"Task {sender.name} completed successfully")
        
        # Additional success handling can be added here
        try:
            from .result_cache import get_task_result_cache
            cache = get_task_result_cache()
            
            # Extend TTL for successful tasks
            if hasattr(sender, 'request') and sender.request.id:
                task_result = cache.get_result(sender.request.id)
                if task_result:
                    cache.store_result(task_result, ttl=7200)  # Keep successful tasks for 2 hours
        except Exception as e:
            logger.debug(f"Failed to extend successful task TTL: {e}")
    
    @task_failure.connect
    def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
        """Handle task failure with enhanced failure handling."""
        logger.error(f"Task {sender.name} [{task_id}] failed: {exception}")
        logger.error(f"Traceback: {traceback}")
        
        # Enhanced failure handling
        try:
            from .failure_handler import handle_task_failure
            
            # Create a mock task object for the failure handler
            class MockTask:
                def __init__(self, name, task_id, max_retries=3):
                    self.name = name
                    self.max_retries = max_retries
                    self.request = type('obj', (object,), {
                        'id': task_id,
                        'retries': 0,  # This would need to be tracked properly
                        'hostname': 'unknown',
                        'args': [],
                        'kwargs': {}
                    })()
            
            mock_task = MockTask(sender.name, task_id)
            should_retry = handle_task_failure(mock_task, exception, str(traceback))
            
            if should_retry:
                logger.info(f"Task {task_id} marked for retry by failure handler")
            else:
                logger.info(f"Task {task_id} will not be retried")
                
        except Exception as e:
            logger.error(f"Error in enhanced failure handling: {e}")
    
    @celery.task_prerun.connect
    def task_sent_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
        """Handle task sent event."""
        try:
            from .result_cache import cache_task_result
            cache_task_result(
                task_id=task_id,
                task_name=task,
                status='PENDING',
                current_step='Task queued'
            )
        except Exception as e:
            logger.debug(f"Failed to cache task sent event: {e}")


# Global Celery instance
celery_app = None


def get_celery_app() -> Celery:
    """Get the global Celery app instance."""
    return celery_app


def create_celery_app(app: Flask = None) -> Celery:
    """Create Celery app for standalone usage."""
    if app is None:
        # Create minimal Flask app for Celery worker
        app = Flask(__name__)
        app.config.update(
            CELERY_BROKER_URL=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1'),
            CELERY_RESULT_BACKEND=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
        )
    
    global celery_app
    celery_app = make_celery(app)
    return celery_app