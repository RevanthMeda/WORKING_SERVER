#!/usr/bin/env python3
"""
Verification script for background task processing implementation.
"""
import sys
import os
import traceback
from datetime import datetime

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all task modules can be imported."""
    print("Testing imports...")
    
    try:
        # Test Celery app
        from tasks.celery_app import make_celery, init_celery, get_celery_app
        print("✓ Celery app imports successful")
        
        # Test result cache
        from tasks.result_cache import TaskResultCache, TaskResult, get_task_result_cache
        print("✓ Result cache imports successful")
        
        # Test failure handler
        from tasks.failure_handler import TaskFailureHandler, FailureType, get_failure_handler
        print("✓ Failure handler imports successful")
        
        # Test monitoring
        from tasks.monitoring import TaskMonitor, get_task_monitor
        print("✓ Monitoring imports successful")
        
        # Test task modules
        from tasks.email_tasks import send_email_task
        from tasks.report_tasks import generate_report_task
        from tasks.maintenance_tasks import cleanup_old_files_task
        from tasks.monitoring_tasks import collect_metrics_task
        print("✓ Task modules imports successful")
        
        # Test CLI
        from tasks.cli import tasks
        print("✓ CLI imports successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Import failed: {e}")
        traceback.print_exc()
        return False

def test_task_result_cache():
    """Test TaskResult and TaskResultCache functionality."""
    print("\nTesting TaskResult and TaskResultCache...")
    
    try:
        from tasks.result_cache import TaskResult, TaskResultCache
        
        # Test TaskResult creation
        task_result = TaskResult(
            task_id='test-123',
            task_name='test_task',
            status='SUCCESS',
            progress=100,
            current_step='Completed'
        )
        
        # Test serialization
        data = task_result.to_dict()
        assert isinstance(data, dict)
        assert data['task_id'] == 'test-123'
        
        # Test deserialization
        restored = TaskResult.from_dict(data)
        assert restored.task_id == task_result.task_id
        
        print("✓ TaskResult functionality working")
        
        # Test TaskResultCache (without Redis)
        cache = TaskResultCache()
        assert cache is not None
        
        print("✓ TaskResultCache creation successful")
        
        return True
        
    except Exception as e:
        print(f"✗ TaskResult/Cache test failed: {e}")
        traceback.print_exc()
        return False

def test_failure_handler():
    """Test TaskFailureHandler functionality."""
    print("\nTesting TaskFailureHandler...")
    
    try:
        from tasks.failure_handler import TaskFailureHandler, FailureType
        
        handler = TaskFailureHandler()
        
        # Test failure classification
        timeout_error = Exception("Task timeout exceeded")
        failure_type = handler.classify_failure(timeout_error, 'test_task')
        assert failure_type == FailureType.TIMEOUT
        
        network_error = Exception("Connection refused")
        failure_type = handler.classify_failure(network_error, 'test_task')
        assert failure_type == FailureType.NETWORK_ERROR
        
        print("✓ Failure classification working")
        
        return True
        
    except Exception as e:
        print(f"✗ Failure handler test failed: {e}")
        traceback.print_exc()
        return False

def test_monitoring():
    """Test TaskMonitor functionality."""
    print("\nTesting TaskMonitor...")
    
    try:
        from tasks.monitoring import TaskMonitor, TaskMetrics
        
        monitor = TaskMonitor()
        assert monitor is not None
        
        # Test metrics creation
        metrics = TaskMetrics()
        metrics.total_tasks = 10
        metrics.successful_tasks = 8
        metrics.failed_tasks = 2
        
        data = metrics.to_dict()
        assert data['total_tasks'] == 10
        assert data['successful_tasks'] == 8
        
        print("✓ TaskMonitor and TaskMetrics working")
        
        return True
        
    except Exception as e:
        print(f"✗ Monitoring test failed: {e}")
        traceback.print_exc()
        return False

def test_celery_configuration():
    """Test Celery configuration."""
    print("\nTesting Celery configuration...")
    
    try:
        from flask import Flask
        from tasks.celery_app import make_celery
        
        # Create minimal Flask app
        app = Flask(__name__)
        app.config.update({
            'CELERY_BROKER_URL': 'redis://localhost:6379/1',
            'CELERY_RESULT_BACKEND': 'redis://localhost:6379/2'
        })
        
        # Create Celery app
        celery_app = make_celery(app)
        assert celery_app is not None
        
        # Test configuration
        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.accept_content == ['json']
        assert celery_app.conf.result_serializer == 'json'
        assert celery_app.conf.timezone == 'UTC'
        
        print("✓ Celery configuration working")
        
        return True
        
    except Exception as e:
        print(f"✗ Celery configuration test failed: {e}")
        traceback.print_exc()
        return False

def test_api_integration():
    """Test API integration."""
    print("\nTesting API integration...")
    
    try:
        from api.tasks import tasks_ns
        
        # Check that namespace is created
        assert tasks_ns is not None
        assert tasks_ns.name == 'tasks'
        
        print("✓ API integration working")
        
        return True
        
    except Exception as e:
        print(f"✗ API integration test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all verification tests."""
    print("=== Background Task Processing Verification ===")
    print(f"Started at: {datetime.now()}")
    
    tests = [
        test_imports,
        test_task_result_cache,
        test_failure_handler,
        test_monitoring,
        test_celery_configuration,
        test_api_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print(f"\n=== Results ===")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    
    if failed == 0:
        print("🎉 All tests passed! Background task processing implementation is working.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == '__main__':
    sys.exit(main())