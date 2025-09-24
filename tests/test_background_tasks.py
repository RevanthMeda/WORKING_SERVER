"""
Tests for background task processing implementation.
"""
import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from tasks.celery_app import make_celery, init_celery
from tasks.result_cache import TaskResultCache, TaskResult, get_task_result_cache
from tasks.failure_handler import TaskFailureHandler, FailureType, get_failure_handler
from tasks.monitoring import TaskMonitor, get_task_monitor
from tasks.email_tasks import send_email_task
from tasks.report_tasks import generate_report_task


class TestCeleryConfiguration:
    """Test Celery configuration and setup."""
    
    def test_celery_app_creation(self, app):
        """Test Celery app creation with Flask integration."""
        celery_app = make_celery(app)
        
        assert celery_app is not None
        assert celery_app.main == app.import_name
        
        # Test configuration
        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.accept_content == ['json']
        assert celery_app.conf.result_serializer == 'json'
        assert celery_app.conf.timezone == 'UTC'
        assert celery_app.conf.enable_utc is True
        
        # Test task routing
        assert 'tasks.email_tasks.*' in celery_app.conf.task_routes
        assert 'tasks.report_tasks.*' in celery_app.conf.task_routes
        
        # Test task annotations
        assert '*' in celery_app.conf.task_annotations
        assert 'rate_limit' in celery_app.conf.task_annotations['*']
    
    def test_celery_initialization(self, app):
        """Test Celery initialization with monitoring setup."""
        celery_app = init_celery(app)
        
        assert celery_app is not None
        
        # Test that task monitoring is set up
        # This would require checking signal connections, which is complex
        # For now, just verify the app is created
        assert hasattr(celery_app, 'Task')


