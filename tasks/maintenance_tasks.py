"""
System maintenance background tasks.
"""
import logging
import os
import re
import requests
import shutil
import tempfile
from typing import Dict, Any
from datetime import datetime, timedelta
from celery import current_task
from flask import current_app
from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def cleanup_old_files_task(self, max_age_days: int = 30) -> Dict[str, Any]:
    """
    Clean up old temporary and log files.
    
    Args:
        max_age_days: Maximum age of files to keep in days
    
    Returns:
        Dict with cleanup results
    """
    try:
        logger.info(f"Starting file cleanup for files older than {max_age_days} days")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing cleanup', 'progress': 10}
        )
        
        cleanup_results = {
            'temp_files': {'deleted': 0, 'space_freed': 0},
            'log_files': {'deleted': 0, 'space_freed': 0},
            'upload_files': {'deleted': 0, 'space_freed': 0},
            'cache_files': {'deleted': 0, 'space_freed': 0}
        }
        
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        # Define cleanup directories
        cleanup_dirs = [
            {
                'name': 'temp_files',
                'path': current_app.config.get('TEMP_DIR', tempfile.gettempdir()),
                'pattern': 'sat_*'
            },
            {
                'name': 'log_files', 
                'path': current_app.config.get('LOG_DIR', 'logs'),
                'pattern': '*.log.*'  # Rotated log files
            },
            {
                'name': 'upload_files',
                'path': current_app.config.get('UPLOAD_FOLDER', 'uploads/temp'),
                'pattern': '*'
            },
            {
                'name': 'cache_files',
                'path': current_app.config.get('CACHE_DIR', 'cache'),
                'pattern': '*'
            }
        ]
        
        total_dirs = len(cleanup_dirs)
        
        for i, cleanup_dir in enumerate(cleanup_dirs):
            try:
                # Update progress
                progress = int(((i + 1) / total_dirs) * 80) + 10
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'status': f'Cleaning {cleanup_dir["name"]}',
                        'progress': progress
                    }
                )
                
                dir_path = cleanup_dir['path']
                if not os.path.exists(dir_path):
                    continue
                
                # Find and delete old files
                import glob
                pattern = os.path.join(dir_path, cleanup_dir['pattern'])
                files = glob.glob(pattern)
                
                for file_path in files:
                    try:
                        if os.path.isfile(file_path):
                            # Check file age
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                            
                            if file_mtime < cutoff_date:
                                # Get file size before deletion
                                file_size = os.path.getsize(file_path)
                                
                                # Delete file
                                os.remove(file_path)
                                
                                cleanup_results[cleanup_dir['name']]['deleted'] += 1
                                cleanup_results[cleanup_dir['name']]['space_freed'] += file_size
                                
                                logger.debug(f"Deleted old file: {file_path}")
                                
                    except Exception as e:
                        logger.error(f"Failed to delete file {file_path}: {e}")
                        
            except Exception as e:
                logger.error(f"Failed to cleanup directory {cleanup_dir['name']}: {e}")
        
        # Calculate totals
        total_deleted = sum(result['deleted'] for result in cleanup_results.values())
        total_space_freed = sum(result['space_freed'] for result in cleanup_results.values())
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Cleanup completed', 'progress': 100}
        )
        
        logger.info(f"File cleanup completed: {total_deleted} files deleted, {total_space_freed} bytes freed")
        
        return {
            'status': 'success',
            'total_files_deleted': total_deleted,
            'total_space_freed': total_space_freed,
            'total_space_freed_mb': round(total_space_freed / (1024 * 1024), 2),
            'cleanup_details': cleanup_results,
            'max_age_days': max_age_days,
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"File cleanup failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'max_age_days': max_age_days
        }


