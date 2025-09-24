"""
Task failure handling and recovery system.
"""
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from celery import Task
from celery.exceptions import Retry, MaxRetriesExceededError
from .result_cache import get_task_result_cache, TaskResult

logger = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of task failures."""
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    DATABASE_ERROR = "database_error"
    VALIDATION_ERROR = "validation_error"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class FailureInfo:
    """Task failure information."""
    task_id: str
    task_name: str
    failure_type: FailureType
    error_message: str
    retry_count: int
    max_retries: int
    failed_at: datetime
    worker: Optional[str] = None
    args: Optional[List] = None
    kwargs: Optional[Dict] = None
    traceback: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'task_id': self.task_id,
            'task_name': self.task_name,
            'failure_type': self.failure_type.value,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'failed_at': self.failed_at.isoformat(),
            'worker': self.worker,
            'args': self.args,
            'kwargs': self.kwargs,
            'traceback': self.traceback
        }


class TaskFailureHandler:
    """Handles task failures and implements recovery strategies."""
    
    def __init__(self):
        self.result_cache = get_task_result_cache()
        self.failure_handlers: Dict[FailureType, Callable] = {
            FailureType.TIMEOUT: self._handle_timeout_failure,
            FailureType.NETWORK_ERROR: self._handle_network_failure,
            FailureType.DATABASE_ERROR: self._handle_database_failure,
            FailureType.VALIDATION_ERROR: self._handle_validation_failure,
            FailureType.RESOURCE_ERROR: self._handle_resource_failure,
            FailureType.UNKNOWN_ERROR: self._handle_unknown_failure
        }
    
    def classify_failure(self, exception: Exception, task_name: str) -> FailureType:
        """
        Classify the type of failure based on exception.
        
        Args:
            exception: The exception that caused the failure
            task_name: Name of the failed task
        
        Returns:
            FailureType classification
        """
        error_message = str(exception).lower()
        
        # Timeout errors
        if any(keyword in error_message for keyword in ['timeout', 'time limit', 'deadline']):
            return FailureType.TIMEOUT
        
        # Network errors
        if any(keyword in error_message for keyword in ['connection', 'network', 'socket', 'dns']):
            return FailureType.NETWORK_ERROR
        
        # Database errors
        if any(keyword in error_message for keyword in ['database', 'sql', 'connection pool', 'deadlock']):
            return FailureType.DATABASE_ERROR
        
        # Validation errors
        if any(keyword in error_message for keyword in ['validation', 'invalid', 'missing required']):
            return FailureType.VALIDATION_ERROR
        
        # Resource errors
        if any(keyword in error_message for keyword in ['memory', 'disk space', 'file not found', 'permission']):
            return FailureType.RESOURCE_ERROR
        
        return FailureType.UNKNOWN_ERROR
    
    def handle_failure(self, task: Task, exception: Exception, 
                      traceback: Optional[str] = None) -> bool:
        """
        Handle task failure with appropriate recovery strategy.
        
        Args:
            task: The failed task
            exception: The exception that caused the failure
            traceback: Exception traceback
        
        Returns:
            True if failure was handled and task should be retried
        """
        try:
            failure_type = self.classify_failure(exception, task.name)
            
            failure_info = FailureInfo(
                task_id=task.request.id,
                task_name=task.name,
                failure_type=failure_type,
                error_message=str(exception),
                retry_count=task.request.retries,
                max_retries=task.max_retries,
                failed_at=datetime.utcnow(),
                worker=task.request.hostname,
                args=task.request.args,
                kwargs=task.request.kwargs,
                traceback=traceback
            )
            
            # Log failure
            logger.error(f"Task {task.name} [{task.request.id}] failed: {failure_type.value} - {str(exception)}")
            
            # Update cache with failure info
            self.result_cache.mark_failed(
                task.request.id,
                str(exception),
                task.request.retries
            )
            
            # Apply failure-specific handling
            handler = self.failure_handlers.get(failure_type, self._handle_unknown_failure)
            should_retry = handler(failure_info, task)
            
            # Store failure info for analysis
            self._store_failure_info(failure_info)
            
            return should_retry
            
        except Exception as e:
            logger.error(f"Error in failure handler: {e}")
            return False
    
    def _handle_timeout_failure(self, failure_info: FailureInfo, task: Task) -> bool:
        """Handle timeout failures."""
        logger.warning(f"Timeout failure for task {failure_info.task_name}")
        
        # For timeout failures, retry with exponential backoff
        if failure_info.retry_count < failure_info.max_retries:
            # Increase timeout for retry
            retry_delay = min(60 * (2 ** failure_info.retry_count), 300)  # Max 5 minutes
            logger.info(f"Retrying task {failure_info.task_id} in {retry_delay} seconds")
            return True
        
        return False
    
    def _handle_network_failure(self, failure_info: FailureInfo, task: Task) -> bool:
        """Handle network failures."""
        logger.warning(f"Network failure for task {failure_info.task_name}")
        
        # For network failures, retry with longer delays
        if failure_info.retry_count < failure_info.max_retries:
            retry_delay = min(120 * (failure_info.retry_count + 1), 600)  # Max 10 minutes
            logger.info(f"Retrying task {failure_info.task_id} in {retry_delay} seconds")
            return True
        
        return False
    
    def _handle_database_failure(self, failure_info: FailureInfo, task: Task) -> bool:
        """Handle database failures."""
        logger.warning(f"Database failure for task {failure_info.task_name}")
        
        # For database failures, check if it's a transient issue
        transient_errors = ['deadlock', 'connection pool', 'timeout']
        is_transient = any(error in failure_info.error_message.lower() for error in transient_errors)
        
        if is_transient and failure_info.retry_count < failure_info.max_retries:
            retry_delay = min(30 * (failure_info.retry_count + 1), 180)  # Max 3 minutes
            logger.info(f"Retrying transient database error for task {failure_info.task_id} in {retry_delay} seconds")
            return True
        
        return False
    
    def _handle_validation_failure(self, failure_info: FailureInfo, task: Task) -> bool:
        """Handle validation failures."""
        logger.error(f"Validation failure for task {failure_info.task_name}: {failure_info.error_message}")
        
        # Validation errors are usually not retryable
        return False
    
    def _handle_resource_failure(self, failure_info: FailureInfo, task: Task) -> bool:
        """Handle resource failures."""
        logger.warning(f"Resource failure for task {failure_info.task_name}")
        
        # For resource failures, retry with longer delays to allow recovery
        if failure_info.retry_count < failure_info.max_retries:
            retry_delay = min(300 * (failure_info.retry_count + 1), 1800)  # Max 30 minutes
            logger.info(f"Retrying resource failure for task {failure_info.task_id} in {retry_delay} seconds")
            return True
        
        return False
    
    def _handle_unknown_failure(self, failure_info: FailureInfo, task: Task) -> bool:
        """Handle unknown failures."""
        logger.error(f"Unknown failure for task {failure_info.task_name}: {failure_info.error_message}")
        
        # For unknown failures, use conservative retry strategy
        if failure_info.retry_count < min(failure_info.max_retries, 2):  # Max 2 retries for unknown errors
            retry_delay = 60 * (failure_info.retry_count + 1)
            logger.info(f"Retrying unknown failure for task {failure_info.task_id} in {retry_delay} seconds")
            return True
        
        return False
    
    def _store_failure_info(self, failure_info: FailureInfo):
        """Store failure information for analysis."""
        try:
            from cache.redis_client import get_redis_client
            
            redis_client = get_redis_client()
            if redis_client and redis_client.is_available():
                # Store in Redis with TTL
                key = f"task_failure:{failure_info.task_id}:{failure_info.retry_count}"
                redis_client.setex(key, 86400, str(failure_info.to_dict()))  # 24 hours TTL
                
                # Add to failure index
                redis_client.zadd(
                    "task_failures_index",
                    {failure_info.task_id: failure_info.failed_at.timestamp()}
                )
                redis_client.expire("task_failures_index", 86400 * 7)  # 7 days
                
        except Exception as e:
            logger.error(f"Failed to store failure info: {e}")
    
    def get_failure_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get failure statistics for the specified time period.
        
        Args:
            hours: Number of hours to analyze
        
        Returns:
            Dictionary with failure statistics
        """
        try:
            from cache.redis_client import get_redis_client
            
            redis_client = get_redis_client()
            if not redis_client or not redis_client.is_available():
                return {'available': False}
            
            # Get failures from the last N hours
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            cutoff_timestamp = cutoff_time.timestamp()
            
            failure_ids = redis_client.zrangebyscore(
                "task_failures_index",
                cutoff_timestamp,
                "+inf"
            )
            
            # Analyze failures
            failure_types = {}
            task_names = {}
            total_failures = 0
            
            for failure_id in failure_ids:
                if isinstance(failure_id, bytes):
                    failure_id = failure_id.decode('utf-8')
                
                # Get failure details (try different retry counts)
                failure_data = None
                for retry_count in range(5):  # Check up to 5 retries
                    key = f"task_failure:{failure_id}:{retry_count}"
                    data = redis_client.get(key)
                    if data:
                        try:
                            failure_data = eval(data)  # Convert string back to dict
                            break
                        except:
                            continue
                
                if failure_data:
                    total_failures += 1
                    
                    # Count by failure type
                    failure_type = failure_data.get('failure_type', 'unknown')
                    failure_types[failure_type] = failure_types.get(failure_type, 0) + 1
                    
                    # Count by task name
                    task_name = failure_data.get('task_name', 'unknown')
                    task_names[task_name] = task_names.get(task_name, 0) + 1
            
            return {
                'available': True,
                'period_hours': hours,
                'total_failures': total_failures,
                'failure_types': failure_types,
                'task_names': task_names,
                'failure_rate': total_failures / hours if hours > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get failure statistics: {e}")
            return {'available': False, 'error': str(e)}


# Global failure handler instance
_failure_handler = None


def get_failure_handler() -> TaskFailureHandler:
    """Get global failure handler instance."""
    global _failure_handler
    if _failure_handler is None:
        _failure_handler = TaskFailureHandler()
    return _failure_handler


def handle_task_failure(task: Task, exception: Exception, 
                       traceback: Optional[str] = None) -> bool:
    """
    Convenience function to handle task failure.
    
    Args:
        task: The failed task
        exception: The exception that caused the failure
        traceback: Exception traceback
    
    Returns:
        True if task should be retried
    """
    handler = get_failure_handler()
    return handler.handle_failure(task, exception, traceback)