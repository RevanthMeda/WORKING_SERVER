"""
API performance tests for SAT Report Generator.
"""
import pytest
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch


@pytest.mark.performance
class TestAPIResponseTimes:
    """Test API response time performance."""
    
    def test_health_endpoint_performance(self, client):
        """Test health endpoint response time."""
        response_times = []
        num_requests = 100
        
        for _ in range(num_requests):
            start_time = time.time()
            response = client.get('/health')
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            response_times.append(response_time)
            
            assert response.status_code == 200
        
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)
        
        print(f"Health endpoint - Avg: {avg_response_time:.2f}ms, "
              f"Max: {max_response_time:.2f}ms, Min: {min_response_time:.2f}ms")
        
        # Performance assertions
        assert avg_response_time < 100, f"Average response time too slow: {avg_response_time:.2f}ms"
        assert max_response_time < 500, f"Max response time too slow: {max_response_time:.2f}ms"
    
    def test_authentication_endpoint_performance(self, client, admin_user):
        """Test authentication endpoint performance."""
        response_times = []
        num_requests = 50
        
        for _ in range(num_requests):
            start_time = time.time()
            response = client.get('/api/check-auth')
            response_time = (time.time() - start_time) * 1000
            response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times)
        
        print(f"Auth check endpoint - Avg: {avg_response_time:.2f}ms")
        
        # Authentication checks should be fast
        assert avg_response_time < 200, f"Auth check too slow: {avg_response_time:.2f}ms"
    
    def test_dashboard_endpoint_performance(self, client, admin_user):
        """Test dashboard endpoint performance."""
        # Login first
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response_times = []
        num_requests = 20
        
        for _ in range(num_requests):
            start_time = time.time()
            response = client.get('/dashboard')
            response_time = (time.time() - start_time) * 1000
            response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times)
        
        print(f"Dashboard endpoint - Avg: {avg_response_time:.2f}ms")
        
        # Dashboard should load reasonably fast
        assert avg_response_time < 1000, f"Dashboard too slow: {avg_response_time:.2f}ms"
    
    def test_reports_list_performance(self, client, admin_user, db_session):
        """Test reports list endpoint performance with data."""
        # Create test reports
        from tests.factories import ReportFactory
        
        reports = []
        for i in range(100):
            report = ReportFactory(user_email=admin_user.email)
            reports.append(report)
        
        db_session.commit()
        
        # Login
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        # Test performance
        response_times = []
        num_requests = 10
        
        for _ in range(num_requests):
            start_time = time.time()
            response = client.get('/reports')
            response_time = (time.time() - start_time) * 1000
            response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times)
        
        print(f"Reports list (100 reports) - Avg: {avg_response_time:.2f}ms")
        
        # Reports list should handle moderate datasets efficiently
        assert avg_response_time < 2000, f"Reports list too slow: {avg_response_time:.2f}ms"