@celery_app.task(bind=True)
def backup_database_task(self, backup_type: str = 'incremental') -> Dict[str, Any]:
    """
    Create database backup.
    
    Args:
        backup_type: Type of backup ('full' or 'incremental')
    
    Returns:
        Dict with backup results
    """
    try:
        logger.info(f"Starting {backup_type} database backup")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing backup', 'progress': 10}
        )
        
        # Import backup manager
        from database.backup import backup_manager
        
        # Generate backup name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{backup_type}_backup_{timestamp}"
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Creating backup', 'progress': 30}
        )
        
        # Create backup
        result = backup_manager.create_backup(
            backup_name=backup_name,
            include_files=True
        )
        
        if not result['success']:
            raise Exception(result['error'])
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Verifying backup', 'progress': 70}
        )
        
        # Verify backup integrity
        backup_path = result['backup_path']
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        backup_size = os.path.getsize(backup_path)
        if backup_size == 0:
            raise Exception("Backup file is empty")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Backup completed', 'progress': 100}
        )
        
        logger.info(f"Database backup completed: {backup_path}")
        
        return {
            'status': 'success',
            'backup_name': backup_name,
            'backup_path': backup_path,
            'backup_size': backup_size,
            'backup_size_mb': round(backup_size / (1024 * 1024), 2),
            'backup_type': backup_type,
            'created_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'backup_type': backup_type
        }


@celery_app.task(bind=True)
def optimize_database_task(self) -> Dict[str, Any]:
    """
    Perform database optimization tasks.
    
    Returns:
        Dict with optimization results
    """
    try:
        logger.info("Starting database optimization")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing optimization', 'progress': 10}
        )
        
        optimization_results = {
            'vacuum_completed': False,
            'statistics_updated': False,
            'indexes_created': 0,
            'cache_cleared': False,
            'old_records_cleaned': 0
        }
        
        # Import database modules
        from database.performance import DatabaseMaintenanceManager, DatabaseIndexManager
        from database.query_cache import get_cache_manager
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Vacuuming database', 'progress': 25}
        )
        
        # Vacuum database
        try:
            if DatabaseMaintenanceManager.vacuum_database():
                optimization_results['vacuum_completed'] = True
                logger.info("Database vacuum completed")
        except Exception as e:
            logger.error(f"Database vacuum failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Updating statistics', 'progress': 40}
        )
        
        # Update database statistics
        try:
            if DatabaseMaintenanceManager.update_statistics():
                optimization_results['statistics_updated'] = True
                logger.info("Database statistics updated")
        except Exception as e:
            logger.error(f"Statistics update failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Creating indexes', 'progress': 55}
        )
        
        # Create recommended indexes
        try:
            created, failed = DatabaseIndexManager.create_recommended_indexes()
            optimization_results['indexes_created'] = len(created)
            logger.info(f"Created {len(created)} database indexes")
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Clearing cache', 'progress': 70}
        )
        
        # Clear query cache
        try:
            cache_manager = get_cache_manager()
            if cache_manager:
                cache_manager.clear_all_cache()
                optimization_results['cache_cleared'] = True
                logger.info("Query cache cleared")
        except Exception as e:
            logger.error(f"Cache clearing failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Cleaning old records', 'progress': 85}
        )
        
        # Clean up old records
        try:
            cleaned_count = DatabaseMaintenanceManager.cleanup_old_records()
            optimization_results['old_records_cleaned'] = cleaned_count
            logger.info(f"Cleaned up {cleaned_count} old records")
        except Exception as e:
            logger.error(f"Record cleanup failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Optimization completed', 'progress': 100}
        )
        
        logger.info("Database optimization completed")
        
        return {
            'status': 'success',
            'optimization_results': optimization_results,
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'optimization_results': optimization_results
        }