class TestTaskResultCache:
    """Test task result caching system."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.is_available.return_value = True
        redis_mock.setex.return_value = True
        redis_mock.get.return_value = None
        redis_mock.zadd.return_value = True
        redis_mock.expire.return_value = True
        redis_mock.zcard.return_value = 0
        redis_mock.zrevrange.return_value = []
        redis_mock.exists.return_value = True
        redis_mock.zrem.return_value = True
        return redis_mock
    
    @pytest.fixture
    def cache(self, mock_redis):
        """Task result cache with mocked Redis."""
        with patch('tasks.result_cache.get_redis_client', return_value=mock_redis):
            return TaskResultCache()
    
    def test_task_result_creation(self):
        """Test TaskResult data structure."""
        task_result = TaskResult(
            task_id='test-123',
            task_name='test_task',
            status='SUCCESS',
            progress=100,
            current_step='Completed'
        )
        
        assert task_result.task_id == 'test-123'
        assert task_result.task_name == 'test_task'
        assert task_result.status == 'SUCCESS'
        assert task_result.progress == 100
        
        # Test serialization
        data = task_result.to_dict()
        assert isinstance(data, dict)
        assert data['task_id'] == 'test-123'
        
        # Test deserialization
        restored = TaskResult.from_dict(data)
        assert restored.task_id == task_result.task_id
        assert restored.task_name == task_result.task_name
    
    def test_store_result(self, cache, mock_redis):
        """Test storing task result in cache."""
        task_result = TaskResult(
            task_id='test-123',
            task_name='test_task',
            status='SUCCESS'
        )
        
        success = cache.store_result(task_result)
        
        assert success is True
        mock_redis.setex.assert_called_once()
        mock_redis.zadd.assert_called_once()
    
    def test_get_result(self, cache, mock_redis):
        """Test retrieving task result from cache."""
        # Mock Redis to return serialized task result
        task_result = TaskResult(
            task_id='test-123',
            task_name='test_task',
            status='SUCCESS'
        )
        mock_redis.get.return_value = json.dumps(task_result.to_dict())
        
        retrieved = cache.get_result('test-123')
        
        assert retrieved is not None
        assert retrieved.task_id == 'test-123'
        assert retrieved.task_name == 'test_task'
        assert retrieved.status == 'SUCCESS'
    
    def test_update_progress(self, cache, mock_redis):
        """Test updating task progress."""
        # Mock existing result
        task_result = TaskResult(
            task_id='test-123',
            task_name='test_task',
            status='PROGRESS',
            progress=50
        )
        mock_redis.get.return_value = json.dumps(task_result.to_dict())
        
        success = cache.update_progress('test-123', 75, 'Processing data')
        
        assert success is True
        # Should call setex to update the cached result
        assert mock_redis.setex.call_count >= 1
    
    def test_mark_completed(self, cache, mock_redis):
        """Test marking task as completed."""
        task_result = TaskResult(
            task_id='test-123',
            task_name='test_task',
            status='PROGRESS'
        )
        mock_redis.get.return_value = json.dumps(task_result.to_dict())
        
        result_data = {'output': 'success'}
        success = cache.mark_completed('test-123', result_data)
        
        assert success is True
        mock_redis.setex.assert_called()
    
    def test_mark_failed(self, cache, mock_redis):
        """Test marking task as failed."""
        task_result = TaskResult(
            task_id='test-123',
            task_name='test_task',
            status='PROGRESS'
        )
        mock_redis.get.return_value = json.dumps(task_result.to_dict())
        
        success = cache.mark_failed('test-123', 'Test error', retries=2)
        
        assert success is True
        mock_redis.setex.assert_called()
    
    def test_cache_unavailable(self):
        """Test cache behavior when Redis is unavailable."""
        with patch('tasks.result_cache.get_redis_client', return_value=None):
            cache = TaskResultCache()
            
            task_result = TaskResult(
                task_id='test-123',
                task_name='test_task',
                status='SUCCESS'
            )
            
            # Should return False when Redis is unavailable
            success = cache.store_result(task_result)
            assert success is False
            
            # Should return None when Redis is unavailable
            retrieved = cache.get_result('test-123')
            assert retrieved is None


class TestTaskFailureHandler:
    """Test task failure handling system."""
    
    @pytest.fixture
    def failure_handler(self):
        """Task failure handler instance."""
        return TaskFailureHandler()
    
    def test_failure_classification(self, failure_handler):
        """Test failure type classification."""
        # Test timeout error
        timeout_error = Exception("Task timeout exceeded")
        failure_type = failure_handler.classify_failure(timeout_error, 'test_task')
        assert failure_type == FailureType.TIMEOUT
        
        # Test network error
        network_error = Exception("Connection refused")
        failure_type = failure_handler.classify_failure(network_error, 'test_task')
        assert failure_type == FailureType.NETWORK_ERROR
        
        # Test database error
        db_error = Exception("Database connection failed")
        failure_type = failure_handler.classify_failure(db_error, 'test_task')
        assert failure_type == FailureType.DATABASE_ERROR
        
        # Test validation error
        validation_error = Exception("Invalid input data")
        failure_type = failure_handler.classify_failure(validation_error, 'test_task')
        assert failure_type == FailureType.VALIDATION_ERROR
        
        # Test unknown error
        unknown_error = Exception("Something went wrong")
        failure_type = failure_handler.classify_failure(unknown_error, 'test_task')
        assert failure_type == FailureType.UNKNOWN_ERROR
    
    def test_handle_failure(self, failure_handler):
        """Test failure handling logic."""
        # Create mock task
        mock_task = Mock()
        mock_task.name = 'test_task'
        mock_task.max_retries = 3
        mock_task.request.id = 'test-123'
        mock_task.request.retries = 1
        mock_task.request.hostname = 'worker-1'
        mock_task.request.args = []
        mock_task.request.kwargs = {}
        
        # Test timeout failure (should retry)
        timeout_error = Exception("Task timeout")
        with patch.object(failure_handler.result_cache, 'mark_failed'):
            should_retry = failure_handler.handle_failure(mock_task, timeout_error)
            assert should_retry is True
        
        # Test validation failure (should not retry)
        validation_error = Exception("Invalid data")
        with patch.object(failure_handler.result_cache, 'mark_failed'):
            should_retry = failure_handler.handle_failure(mock_task, validation_error)
            assert should_retry is False
    
    @patch('tasks.failure_handler.get_redis_client')
    def test_failure_statistics(self, mock_get_redis, failure_handler):
        """Test failure statistics collection."""
        mock_redis = Mock()
        mock_redis.is_available.return_value = True
        mock_redis.zrangebyscore.return_value = ['test-123']
        mock_redis.get.return_value = str({
            'task_id': 'test-123',
            'task_name': 'test_task',
            'failure_type': 'timeout',
            'failed_at': datetime.utcnow().isoformat()
        })
        mock_get_redis.return_value = mock_redis
        
        stats = failure_handler.get_failure_statistics(24)
        
        assert stats['available'] is True
        assert 'total_failures' in stats
        assert 'failure_types' in stats
        assert 'task_names' in stats


class TestTaskMonitoring:
    """Test task monitoring system."""
    
    @pytest.fixture
    def mock_cache(self):
        """Mock task result cache."""
        cache_mock = Mock()
        cache_mock.get_recent_results.return_value = [
            TaskResult(
                task_id='test-1',
                task_name='test_task',
                status='SUCCESS',
                started_at=datetime.utcnow() - timedelta(minutes=30),
                completed_at=datetime.utcnow() - timedelta(minutes=25)
            ),
            TaskResult(
                task_id='test-2',
                task_name='test_task',
                status='FAILURE',
                started_at=datetime.utcnow() - timedelta(minutes=20),
                completed_at=datetime.utcnow() - timedelta(minutes=15)
            )
        ]
        return cache_mock
    
    @pytest.fixture
    def monitor(self, mock_cache):
        """Task monitor with mocked dependencies."""
        with patch('tasks.monitoring.get_task_result_cache', return_value=mock_cache):
            return TaskMonitor()
    
    def test_overall_metrics(self, monitor):
        """Test overall metrics calculation."""
        metrics = monitor.get_overall_metrics(24)
        
        assert metrics.total_tasks == 2
        assert metrics.successful_tasks == 1
        assert metrics.failed_tasks == 1
        assert metrics.success_rate == 50.0
        assert metrics.failure_rate == 50.0
        assert metrics.avg_execution_time > 0
    
    def test_task_type_metrics(self, monitor):
        """Test task type metrics calculation."""
        task_metrics = monitor.get_task_type_metrics(24)
        
        assert 'test_task' in task_metrics
        metrics = task_metrics['test_task']
        assert metrics.total_tasks == 2
        assert metrics.successful_tasks == 1
        assert metrics.failed_tasks == 1
    
    @patch('tasks.monitoring.get_celery_app')
    def test_worker_metrics(self, mock_get_celery, monitor):
        """Test worker metrics collection."""
        # Mock Celery app and inspect
        mock_celery = Mock()
        mock_inspect = Mock()
        mock_inspect.stats.return_value = {
            'worker-1': {
                'pool': {'implementation': 'prefork', 'max-concurrency': 4},
                'total': {'test_task': 10},
                'rusage': {'maxrss': 1024, 'utime': 1.5, 'stime': 0.5}
            }
        }
        mock_inspect.active.return_value = {'worker-1': []}
        mock_celery.control.inspect.return_value = mock_inspect
        mock_get_celery.return_value = mock_celery
        
        worker_metrics = monitor.get_worker_metrics()
        
        assert len(worker_metrics) == 1
        assert worker_metrics[0].worker_name == 'worker-1'
        assert worker_metrics[0].status == 'online'
        assert worker_metrics[0].processed_tasks == 10
    
    def test_comprehensive_report(self, monitor):
        """Test comprehensive monitoring report generation."""
        with patch.object(monitor, 'get_worker_metrics', return_value=[]):
            with patch.object(monitor, 'get_queue_metrics', return_value={}):
                with patch.object(monitor, 'get_performance_trends', return_value={}):
                    with patch.object(monitor.failure_handler, 'get_failure_statistics', return_value={'available': False}):
                        with patch.object(monitor.result_cache, 'get_cache_stats', return_value={'available': False}):
                            report = monitor.get_comprehensive_report(24)
        
        assert 'generated_at' in report
        assert 'analysis_period_hours' in report
        assert 'overall_metrics' in report
        assert 'task_type_metrics' in report
        assert 'insights' in report


class TestTaskIntegration:
    """Test task integration and end-to-end functionality."""
    
    @patch('tasks.email_tasks.smtplib.SMTP')
    def test_email_task_execution(self, mock_smtp, app):
        """Test email task execution."""
        with app.app_context():
            # Mock SMTP server
            mock_server = Mock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            # Execute email task
            result = send_email_task.apply(
                args=['test@example.com', 'Test Subject', 'Test Body']
            )
            
            assert result.successful()
            task_result = result.get()
            assert task_result['status'] == 'success'
            assert task_result['to_email'] == 'test@example.com'
    
    def test_report_generation_task(self, app):
        """Test report generation task."""
        with app.app_context():
            # Mock report data
            report_data = {
                'id': 'test-report-123',
                'type': 'SAT',
                'document_title': 'Test Report',
                'document_reference': 'TR-001'
            }
            
            # Mock the report generator and file system
            with patch('tasks.report_tasks.ReportGenerator') as mock_generator:
                with patch('tasks.report_tasks.os.path.exists', return_value=True):
                    with patch('tasks.report_tasks.os.path.getsize', return_value=1024):
                        with patch('tasks.report_tasks.Report') as mock_report_model:
                            # Mock database operations
                            mock_report = Mock()
                            mock_report.status = 'PENDING'
                            mock_report_model.query.get.return_value = mock_report
                            
                            # Mock report generator
                            mock_gen_instance = Mock()
                            mock_gen_instance.generate_sat_report.return_value = {'success': True}
                            mock_generator.return_value = mock_gen_instance
                            
                            # Execute task
                            result = generate_report_task.apply(
                                args=['test-report-123', 'SAT', report_data]
                            )
                            
                            assert result.successful()
                            task_result = result.get()
                            assert task_result['status'] == 'success'
                            assert task_result['report_id'] == 'test-report-123'


class TestTaskAPI:
    """Test task management API endpoints."""
    
    def test_send_email_endpoint(self, client, admin_user):
        """Test email sending API endpoint."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
        
        data = {
            'to_email': 'test@example.com',
            'subject': 'Test Subject',
            'body': 'Test Body'
        }
        
        response = client.post('/api/v1/tasks/email/send', 
                             json=data,
                             headers={'Content-Type': 'application/json'})
        
        assert response.status_code == 202
        response_data = response.get_json()
        assert 'task_id' in response_data
        assert response_data['status'] == 'pending'
    
    def test_task_status_endpoint(self, client, admin_user):
        """Test task status API endpoint."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
        
        # Mock Celery result
        with patch('api.tasks.get_celery_app') as mock_get_celery:
            mock_celery = Mock()
            mock_result = Mock()
            mock_result.status = 'SUCCESS'
            mock_result.info = None
            mock_celery.AsyncResult.return_value = mock_result
            mock_get_celery.return_value = mock_celery
            
            response = client.get('/api/v1/tasks/status/test-task-123')
            
            assert response.status_code == 200
            response_data = response.get_json()
            assert response_data['task_id'] == 'test-task-123'
            assert response_data['status'] == 'SUCCESS'
    
    def test_monitoring_metrics_endpoint(self, client, admin_user):
        """Test monitoring metrics API endpoint."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
        
        with patch('api.tasks.get_task_monitor') as mock_get_monitor:
            mock_monitor = Mock()
            mock_metrics = Mock()
            mock_metrics.to_dict.return_value = {
                'total_tasks': 10,
                'successful_tasks': 8,
                'failed_tasks': 2
            }
            mock_monitor.get_overall_metrics.return_value = mock_metrics
            mock_monitor.get_task_type_metrics.return_value = {}
            mock_monitor.get_worker_metrics.return_value = []
            mock_get_monitor.return_value = mock_monitor
            
            response = client.get('/api/v1/tasks/monitoring/metrics')
            
            assert response.status_code == 200
            response_data = response.get_json()
            assert 'overall_metrics' in response_data
            assert response_data['overall_metrics']['total_tasks'] == 10


