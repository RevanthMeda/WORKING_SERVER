"""
CLI commands for background task management.
"""
import click
import json
from datetime import datetime
from flask.cli import with_appcontext
from .celery_app import get_celery_app
from .monitoring import get_task_monitor
from .result_cache import get_task_result_cache
from .failure_handler import get_failure_handler


@click.group()
def tasks():
    """Task management commands."""
    pass


@tasks.command()
@click.option('--hours', default=24, help='Hours to analyze')
@with_appcontext
def status(hours):
    """Show task system status."""
    try:
        monitor = get_task_monitor()
        
        # Get overall metrics
        metrics = monitor.get_overall_metrics(hours)
        
        click.echo(f"\n=== Task System Status (Last {hours} hours) ===")
        click.echo(f"Total Tasks: {metrics.total_tasks}")
        click.echo(f"Successful: {metrics.successful_tasks} ({metrics.success_rate:.1f}%)")
        click.echo(f"Failed: {metrics.failed_tasks} ({metrics.failure_rate:.1f}%)")
        click.echo(f"Pending: {metrics.pending_tasks}")
        click.echo(f"In Progress: {metrics.in_progress_tasks}")
        click.echo(f"Avg Execution Time: {metrics.avg_execution_time:.2f}s")
        
        # Get worker status
        worker_metrics = monitor.get_worker_metrics()
        click.echo(f"\n=== Workers ===")
        if worker_metrics:
            for worker in worker_metrics:
                click.echo(f"Worker: {worker.worker_name}")
                click.echo(f"  Status: {worker.status}")
                click.echo(f"  Active Tasks: {worker.active_tasks}")
                click.echo(f"  Processed Tasks: {worker.processed_tasks}")
        else:
            click.echo("No active workers found")
        
    except Exception as e:
        click.echo(f"Error getting status: {e}", err=True)


@tasks.command()
@click.option('--hours', default=24, help='Hours to analyze')
@click.option('--output', default=None, help='Output file path')
@with_appcontext
def report(hours, output):
    """Generate comprehensive task monitoring report."""
    try:
        monitor = get_task_monitor()
        report_data = monitor.get_comprehensive_report(hours)
        
        if output:
            with open(output, 'w') as f:
                json.dump(report_data, f, indent=2)
            click.echo(f"Report saved to {output}")
        else:
            click.echo(json.dumps(report_data, indent=2))
            
    except Exception as e:
        click.echo(f"Error generating report: {e}", err=True)


@tasks.command()
@with_appcontext
def workers():
    """Show detailed worker information."""
    try:
        celery_app = get_celery_app()
        if not celery_app:
            click.echo("Celery not available", err=True)
            return
        
        inspect = celery_app.control.inspect()
        
        # Get worker stats
        stats = inspect.stats()
        active_tasks = inspect.active()
        reserved_tasks = inspect.reserved()
        
        if not stats:
            click.echo("No workers found")
            return
        
        click.echo("\n=== Worker Details ===")
        for worker_name, worker_stats in stats.items():
            click.echo(f"\nWorker: {worker_name}")
            click.echo(f"  Status: Online")
            
            # Pool info
            pool_info = worker_stats.get('pool', {})
            click.echo(f"  Pool: {pool_info.get('implementation', 'unknown')}")
            click.echo(f"  Pool Size: {pool_info.get('max-concurrency', 'unknown')}")
            
            # Active tasks
            active_count = len(active_tasks.get(worker_name, [])) if active_tasks else 0
            click.echo(f"  Active Tasks: {active_count}")
            
            # Reserved tasks
            reserved_count = len(reserved_tasks.get(worker_name, [])) if reserved_tasks else 0
            click.echo(f"  Reserved Tasks: {reserved_count}")
            
            # Total processed
            total_stats = worker_stats.get('total', {})
            total_processed = sum(total_stats.values()) if total_stats else 0
            click.echo(f"  Total Processed: {total_processed}")
            
    except Exception as e:
        click.echo(f"Error getting worker info: {e}", err=True)


@tasks.command()
@click.option('--task-id', required=True, help='Task ID to inspect')
@with_appcontext
def inspect(task_id):
    """Inspect a specific task."""
    try:
        # Get from cache first
        cache = get_task_result_cache()
        cached_result = cache.get_result(task_id)
        
        if cached_result:
            click.echo(f"\n=== Cached Task Result ===")
            click.echo(f"Task ID: {cached_result.task_id}")
            click.echo(f"Task Name: {cached_result.task_name}")
            click.echo(f"Status: {cached_result.status}")
            click.echo(f"Progress: {cached_result.progress}%")
            click.echo(f"Current Step: {cached_result.current_step}")
            if cached_result.started_at:
                click.echo(f"Started: {cached_result.started_at}")
            if cached_result.completed_at:
                click.echo(f"Completed: {cached_result.completed_at}")
            if cached_result.worker:
                click.echo(f"Worker: {cached_result.worker}")
            if cached_result.error:
                click.echo(f"Error: {cached_result.error}")
            if cached_result.result:
                click.echo(f"Result: {json.dumps(cached_result.result, indent=2)}")
        
        # Get from Celery
        celery_app = get_celery_app()
        if celery_app:
            result = celery_app.AsyncResult(task_id)
            click.echo(f"\n=== Celery Task Result ===")
            click.echo(f"Task ID: {task_id}")
            click.echo(f"Status: {result.status}")
            if result.result:
                click.echo(f"Result: {json.dumps(result.result, indent=2)}")
            if result.traceback:
                click.echo(f"Traceback: {result.traceback}")
        
    except Exception as e:
        click.echo(f"Error inspecting task: {e}", err=True)