@pytest.mark.performance
class TestConcurrentAPIAccess:
    """Test API performance under concurrent access."""
    
    def test_concurrent_health_checks(self, client):
        """Test concurrent access to health endpoint."""
        num_threads = 20
        requests_per_thread = 10
        
        def make_requests(thread_id):
            """Make multiple requests in a thread."""
            response_times = []
            for _ in range(requests_per_thread):
                start_time = time.time()
                response = client.get('/health')
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)
                
                assert response.status_code == 200
            
            return response_times
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(make_requests, i) 
                for i in range(num_threads)
            ]
            
            all_response_times = []
            for future in as_completed(futures):
                all_response_times.extend(future.result())
        
        total_time = time.time() - start_time
        total_requests = num_threads * requests_per_thread
        
        avg_response_time = sum(all_response_times) / len(all_response_times)
        throughput = total_requests / total_time
        
        print(f"Concurrent health checks:")
        print(f"  Total requests: {total_requests}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {throughput:.2f} req/s")
        print(f"  Avg response time: {avg_response_time:.2f}ms")
        
        # Performance assertions
        assert throughput > 50, f"Throughput too low: {throughput:.2f} req/s"
        assert avg_response_time < 500, f"Avg response time too high: {avg_response_time:.2f}ms"
    
    def test_concurrent_authenticated_requests(self, client, admin_user):
        """Test concurrent authenticated requests."""
        num_threads = 10
        requests_per_thread = 5
        
        def make_authenticated_requests(thread_id):
            """Make authenticated requests in a thread."""
            # Each thread needs its own session
            with client.session_transaction() as sess:
                sess['user_id'] = admin_user.id
                sess['_fresh'] = True
            
            response_times = []
            for _ in range(requests_per_thread):
                start_time = time.time()
                response = client.get('/api/check-auth')
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)
            
            return response_times
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(make_authenticated_requests, i) 
                for i in range(num_threads)
            ]
            
            all_response_times = []
            for future in as_completed(futures):
                all_response_times.extend(future.result())
        
        total_time = time.time() - start_time
        total_requests = num_threads * requests_per_thread
        
        avg_response_time = sum(all_response_times) / len(all_response_times)
        throughput = total_requests / total_time
        
        print(f"Concurrent authenticated requests:")
        print(f"  Throughput: {throughput:.2f} req/s")
        print(f"  Avg response time: {avg_response_time:.2f}ms")
        
        # Authenticated requests should still be reasonably fast
        assert avg_response_time < 1000, f"Authenticated requests too slow: {avg_response_time:.2f}ms"
    
    def test_mixed_endpoint_load(self, client, admin_user):
        """Test mixed load across different endpoints."""
        endpoints = [
            '/health',
            '/api/check-auth',
            '/dashboard',
            '/reports'
        ]
        
        num_threads = 15
        requests_per_thread = 8
        
        def make_mixed_requests(thread_id):
            """Make requests to various endpoints."""
            # Setup session for authenticated endpoints
            with client.session_transaction() as sess:
                sess['user_id'] = admin_user.id
                sess['_fresh'] = True
            
            response_times = {}
            
            for endpoint in endpoints:
                start_time = time.time()
                response = client.get(endpoint)
                response_time = (time.time() - start_time) * 1000
                
                if endpoint not in response_times:
                    response_times[endpoint] = []
                response_times[endpoint].append(response_time)
            
            return response_times
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(make_mixed_requests, i) 
                for i in range(num_threads)
            ]
            
            endpoint_times = {endpoint: [] for endpoint in endpoints}
            
            for future in as_completed(futures):
                thread_times = future.result()
                for endpoint, times in thread_times.items():
                    endpoint_times[endpoint].extend(times)
        
        total_time = time.time() - start_time
        
        print(f"Mixed endpoint load test ({total_time:.2f}s total):")
        
        for endpoint, times in endpoint_times.items():
            if times:
                avg_time = sum(times) / len(times)
                max_time = max(times)
                print(f"  {endpoint}: Avg {avg_time:.2f}ms, Max {max_time:.2f}ms")
                
                # Each endpoint should meet performance criteria
                assert avg_time < 2000, f"{endpoint} too slow: {avg_time:.2f}ms"