@celery_app.task(bind=True)
def system_health_maintenance_task(self) -> Dict[str, Any]:
    """
    Perform comprehensive system health maintenance.
    
    Returns:
        Dict with maintenance results
    """
    try:
        logger.info("Starting system health maintenance")
        
        maintenance_results = {
            'disk_usage_checked': False,
            'memory_usage_checked': False,
            'service_health_checked': False,
            'log_rotation_completed': False,
            'alerts_generated': []
        }
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Checking disk usage', 'progress': 20}
        )
        
        # Check disk usage
        try:
            import psutil
            disk_usage = psutil.disk_usage('/')
            disk_percent = (disk_usage.used / disk_usage.total) * 100
            
            maintenance_results['disk_usage_checked'] = True
            maintenance_results['disk_usage_percent'] = round(disk_percent, 2)
            
            if disk_percent > 90:
                maintenance_results['alerts_generated'].append({
                    'type': 'disk_space',
                    'severity': 'critical',
                    'message': f'Disk usage is {disk_percent:.1f}%'
                })
            elif disk_percent > 80:
                maintenance_results['alerts_generated'].append({
                    'type': 'disk_space',
                    'severity': 'warning',
                    'message': f'Disk usage is {disk_percent:.1f}%'
                })
                
        except Exception as e:
            logger.error(f"Disk usage check failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Checking memory usage', 'progress': 40}
        )
        
        # Check memory usage
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            maintenance_results['memory_usage_checked'] = True
            maintenance_results['memory_usage_percent'] = round(memory_percent, 2)
            
            if memory_percent > 90:
                maintenance_results['alerts_generated'].append({
                    'type': 'memory_usage',
                    'severity': 'critical',
                    'message': f'Memory usage is {memory_percent:.1f}%'
                })
            elif memory_percent > 80:
                maintenance_results['alerts_generated'].append({
                    'type': 'memory_usage',
                    'severity': 'warning',
                    'message': f'Memory usage is {memory_percent:.1f}%'
                })
                
        except Exception as e:
            logger.error(f"Memory usage check failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Checking service health', 'progress': 60}
        )
        
        # Check service health
        try:
            from database.pooling import get_pool_metrics
            from cache.redis_client import get_redis_client
            
            # Check database health
            pool_metrics = get_pool_metrics()
            if pool_metrics.get('health', {}).get('status') != 'healthy':
                maintenance_results['alerts_generated'].append({
                    'type': 'database_health',
                    'severity': 'warning',
                    'message': 'Database connection pool health issues detected'
                })
            
            # Check Redis health
            redis_client = get_redis_client()
            if redis_client and not redis_client.is_available():
                maintenance_results['alerts_generated'].append({
                    'type': 'redis_health',
                    'severity': 'warning',
                    'message': 'Redis connection issues detected'
                })
            
            maintenance_results['service_health_checked'] = True
            
        except Exception as e:
            logger.error(f"Service health check failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Rotating logs', 'progress': 80}
        )
        
        # Rotate logs if needed
        try:
            log_dir = current_app.config.get('LOG_DIR', 'logs')
            if os.path.exists(log_dir):
                # Simple log rotation logic
                import glob
                log_files = glob.glob(os.path.join(log_dir, '*.log'))
                
                for log_file in log_files:
                    try:
                        file_size = os.path.getsize(log_file)
                        # Rotate if file is larger than 100MB
                        if file_size > 100 * 1024 * 1024:
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            rotated_name = f"{log_file}.{timestamp}"
                            shutil.move(log_file, rotated_name)
                            logger.info(f"Rotated log file: {log_file} -> {rotated_name}")
                    except Exception as e:
                        logger.error(f"Failed to rotate log file {log_file}: {e}")
                
                maintenance_results['log_rotation_completed'] = True
                
        except Exception as e:
            logger.error(f"Log rotation failed: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Maintenance completed', 'progress': 100}
        )
        
        logger.info("System health maintenance completed")
        
        return {
            'status': 'success',
            'maintenance_results': maintenance_results,
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"System health maintenance failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'maintenance_results': maintenance_results
        }


@celery_app.task(bind=True)
def sync_cully_statistics_task(self) -> Dict[str, Any]:
    """
    Synchronize statistics from Cully.ie website.
    This task runs daily to keep numbers up-to-date.
    """
    try:
        logger.info("Starting Cully statistics synchronization")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Fetching data from Cully.ie', 'progress': 20}
        )
        
        # Import the model after app context is available
        from models import CullyStatistics
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Updating database', 'progress': 60}
        )
        
        # Use the model's built-in sync method
        success = CullyStatistics.fetch_and_update_from_cully()
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Sync completed', 'progress': 100}
        )
        
        if success:
            # Get updated statistics
            stats = CullyStatistics.get_current_statistics()
            logger.info(f"Successfully synced Cully statistics: {stats}")
            
            return {
                'status': 'success',
                'statistics': stats,
                'completed_at': datetime.utcnow().isoformat(),
                'message': 'Statistics successfully synchronized from Cully.ie'
            }
        else:
            logger.warning("Failed to sync Cully statistics, using cached data")
            stats = CullyStatistics.get_current_statistics()
            
            return {
                'status': 'partial_success',
                'statistics': stats,
                'completed_at': datetime.utcnow().isoformat(),
                'message': 'Using cached statistics due to sync failure'
            }
            
    except Exception as e:
        logger.error(f"Cully statistics sync failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'completed_at': datetime.utcnow().isoformat()
        }