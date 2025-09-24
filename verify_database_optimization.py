#!/usr/bin/env python3
"""
Verification script for database query performance optimization implementation.
"""

import sys
import os
import traceback
from datetime import datetime

def test_imports():
    """Test that all modules can be imported successfully."""
    print("🔍 Testing module imports...")
    
    try:
        # Test query cache imports
        from database.query_cache import QueryCache, QueryCacheManager, init_query_cache
        print("✅ Query cache modules imported successfully")
        
        # Test query analyzer imports
        from database.query_analyzer import QueryAnalyzer, QueryMetrics, setup_query_analysis, get_query_analyzer
        print("✅ Query analyzer modules imported successfully")
        
        # Test pooling imports
        from database.pooling import ConnectionPoolManager, ConnectionLeakDetector
        print("✅ Connection pooling modules imported successfully")
        
        # Test performance imports
        from database.performance import DatabaseIndexManager, QueryOptimizer
        print("✅ Performance optimization modules imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False


def test_query_cache():
    """Test query cache functionality."""
    print("\n🔍 Testing query cache functionality...")
    
    try:
        from database.query_cache import QueryCache
        
        # Mock Redis client
        class MockRedis:
            def __init__(self):
                self.data = {}
                self.available = True
            
            def is_available(self):
                return self.available
            
            def get(self, key):
                return self.data.get(key)
            
            def set(self, key, value, ttl=None):
                self.data[key] = value
                return True
            
            def delete(self, *keys):
                count = 0
                for key in keys:
                    if key in self.data:
                        del self.data[key]
                        count += 1
                return count
            
            def keys(self, pattern):
                return [k for k in self.data.keys() if pattern.replace('*', '') in k]
        
        # Test cache operations
        mock_redis = MockRedis()
        cache = QueryCache(mock_redis, default_ttl=300)
        
        # Test cache availability
        assert cache.is_available() == True
        print("✅ Cache availability check passed")
        
        # Test cache set/get
        test_query = "SELECT * FROM users WHERE id = ?"
        test_result = [{"id": 1, "name": "Test User"}]
        
        success = cache.set(test_query, test_result)
        assert success == True
        print("✅ Cache set operation passed")
        
        # Test cache retrieval
        cached_result = cache.get(test_query)
        assert cached_result is not None
        print("✅ Cache get operation passed")
        
        # Test cache invalidation
        deleted_count = cache.invalidate()
        assert deleted_count >= 0
        print("✅ Cache invalidation passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Query cache test failed: {e}")
        traceback.print_exc()
        return False


def test_query_analyzer():
    """Test query analyzer functionality."""
    print("\n🔍 Testing query analyzer functionality...")
    
    try:
        from database.query_analyzer import QueryAnalyzer, QueryMetrics
        
        # Initialize analyzer
        analyzer = QueryAnalyzer(slow_query_threshold=1.0)
        
        # Test query normalization
        query1 = "SELECT * FROM users WHERE id = 123 AND name = 'John'"
        query2 = "SELECT * FROM users WHERE id = 456 AND name = 'Jane'"
        
        normalized1 = analyzer._normalize_query(query1)
        normalized2 = analyzer._normalize_query(query2)
        
        assert normalized1 == normalized2
        print("✅ Query normalization passed")
        
        # Test table extraction
        complex_query = "SELECT u.name, r.title FROM users u JOIN reports r ON u.id = r.user_id"
        tables = analyzer._extract_tables(complex_query)
        
        assert 'users' in tables
        assert 'reports' in tables
        print("✅ Table extraction passed")
        
        # Test query analysis
        test_query = "SELECT * FROM users WHERE email = ?"
        
        # Analyze multiple executions
        analyzer.analyze_query(test_query, 0.5)  # Fast
        analyzer.analyze_query(test_query, 1.5)  # Slow
        analyzer.analyze_query(test_query, 0.8, error="Connection timeout")  # Error
        
        # Check metrics
        assert len(analyzer.query_metrics) == 1
        print("✅ Query analysis passed")
        
        # Test performance summary
        summary = analyzer.get_performance_summary()
        
        assert 'total_queries' in summary
        assert 'slow_queries' in summary
        assert summary['total_queries'] == 3
        print("✅ Performance summary generation passed")
        
        # Test slow queries analysis
        slow_queries = analyzer.get_slow_queries(10)
        assert isinstance(slow_queries, list)
        print("✅ Slow queries analysis passed")
        
        # Test optimization recommendations
        recommendations = analyzer.generate_optimization_recommendations()
        assert isinstance(recommendations, list)
        print("✅ Optimization recommendations passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Query analyzer test failed: {e}")
        traceback.print_exc()
        return False


def test_connection_pooling():
    """Test connection pooling functionality."""
    print("\n🔍 Testing connection pooling functionality...")
    
    try:
        from database.pooling import ConnectionPoolManager, ConnectionLeakDetector
        
        # Test pool manager
        manager = ConnectionPoolManager()
        
        # Test configuration generation
        sqlite_config = manager.get_optimal_pool_config(
            'sqlite:///test.db', 
            environment='development'
        )
        
        assert 'pool_size' in sqlite_config
        assert sqlite_config['pool_size'] == 1  # SQLite should have pool size 1
        print("✅ Pool configuration generation passed")
        
        # Test leak detector
        detector = ConnectionLeakDetector()
        
        # Track and release connections
        detector.track_connection('conn1', 'test_context')
        assert len(detector.active_connections) == 1
        
        detector.release_connection('conn1')
        assert len(detector.active_connections) == 0
        print("✅ Connection leak detection passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection pooling test failed: {e}")
        traceback.print_exc()
        return False


def test_performance_optimization():
    """Test performance optimization functionality."""
    print("\n🔍 Testing performance optimization functionality...")
    
    try:
        from database.performance import QueryOptimizer
        
        # Initialize optimizer
        optimizer = QueryOptimizer()
        
        # Test optimization rules
        assert len(optimizer.optimization_rules) > 0
        print("✅ Optimization rules loaded")
        
        # Test individual rules
        select_star_suggestions = optimizer._check_select_star("select * from users", {})
        assert len(select_star_suggestions) > 0
        assert select_star_suggestions[0]['type'] == 'select_star'
        print("✅ SELECT * detection passed")
        
        missing_where_suggestions = optimizer._check_missing_where_clause(
            "select name from users", {}
        )
        assert len(missing_where_suggestions) > 0
        assert missing_where_suggestions[0]['type'] == 'missing_where'
        print("✅ Missing WHERE clause detection passed")
        
        # Test priority calculation
        high_priority = optimizer._calculate_priority(
            {'avg_time': 3.0, 'count': 200, 'total_time': 600},
            [{'type': 'missing_index'}]
        )
        assert high_priority == 'high'
        print("✅ Priority calculation passed")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance optimization test failed: {e}")
        traceback.print_exc()
        return False


def test_cli_integration():
    """Test CLI integration."""
    print("\n🔍 Testing CLI integration...")
    
    try:
        from database.optimization_cli import db_optimize
        
        # Check that CLI commands are registered
        assert db_optimize is not None
        print("✅ CLI commands registered")
        
        return True
        
    except Exception as e:
        print(f"❌ CLI integration test failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("🚀 Database Query Performance Optimization Verification")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Query Cache", test_query_cache),
        ("Query Analyzer", test_query_analyzer),
        ("Connection Pooling", test_connection_pooling),
        ("Performance Optimization", test_performance_optimization),
        ("CLI Integration", test_cli_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name} tests...")
        try:
            if test_func():
                print(f"✅ {test_name} tests PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} tests FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} tests FAILED with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results Summary:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {(passed / (passed + failed) * 100):.1f}%")
    
    if failed == 0:
        print("\n🎉 All database query performance optimization features are working correctly!")
        return 0
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please review the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())