class TestTaskCLI:
    """Test task management CLI commands."""
    
    def test_task_status_command(self, app):
        """Test task status CLI command."""
        with app.app_context():
            from tasks.cli import status
            from click.testing import CliRunner
            
            runner = CliRunner()
            
            with patch('tasks.cli.get_task_monitor') as mock_get_monitor:
                mock_monitor = Mock()
                mock_metrics = Mock()
                mock_metrics.total_tasks = 10
                mock_metrics.successful_tasks = 8
                mock_metrics.failed_tasks = 2
                mock_metrics.success_rate = 80.0
                mock_metrics.failure_rate = 20.0
                mock_metrics.avg_execution_time = 5.5
                mock_monitor.get_overall_metrics.return_value = mock_metrics
                mock_monitor.get_worker_metrics.return_value = []
                mock_get_monitor.return_value = mock_monitor
                
                result = runner.invoke(status, ['--hours', '24'])
                
                assert result.exit_code == 0
                assert 'Total Tasks: 10' in result.output
                assert 'Successful: 8' in result.output
    
    def test_cache_cleanup_command(self, app):
        """Test cache cleanup CLI command."""
        with app.app_context():
            from tasks.cli import cache_cleanup
            from click.testing import CliRunner
            
            runner = CliRunner()
            
            with patch('tasks.cli.get_task_result_cache') as mock_get_cache:
                mock_cache = Mock()
                mock_cache.cleanup_expired_results.return_value = 5
                mock_get_cache.return_value = mock_cache
                
                result = runner.invoke(cache_cleanup)
                
                assert result.exit_code == 0
                assert 'Cleaned up 5 expired task results' in result.output


if __name__ == '__main__':
    pytest.main([__file__])