@pytest.mark.performance
class TestAPIScalability:
    """Test API scalability characteristics."""
    
    def test_response_time_under_load(self, client):
        """Test how response times change under increasing load."""
        load_levels = [1, 5, 10, 20, 50]
        results = {}
        
        for num_concurrent in load_levels:
            def make_request():
                start_time = time.time()
                response = client.get('/health')
                return (time.time() - start_time) * 1000
            
            # Make concurrent requests
            with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
                futures = [executor.submit(make_request) for _ in range(num_concurrent)]
                response_times = [future.result() for future in as_completed(futures)]
            
            avg_time = sum(response_times) / len(response_times)
            max_time = max(response_times)
            
            results[num_concurrent] = {
                'avg': avg_time,
                'max': max_time
            }
            
            print(f"Load level {num_concurrent}: Avg {avg_time:.2f}ms, Max {max_time:.2f}ms")
        
        # Response times should not degrade dramatically with load
        baseline_avg = results[1]['avg']
        high_load_avg = results[50]['avg']
        
        degradation_factor = high_load_avg / baseline_avg
        
        print(f"Performance degradation factor: {degradation_factor:.2f}x")
        
        # Should not degrade more than 5x under 50x load
        assert degradation_factor < 5.0, f"Performance degrades too much: {degradation_factor:.2f}x"
    
    def test_memory_usage_under_load(self, client):
        """Test memory usage under sustained load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Sustained load test
        num_requests = 1000
        
        for i in range(num_requests):
            response = client.get('/health')
            assert response.status_code == 200
            
            # Check memory every 100 requests
            if i % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_increase = current_memory - initial_memory
                
                print(f"Request {i}: Memory usage {current_memory:.2f} MB "
                      f"(+{memory_increase:.2f} MB)")
                
                # Memory should not grow excessively
                assert memory_increase < 100, f"Memory leak detected: +{memory_increase:.2f} MB"
        
        final_memory = process.memory_info().rss / 1024 / 1024
        total_increase = final_memory - initial_memory
        
        print(f"Total memory increase after {num_requests} requests: {total_increase:.2f} MB")
        
        # Final memory increase should be reasonable
        assert total_increase < 50, f"Excessive memory usage: +{total_increase:.2f} MB"
    
    def test_error_handling_performance(self, client):
        """Test performance of error handling."""
        error_endpoints = [
            '/nonexistent-endpoint',  # 404
            '/admin/restricted',      # 403 (if not admin)
        ]
        
        for endpoint in error_endpoints:
            response_times = []
            num_requests = 50
            
            for _ in range(num_requests):
                start_time = time.time()
                response = client.get(endpoint)
                response_time = (time.time() - start_time) * 1000
                response_times.append(response_time)
                
                # Should return error status quickly
                assert response.status_code in [403, 404, 500]
            
            avg_response_time = sum(response_times) / len(response_times)
            
            print(f"Error endpoint {endpoint}: Avg {avg_response_time:.2f}ms")
            
            # Error responses should be fast
            assert avg_response_time < 200, f"Error handling too slow: {avg_response_time:.2f}ms"


@pytest.mark.performance
class TestAPIResourceUsage:
    """Test API resource usage patterns."""
    
    def test_cpu_usage_under_load(self, client):
        """Test CPU usage during API load."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Baseline CPU usage
        baseline_cpu = process.cpu_percent(interval=1)
        
        # Generate load
        num_requests = 200
        start_time = time.time()
        
        for _ in range(num_requests):
            response = client.get('/health')
            assert response.status_code == 200
        
        load_time = time.time() - start_time
        
        # Measure CPU usage during load
        load_cpu = process.cpu_percent(interval=1)
        
        throughput = num_requests / load_time
        
        print(f"CPU usage: Baseline {baseline_cpu:.1f}%, Under load {load_cpu:.1f}%")
        print(f"Throughput: {throughput:.2f} req/s")
        
        # CPU usage should be reasonable
        assert load_cpu < 80, f"CPU usage too high: {load_cpu:.1f}%"
        assert throughput > 20, f"Throughput too low: {throughput:.2f} req/s"
    
    def test_file_descriptor_usage(self, client):
        """Test file descriptor usage during API operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        try:
            initial_fds = process.num_fds()
        except AttributeError:
            # num_fds() not available on Windows
            pytest.skip("File descriptor monitoring not available on this platform")
        
        # Make many requests
        num_requests = 500
        
        for _ in range(num_requests):
            response = client.get('/health')
            assert response.status_code == 200
        
        final_fds = process.num_fds()
        fd_increase = final_fds - initial_fds
        
        print(f"File descriptors: Initial {initial_fds}, Final {final_fds}, "
              f"Increase {fd_increase}")
        
        # Should not leak file descriptors
        assert fd_increase < 10, f"File descriptor leak detected: +{fd_increase}"
    
    @patch('utils.send_email')
    def test_external_service_timeout_handling(self, mock_send_email, client, admin_user):
        """Test handling of external service timeouts."""
        # Mock email service to simulate timeout
        def slow_email(*args, **kwargs):
            time.sleep(2)  # Simulate slow external service
            return True
        
        mock_send_email.side_effect = slow_email
        
        # Login
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        # Test endpoint that might trigger email
        start_time = time.time()
        response = client.post('/reports/submit', data={
            'document_title': 'Timeout Test Report',
            'project_reference': 'TIMEOUT-001'
        })
        response_time = (time.time() - start_time) * 1000
        
        print(f"Response time with slow external service: {response_time:.2f}ms")
        
        # Should handle external service delays gracefully
        # Response time will be affected, but should not hang indefinitely
        assert response_time < 10000, f"Request hung too long: {response_time:.2f}ms"