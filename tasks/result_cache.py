"""
Task result caching and retrieval system.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from cache.redis_client import get_redis_client

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Task result data structure."""
    task_id: str
    task_name: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: int = 0
    current_step: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    worker: Optional[str] = None
    retries: int = 0
    eta: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with datetime serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskResult':
        """Create from dictionary with datetime deserialization."""
        # Convert ISO strings back to datetime objects
        datetime_fields = ['started_at', 'completed_at', 'eta']
        for field in datetime_fields:
            if data.get(field):
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except (ValueError, TypeError):
                    data[field] = None
        
        return cls(**data)


class TaskResultCache:
    """Task result caching manager."""
    
    def __init__(self):
        self.redis_client = get_redis_client()
        self.cache_prefix = "task_result:"
        self.index_key = "task_results_index"
        self.default_ttl = 3600  # 1 hour
        
    def _get_cache_key(self, task_id: str) -> str:
        """Get cache key for task ID."""
        return f"{self.cache_prefix}{task_id}"
    
    def store_result(self, task_result: TaskResult, ttl: Optional[int] = None) -> bool:
        """
        Store task result in cache.
        
        Args:
            task_result: Task result to store
            ttl: Time to live in seconds
        
        Returns:
            True if stored successfully
        """
        try:
            if not self.redis_client or not self.redis_client.is_available():
                logger.warning("Redis not available for task result caching")
                return False
            
            cache_key = self._get_cache_key(task_result.task_id)
            ttl = ttl or self.default_ttl
            
            # Store result data
            result_data = json.dumps(task_result.to_dict())
            success = self.redis_client.setex(cache_key, ttl, result_data)
            
            if success:
                # Add to index for listing
                self.redis_client.zadd(
                    self.index_key,
                    {task_result.task_id: datetime.utcnow().timestamp()}
                )
                
                # Set TTL on index (longer than individual results)
                self.redis_client.expire(self.index_key, ttl * 2)
                
                logger.debug(f"Cached task result for {task_result.task_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to cache task result {task_result.task_id}: {e}")
            return False
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get task result from cache.
        
        Args:
            task_id: Task ID to retrieve
        
        Returns:
            TaskResult if found, None otherwise
        """
        try:
            if not self.redis_client or not self.redis_client.is_available():
                return None
            
            cache_key = self._get_cache_key(task_id)
            result_data = self.redis_client.get(cache_key)
            
            if result_data:
                data = json.loads(result_data)
                return TaskResult.from_dict(data)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached task result {task_id}: {e}")
            return None
    
    def update_progress(self, task_id: str, progress: int, current_step: str) -> bool:
        """
        Update task progress in cache.
        
        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)
            current_step: Current step description
        
        Returns:
            True if updated successfully
        """
        try:
            task_result = self.get_result(task_id)
            if task_result:
                task_result.progress = progress
                task_result.current_step = current_step
                return self.store_result(task_result)
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update task progress {task_id}: {e}")
            return False
    
    def mark_completed(self, task_id: str, result: Dict[str, Any], 
                      status: str = 'SUCCESS') -> bool:
        """
        Mark task as completed in cache.
        
        Args:
            task_id: Task ID
            result: Task result data
            status: Task status
        
        Returns:
            True if updated successfully
        """
        try:
            task_result = self.get_result(task_id)
            if task_result:
                task_result.status = status
                task_result.result = result
                task_result.progress = 100
                task_result.completed_at = datetime.utcnow()
                task_result.current_step = "Completed"
                return self.store_result(task_result, ttl=7200)  # Keep completed tasks longer
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to mark task completed {task_id}: {e}")
            return False
    
    def mark_failed(self, task_id: str, error: str, retries: int = 0) -> bool:
        """
        Mark task as failed in cache.
        
        Args:
            task_id: Task ID
            error: Error message
            retries: Number of retries attempted
        
        Returns:
            True if updated successfully
        """
        try:
            task_result = self.get_result(task_id)
            if task_result:
                task_result.status = 'FAILURE'
                task_result.error = error
                task_result.retries = retries
                task_result.completed_at = datetime.utcnow()
                task_result.current_step = f"Failed: {error}"
                return self.store_result(task_result, ttl=7200)  # Keep failed tasks longer
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to mark task failed {task_id}: {e}")
            return False
    
    def get_recent_results(self, limit: int = 100) -> List[TaskResult]:
        """
        Get recent task results.
        
        Args:
            limit: Maximum number of results to return
        
        Returns:
            List of recent task results
        """
        try:
            if not self.redis_client or not self.redis_client.is_available():
                return []
            
            # Get recent task IDs from index
            task_ids = self.redis_client.zrevrange(self.index_key, 0, limit - 1)
            
            results = []
            for task_id in task_ids:
                if isinstance(task_id, bytes):
                    task_id = task_id.decode('utf-8')
                
                task_result = self.get_result(task_id)
                if task_result:
                    results.append(task_result)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get recent task results: {e}")
            return []
    
    def get_results_by_status(self, status: str, limit: int = 100) -> List[TaskResult]:
        """
        Get task results by status.
        
        Args:
            status: Task status to filter by
            limit: Maximum number of results to return
        
        Returns:
            List of task results with specified status
        """
        try:
            recent_results = self.get_recent_results(limit * 2)  # Get more to filter
            filtered_results = [r for r in recent_results if r.status == status]
            return filtered_results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get results by status {status}: {e}")
            return []
    
    def cleanup_expired_results(self) -> int:
        """
        Clean up expired task results from index.
        
        Returns:
            Number of expired results cleaned up
        """
        try:
            if not self.redis_client or not self.redis_client.is_available():
                return 0
            
            # Get all task IDs from index
            all_task_ids = self.redis_client.zrange(self.index_key, 0, -1)
            
            expired_count = 0
            for task_id in all_task_ids:
                if isinstance(task_id, bytes):
                    task_id = task_id.decode('utf-8')
                
                cache_key = self._get_cache_key(task_id)
                if not self.redis_client.exists(cache_key):
                    # Remove from index if cache entry doesn't exist
                    self.redis_client.zrem(self.index_key, task_id)
                    expired_count += 1
            
            logger.info(f"Cleaned up {expired_count} expired task results")
            return expired_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired results: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            if not self.redis_client or not self.redis_client.is_available():
                return {'available': False}
            
            # Get total cached results
            total_results = self.redis_client.zcard(self.index_key)
            
            # Get results by status
            recent_results = self.get_recent_results(1000)  # Sample recent results
            status_counts = {}
            for result in recent_results:
                status_counts[result.status] = status_counts.get(result.status, 0) + 1
            
            return {
                'available': True,
                'total_cached_results': total_results,
                'status_distribution': status_counts,
                'cache_prefix': self.cache_prefix,
                'default_ttl': self.default_ttl
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {'available': False, 'error': str(e)}


# Global cache instance
_task_result_cache = None


def get_task_result_cache() -> TaskResultCache:
    """Get global task result cache instance."""
    global _task_result_cache
    if _task_result_cache is None:
        _task_result_cache = TaskResultCache()
    return _task_result_cache


def cache_task_result(task_id: str, task_name: str, status: str, 
                     worker: Optional[str] = None, **kwargs) -> bool:
    """
    Convenience function to cache task result.
    
    Args:
        task_id: Task ID
        task_name: Task name
        status: Task status
        worker: Worker name
        **kwargs: Additional task result fields
    
    Returns:
        True if cached successfully
    """
    try:
        cache = get_task_result_cache()
        
        task_result = TaskResult(
            task_id=task_id,
            task_name=task_name,
            status=status,
            worker=worker,
            started_at=datetime.utcnow() if status in ['PENDING', 'PROGRESS'] else None,
            **kwargs
        )
        
        return cache.store_result(task_result)
        
    except Exception as e:
        logger.error(f"Failed to cache task result: {e}")
        return False