@tasks.command()
@click.option('--hours', default=24, help='Hours to analyze')
@with_appcontext
def failures(hours):
    """Show task failure analysis."""
    try:
        failure_handler = get_failure_handler()
        failure_stats = failure_handler.get_failure_statistics(hours)
        
        if not failure_stats.get('available'):
            click.echo("Failure statistics not available")
            return
        
        click.echo(f"\n=== Failure Analysis (Last {hours} hours) ===")
        click.echo(f"Total Failures: {failure_stats['total_failures']}")
        click.echo(f"Failure Rate: {failure_stats['failure_rate']:.2f} failures/hour")
        
        # Failure types
        failure_types = failure_stats.get('failure_types', {})
        if failure_types:
            click.echo(f"\n=== Failure Types ===")
            for failure_type, count in failure_types.items():
                click.echo(f"  {failure_type}: {count}")
        
        # Task names
        task_names = failure_stats.get('task_names', {})
        if task_names:
            click.echo(f"\n=== Failed Tasks ===")
            for task_name, count in task_names.items():
                click.echo(f"  {task_name}: {count}")
        
    except Exception as e:
        click.echo(f"Error getting failure analysis: {e}", err=True)


@tasks.command()
@with_appcontext
def cache_stats():
    """Show task result cache statistics."""
    try:
        cache = get_task_result_cache()
        stats = cache.get_cache_stats()
        
        click.echo(f"\n=== Cache Statistics ===")
        if stats.get('available'):
            click.echo(f"Total Cached Results: {stats['total_cached_results']}")
            click.echo(f"Cache Prefix: {stats['cache_prefix']}")
            click.echo(f"Default TTL: {stats['default_ttl']} seconds")
            
            status_dist = stats.get('status_distribution', {})
            if status_dist:
                click.echo(f"\n=== Status Distribution ===")
                for status, count in status_dist.items():
                    click.echo(f"  {status}: {count}")
        else:
            click.echo("Cache not available")
            if 'error' in stats:
                click.echo(f"Error: {stats['error']}")
        
    except Exception as e:
        click.echo(f"Error getting cache stats: {e}", err=True)


@tasks.command()
@with_appcontext
def cache_cleanup():
    """Clean up expired task results from cache."""
    try:
        cache = get_task_result_cache()
        cleaned_count = cache.cleanup_expired_results()
        
        click.echo(f"Cleaned up {cleaned_count} expired task results")
        
    except Exception as e:
        click.echo(f"Error cleaning up cache: {e}", err=True)


@tasks.command()
@click.option('--queue', default='celery', help='Queue name')
@with_appcontext
def purge(queue):
    """Purge all tasks from a queue."""
    try:
        celery_app = get_celery_app()
        if not celery_app:
            click.echo("Celery not available", err=True)
            return
        
        # Purge queue
        celery_app.control.purge()
        click.echo(f"Purged all tasks from queue: {queue}")
        
    except Exception as e:
        click.echo(f"Error purging queue: {e}", err=True)


@tasks.command()
@click.option('--task-name', required=True, help='Task name to test')
@click.option('--args', default='[]', help='Task arguments as JSON')
@click.option('--kwargs', default='{}', help='Task keyword arguments as JSON')
@with_appcontext
def test(task_name, args, kwargs):
    """Test a task by running it asynchronously."""
    try:
        celery_app = get_celery_app()
        if not celery_app:
            click.echo("Celery not available", err=True)
            return
        
        # Parse arguments
        task_args = json.loads(args)
        task_kwargs = json.loads(kwargs)
        
        # Send task
        result = celery_app.send_task(task_name, args=task_args, kwargs=task_kwargs)
        
        click.echo(f"Task sent: {result.id}")
        click.echo(f"Task name: {task_name}")
        click.echo(f"Arguments: {task_args}")
        click.echo(f"Keyword arguments: {task_kwargs}")
        
        # Wait for result (with timeout)
        try:
            task_result = result.get(timeout=30)
            click.echo(f"Task completed successfully")
            click.echo(f"Result: {json.dumps(task_result, indent=2)}")
        except Exception as e:
            click.echo(f"Task failed or timed out: {e}")
        
    except Exception as e:
        click.echo(f"Error testing task: {e}", err=True)
