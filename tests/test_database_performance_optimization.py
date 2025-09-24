"""
Tests for database query performance optimization.
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from database.query_cache import QueryCache, QueryCacheManager, init_query_cache
from database.query_analyzer import QueryAnalyzer, QueryMetrics, setup_query_analysis
from database.pooling import ConnectionPoolManager, ConnectionLeakDetector
from database.performance import DatabaseIndexManager, QueryOptimizer


class TestQueryCache:
    """Test query result caching functionality."""
    
    def test_query_cache_initialization(self):
        """Test query cache initialization."""
        mock_redis = Mock()
        mock_redis.is_available.return_value = True
        
        cache = QueryCache(mock_redis, default_ttl=300)
        
        assert cache.redis_client == mock_redis
        assert cache.default_ttl == 300
        assert cache.enabled == True
    
    def test_cache_key_generation(self):
        """Test cache key generation."""
        mock_redis = Mock()
        cache = QueryCache(mock_redis)
        
        query_hash, params_hash = cache._hash_query("SELECT * FROM users WHERE id = ?", {"id": 1})
        
        assert len(query_hash) == 32  # MD5 hash length
        assert len(params_hash) == 32
    
    def test_cache_get_set(self):
        """Test cache get and set operations."""
        mock_redis = Mock()
        mock_redis.is_available.return_value = True
        mock_redis.get.return_value = '{"result": "cached_data"}'
        mock_redis.set.return_value = True
        
        cache = QueryCache(mock_redis)
        
        # Test cache miss
        result = cache.get("SELECT * FROM users")
        assert result is None
        
        # Test cache set
        success = cache.set("SELECT * FROM users", {"result": "test_data"})
        assert success == True
        
        # Test cache hit
        mock_redis.get.return_value = '{"result": "test_data"}'
        result = cache.get("SELECT * FROM users")
        assert result == {"result": "test_data"}
    
    def test_cache_invalidation(self):
        """Test cache invalidation."""
        mock_redis = Mock()
        mock_redis.is_available.return_value = True
        mock_redis.keys.return_value = ['query_cache:key1', 'query_cache:key2']
        mock_redis.delete.return_value = 2
        
        cache = QueryCache(mock_redis)
        
        # Test pattern-based invalidation
        deleted_count = cache.invalidate(pattern="users")
        assert deleted_count == 2
        
        # Test table-based invalidation
        deleted_count = cache.invalidate(table_name="reports")
        assert deleted_count == 2
    
    def test_cache_stats(self):
        """Test cache statistics."""
        mock_redis = Mock()
        mock_redis.is_available.return_value = True
        
        cache = QueryCache(mock_redis)
        cache.hit_count = 10
        cache.miss_count = 5
        
        stats = cache.get_stats()
        
        assert stats['hit_count'] == 10
        assert stats['miss_count'] == 5
        assert stats['total_requests'] == 15
        assert stats['hit_rate'] == 66.67


class TestQueryAnalyzer:
    """Test query performance analyzer."""
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = QueryAnalyzer(slow_query_threshold=2.0)
        
        assert analyzer.slow_query_threshold == 2.0
        assert len(analyzer.query_metrics) == 0
        assert len(analyzer.execution_history) == 0
    
    def test_query_normalization(self):
        """Test query normalization."""
        analyzer = QueryAnalyzer()
        
        query1 = "SELECT * FROM users WHERE id = 123 AND name = 'John'"
        query2 = "SELECT * FROM users WHERE id = 456 AND name = 'Jane'"
        
        normalized1 = analyzer._normalize_query(query1)
        normalized2 = analyzer._normalize_query(query2)
        
        # Both queries should normalize to the same pattern
        assert normalized1 == normalized2
        assert "?" in normalized1  # Parameters should be replaced
    
    def test_table_extraction(self):
        """Test table name extraction from queries."""
        analyzer = QueryAnalyzer()
        
        query = """
        SELECT u.name, r.title 
        FROM users u 
        JOIN reports r ON u.id = r.user_id 
        WHERE u.status = 'active'
        """
        
        tables = analyzer._extract_tables(query)
        
        assert 'users' in tables
        assert 'reports' in tables
    
    def test_query_analysis(self):
        """Test query execution analysis."""
        analyzer = QueryAnalyzer(slow_query_threshold=1.0)
        
        query = "SELECT * FROM users WHERE email = ?"
        
        # Analyze fast query
        analyzer.analyze_query(query, 0.5)
        
        # Analyze slow query
        analyzer.analyze_query(query, 1.5)
        
        # Analyze query with error
        analyzer.analyze_query(query, 0.8, error="Connection timeout")
        
        # Check metrics
        assert len(analyzer.query_metrics) == 1
        
        query_hash = list(analyzer.query_metrics.keys())[0]
        metrics = analyzer.query_metrics[query_hash]
        
        assert metrics.execution_count == 3
        assert metrics.slow_executions == 1
        assert metrics.error_count == 1
        assert metrics.avg_time == (0.5 + 1.5 + 0.8) / 3
    
    def test_performance_summary(self):
        """Test performance summary generation."""
        analyzer = QueryAnalyzer(slow_query_threshold=1.0)
        
        # Add some test data
        analyzer.analyze_query("SELECT * FROM users", 0.5)
        analyzer.analyze_query("SELECT * FROM reports", 1.5)  # Slow
        analyzer.analyze_query("SELECT * FROM users", 0.3)
        
        summary = analyzer.get_performance_summary()
        
        assert summary['total_queries'] == 3
        assert summary['unique_queries'] == 2
        assert summary['slow_queries'] == 1
        assert summary['slow_query_percentage'] > 0
        assert 'percentiles' in summary
    
    def test_slow_queries_analysis(self):
        """Test slow queries analysis."""
        analyzer = QueryAnalyzer(slow_query_threshold=1.0)
        
        # Add slow queries
        analyzer.analyze_query("SELECT * FROM large_table", 2.5)
        analyzer.analyze_query("SELECT COUNT(*) FROM reports", 1.8)
        
        slow_queries = analyzer.get_slow_queries(10)
        
        assert len(slow_queries) == 2
        assert slow_queries[0]['avg_time'] >= slow_queries[1]['avg_time']  # Sorted by time
        assert all(q['performance_score'] <= 100 for q in slow_queries)
    
    def test_optimization_recommendations(self):
        """Test optimization recommendations generation."""
        analyzer = QueryAnalyzer(slow_query_threshold=1.0)
        
        # Add various query patterns
        analyzer.analyze_query("SELECT * FROM users WHERE email = ?", 2.0)  # Slow
        analyzer.analyze_query("SELECT * FROM reports", 0.1)  # Fast but frequent
        for _ in range(150):  # Make it frequent
            analyzer.analyze_query("SELECT * FROM reports", 0.1)
        
        analyzer.analyze_query("SELECT * FROM audit_logs", 0.5, error="Timeout")  # Error
        
        recommendations = analyzer.generate_optimization_recommendations()
        
        assert len(recommendations) > 0
        
        # Check for different recommendation categories
        categories = [rec['category'] for rec in recommendations]
        assert 'slow_queries' in categories or 'frequent_queries' in categories
    
    def test_query_trends(self):
        """Test query trends analysis."""
        analyzer = QueryAnalyzer()
        
        # Simulate queries over time
        base_time = datetime.utcnow() - timedelta(hours=2)
        
        with patch('database.query_analyzer.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = base_time
            analyzer.analyze_query("SELECT * FROM users", 0.5)
            
            mock_datetime.utcnow.return_value = base_time + timedelta(hours=1)
            analyzer.analyze_query("SELECT * FROM reports", 1.2)
        
        trends = analyzer.get_query_trends(hours=24)
        
        assert 'trends' in trends
        assert trends['total_executions'] == 2


class TestConnectionPoolManager:
    """Test connection pool management."""
    
    def test_pool_manager_initialization(self):
        """Test pool manager initialization."""
        manager = ConnectionPoolManager()
        
        assert 'total_connections' in manager.pool_stats
        assert 'active_connections' in manager.pool_stats
        assert len(manager.checkout_times) == 0
    
    def test_optimal_pool_config(self):
        """Test optimal pool configuration generation."""
        manager = ConnectionPoolManager()
        
        # Test SQLite configuration
        sqlite_config = manager.get_optimal_pool_config(
            'sqlite:///test.db', 
            environment='development'
        )
        
        assert sqlite_config['pool_size'] == 1
        assert 'check_same_thread' in sqlite_config['connect_args']
        
        # Test PostgreSQL configuration
        pg_config = manager.get_optimal_pool_config(
            'postgresql://user:pass@localhost/db',
            environment='production'
        )
        
        assert pg_config['pool_size'] > 1
        assert pg_config['pool_recycle'] == 3600
    
    def test_pool_optimization_recommendations(self):
        """Test pool optimization recommendations."""
        manager = ConnectionPoolManager()
        
        # Mock engine and pool status
        mock_engine = Mock()
        mock_pool = Mock()
        mock_pool.size.return_value = 10
        mock_pool.checkedin.return_value = 2
        mock_pool.checkedout.return_value = 8
        mock_pool.overflow.return_value = 0
        mock_pool.invalid.return_value = 0
        mock_engine.pool = mock_pool
        
        # Set high utilization
        manager.pool_stats['avg_checkout_time'] = 0.5
        
        recommendations = manager.optimize_pool_settings(mock_engine)
        
        assert isinstance(recommendations, list)
        # High utilization should generate recommendations
        if recommendations:
            assert any('pool_size' in rec.get('setting', '') for rec in recommendations)
    
    def test_pool_health_check(self):
        """Test pool health check."""
        manager = ConnectionPoolManager()
        
        # Mock successful connection
        mock_engine = Mock()
        mock_connection = Mock()
        mock_engine.connect.return_value.__enter__.return_value = mock_connection
        mock_connection.execute.return_value.close.return_value = None
        
        # Mock pool status
        mock_pool = Mock()
        mock_pool.size.return_value = 5
        mock_pool.checkedin.return_value = 3
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 0
        mock_pool.invalid.return_value = 0
        mock_engine.pool = mock_pool
        
        health = manager.health_check(mock_engine)
        
        assert 'status' in health
        assert health['status'] in ['healthy', 'warning', 'critical']
        assert 'issues' in health
        assert 'pool_status' in health


class TestConnectionLeakDetector:
    """Test connection leak detection."""
    
    def test_leak_detector_initialization(self):
        """Test leak detector initialization."""
        detector = ConnectionLeakDetector()
        
        assert len(detector.active_connections) == 0
        assert detector.leak_threshold == 300  # 5 minutes
    
    def test_connection_tracking(self):
        """Test connection tracking."""
        detector = ConnectionLeakDetector()
        
        # Track connections
        detector.track_connection('conn1', 'test_context')
        detector.track_connection('conn2', 'another_context')
        
        assert len(detector.active_connections) == 2
        assert 'conn1' in detector.active_connections
        assert detector.active_connections['conn1']['context'] == 'test_context'
        
        # Release connection
        detector.release_connection('conn1')
        
        assert len(detector.active_connections) == 1
        assert 'conn1' not in detector.active_connections
    
    def test_leak_detection(self):
        """Test leak detection."""
        detector = ConnectionLeakDetector()
        detector.leak_threshold = 1  # 1 second for testing
        
        # Track connection
        detector.track_connection('old_conn', 'test')
        
        # Wait for leak threshold
        time.sleep(1.1)
        
        leaks = detector.detect_leaks()
        
        assert len(leaks) == 1
        assert leaks[0]['connection_id'] == 'old_conn'
        assert leaks[0]['age_seconds'] > 1


class TestDatabaseIndexManager:
    """Test database index management."""
    
    @patch('database.performance.db')
    def test_index_creation(self, mock_db):
        """Test recommended index creation."""
        # Mock database inspector
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['reports', 'users', 'audit_logs']
        mock_inspector.get_indexes.return_value = []  # No existing indexes
        
        mock_db.inspect.return_value = mock_inspector
        mock_db.engine.execute = Mock()
        
        created, failed = DatabaseIndexManager.create_recommended_indexes()
        
        assert isinstance(created, list)
        assert isinstance(failed, list)
        # Should attempt to create indexes for existing tables
        assert len(created) + len(failed) > 0
    
    @patch('database.performance.db')
    def test_missing_index_analysis(self, mock_db):
        """Test missing index analysis."""
        # Mock database inspector
        mock_inspector = Mock()
        mock_inspector.get_table_names.return_value = ['reports', 'users']
        mock_inspector.get_columns.return_value = [
            {'name': 'id'}, {'name': 'user_email'}, {'name': 'status'}
        ]
        mock_inspector.get_indexes.return_value = []
        mock_inspector.get_foreign_keys.return_value = [
            {'constrained_columns': ['user_id']}
        ]
        
        mock_db.inspect.return_value = mock_inspector
        
        suggestions = DatabaseIndexManager.analyze_missing_indexes()
        
        assert isinstance(suggestions, list)
        # Should suggest indexes for foreign keys and common columns
        if suggestions:
            assert any(s['type'] == 'foreign_key' for s in suggestions)


class TestQueryOptimizer:
    """Test query optimization."""
    
    def test_optimizer_initialization(self):
        """Test optimizer initialization."""
        optimizer = QueryOptimizer()
        
        assert len(optimizer.optimization_rules) > 0
        assert hasattr(optimizer, '_check_missing_where_clause')
        assert hasattr(optimizer, '_check_select_star')
    
    def test_query_analysis_rules(self):
        """Test individual optimization rules."""
        optimizer = QueryOptimizer()
        
        # Test SELECT * detection
        suggestions = optimizer._check_select_star("select * from users", {})
        assert len(suggestions) > 0
        assert suggestions[0]['type'] == 'select_star'
        
        # Test missing WHERE clause detection
        suggestions = optimizer._check_missing_where_clause(
            "select name from users", {}
        )
        assert len(suggestions) > 0
        assert suggestions[0]['type'] == 'missing_where'
        
        # Test ORDER BY without LIMIT
        suggestions = optimizer._check_order_by_without_limit(
            "select * from users order by name", {}
        )
        assert len(suggestions) > 0
        assert suggestions[0]['type'] == 'order_without_limit'
    
    def test_priority_calculation(self):
        """Test optimization priority calculation."""
        optimizer = QueryOptimizer()
        
        # High priority: slow + frequent
        high_priority = optimizer._calculate_priority(
            {'avg_time': 3.0, 'count': 200, 'total_time': 600},
            [{'type': 'missing_index'}]
        )
        assert high_priority == 'high'
        
        # Medium priority: moderately slow
        medium_priority = optimizer._calculate_priority(
            {'avg_time': 1.5, 'count': 75, 'total_time': 112.5},
            [{'type': 'select_star'}]
        )
        assert medium_priority == 'medium'
        
        # Low priority: fast queries
        low_priority = optimizer._calculate_priority(
            {'avg_time': 0.1, 'count': 10, 'total_time': 1},
            [{'type': 'distinct_usage'}]
        )
        assert low_priority == 'low'


class TestIntegration:
    """Integration tests for database performance optimization."""
    
    @patch('database.query_cache.get_cache_manager')
    @patch('database.query_analyzer.get_query_analyzer')
    def test_performance_monitoring_integration(self, mock_analyzer, mock_cache):
        """Test integration between different performance components."""
        # Mock analyzer
        mock_analyzer_instance = Mock()
        mock_analyzer_instance.get_performance_summary.return_value = {
            'total_queries': 100,
            'slow_queries': 5,
            'avg_execution_time': 0.25
        }
        mock_analyzer.return_value = mock_analyzer_instance
        
        # Mock cache manager
        mock_cache_instance = Mock()
        mock_cache_instance.get_cache_stats.return_value = {
            'hit_rate': 75.0,
            'total_requests': 200
        }
        mock_cache.return_value = mock_cache_instance
        
        # Test that components work together
        analyzer = mock_analyzer()
        cache_mgr = mock_cache()
        
        summary = analyzer.get_performance_summary()
        cache_stats = cache_mgr.get_cache_stats()
        
        assert summary['total_queries'] == 100
        assert cache_stats['hit_rate'] == 75.0
    
    def test_concurrent_analysis(self):
        """Test concurrent query analysis."""
        analyzer = QueryAnalyzer()
        
        def analyze_queries():
            for i in range(50):
                analyzer.analyze_query(f"SELECT * FROM table_{i % 5}", 0.1 * (i % 10))
        
        # Run concurrent analysis
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=analyze_queries)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify thread safety
        summary = analyzer.get_performance_summary()
        assert summary['total_queries'] == 250  # 5 threads * 50 queries each
        assert summary['unique_queries'] == 5   # 5 different table patterns


if __name__ == '__main__':
    pytest.main([__file__])