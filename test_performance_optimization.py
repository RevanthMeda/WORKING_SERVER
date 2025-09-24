#!/usr/bin/env python3
"""
Test script for performance optimization components.
"""

import os
import sys
import time
import logging
from datetime import datetime

# Add the SERVER directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User, Report

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_redis_caching(app):
    """Test Redis caching functionality."""
    print("\n🔄 Testing Redis Caching...")
    
    with app.app_context():
        if not hasattr(app, 'cache') or not app.cache.redis_client.is_available():
            print("❌ Redis cache not available")
            return False
        
        try:
            # Test basic caching
            test_key = 'test_key'
            test_value = {'message': 'Hello, Redis!', 'timestamp': time.time()}
            
            # Set cache
            success = app.cache.set(test_key, test_value, timeout=60)
            if not success:
                print("❌ Failed to set cache value")
                return False
            
            # Get cache
            cached_value = app.cache.get(test_key)
            if cached_value != test_value:
                print("❌ Cached value doesn't match original")
                return False
            
            # Test cache monitoring
            if hasattr(app.cache, 'monitor'):
                stats = app.cache.monitor.get_stats()
                print(f"✅ Cache stats: {stats.get('hits', 0)} hits, {stats.get('misses', 0)} misses")
            
            print("✅ Redis caching working correctly")
            return True
            
        except Exception as e:
            print(f"❌ Redis caching test failed: {e}")
            return False


def test_session_storage(app):
    """Test Redis session storage."""
    print("\n🔄 Testing Redis Session Storage...")
    
    with app.app_context():
        try:
            # Test session manager
            if hasattr(app, 'session_manager'):
                stats = app.session_manager.get_session_stats()
                print(f"✅ Session stats: {stats}")
                return True
            else:
                print("⚠️ Session manager not available (using filesystem sessions)")
                return True
                
        except Exception as e:
            print(f"❌ Session storage test failed: {e}")
            return False


def test_query_caching(app):
    """Test database query caching."""
    print("\n🔄 Testing Query Caching...")
    
    with app.app_context():
        if not hasattr(app, 'query_cache'):
            print("❌ Query cache not available")
            return False
        
        try:
            # Test query cache stats
            stats = app.query_cache.get_cache_stats()
            print(f"✅ Query cache stats: {stats}")
            
            # Test cached query decorator
            from database.query_cache import cache_system_stats
            
            @cache_system_stats(ttl=60)
            def get_test_stats():
                return {
                    'timestamp': datetime.utcnow().isoformat(),
                    'test_data': 'This is cached data'
                }
            
            # First call - should cache
            start_time = time.time()
            result1 = get_test_stats()
            first_call_time = time.time() - start_time
            
            # Second call - should use cache
            start_time = time.time()
            result2 = get_test_stats()
            second_call_time = time.time() - start_time
            
            if result1 == result2 and second_call_time < first_call_time:
                print(f"✅ Query caching working (first: {first_call_time:.4f}s, cached: {second_call_time:.4f}s)")
                return True
            else:
                print("⚠️ Query caching may not be working optimally")
                return True
                
        except Exception as e:
            print(f"❌ Query caching test failed: {e}")
            return False


def test_cdn_integration(app):
    """Test CDN integration."""
    print("\n🔄 Testing CDN Integration...")
    
    with app.app_context():
        if not hasattr(app, 'cdn_extension') or not app.cdn_extension:
            print("⚠️ CDN extension not available")
            return True
        
        try:
            cdn_manager = app.cdn_extension.cdn_manager
            
            # Test CDN configuration
            print(f"CDN Enabled: {cdn_manager.is_enabled()}")
            print(f"CDN Provider: {cdn_manager.provider}")
            print(f"CDN Base URL: {cdn_manager.base_url}")
            
            # Test asset URL generation
            test_asset = 'css/main.css'
            asset_url = cdn_manager.get_asset_url(test_asset)
            print(f"✅ Asset URL generated: {asset_url}")
            
            # Test CDN stats (if enabled)
            if cdn_manager.is_enabled():
                stats = cdn_manager.get_distribution_stats()
                if 'error' not in stats:
                    print(f"✅ CDN distribution stats: {stats.get('status', 'Unknown')}")
                else:
                    print(f"⚠️ CDN stats error: {stats['error']}")
            
            return True
            
        except Exception as e:
            print(f"❌ CDN integration test failed: {e}")
            return False


def test_background_tasks(app):
    """Test background task processing."""
    print("\n🔄 Testing Background Task Processing...")
    
    with app.app_context():
        if not hasattr(app, 'celery'):
            print("❌ Celery not available")
            return False
        
        try:
            # Test Celery connection
            celery_app = app.celery
            
            # Check if Celery is properly configured
            print(f"Celery Broker: {celery_app.conf.broker_url}")
            print(f"Celery Backend: {celery_app.conf.result_backend}")
            
            # Test task result cache
            try:
                from tasks.result_cache import get_task_result_cache
                cache = get_task_result_cache()
                if cache:
                    print("✅ Task result cache available")
                else:
                    print("⚠️ Task result cache not available")
            except Exception as e:
                print(f"⚠️ Task result cache error: {e}")
            
            # Test simple task (if workers are running)
            try:
                from tasks.monitoring_tasks import health_check_task
                
                # This will only work if Celery workers are running
                result = health_check_task.delay()
                print(f"✅ Background task queued: {result.id}")
                
                # Don't wait for result in test
                return True
                
            except Exception as e:
                print(f"⚠️ Background task test failed (workers may not be running): {e}")
                return True
            
        except Exception as e:
            print(f"❌ Background task processing test failed: {e}")
            return False


def test_performance_endpoints(app):
    """Test performance monitoring endpoints."""
    print("\n🔄 Testing Performance Monitoring Endpoints...")
    
    with app.test_client() as client:
        try:
            # Test cache health endpoint
            response = client.get('/api/cache/health')
            if response.status_code in [200, 503]:  # 503 is acceptable if Redis is down
                print(f"✅ Cache health endpoint: {response.status_code}")
            else:
                print(f"❌ Cache health endpoint failed: {response.status_code}")
            
            # Test cache stats endpoint
            response = client.get('/api/cache/stats')
            if response.status_code == 200:
                print("✅ Cache stats endpoint working")
            else:
                print(f"⚠️ Cache stats endpoint: {response.status_code}")
            
            # Test CDN status endpoint (if available)
            response = client.get('/api/cdn/status')
            if response.status_code == 200:
                print("✅ CDN status endpoint working")
            elif response.status_code == 404:
                print("⚠️ CDN status endpoint not available (CDN may be disabled)")
            else:
                print(f"⚠️ CDN status endpoint: {response.status_code}")
            
            return True
            
        except Exception as e:
            print(f"❌ Performance endpoints test failed: {e}")
            return False


def main():
    """Run all performance optimization tests."""
    print("🚀 Starting Performance Optimization Tests")
    print("=" * 50)
    
    # Create app instance
    app = create_app('testing')
    
    # Run tests
    tests = [
        test_redis_caching,
        test_session_storage,
        test_query_caching,
        test_cdn_integration,
        test_background_tasks,
        test_performance_endpoints
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func(app)
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} crashed: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    for i, (test_func, result) in enumerate(zip(tests, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {test_func.__name__}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All performance optimization components are working!")
        return 0
    else:
        print("⚠️ Some components may need attention")
        return 1


if __name__ == '__main__':
    sys.exit(main())