"""
Database performance tests for SAT Report Generator.
"""
import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from models import db, User, Report, SATReport, Notification
from tests.factories import UserFactory, ReportFactory, SATReportFactory, NotificationFactory


@pytest.mark.performance
class TestDatabasePerformance:
    """Test database performance under various loads."""
    
    def test_user_query_performance(self, db_session):
        """Test user query performance with large dataset."""
        # Create large number of users
        users = []
        batch_size = 100
        total_users = 1000
        
        start_time = time.time()
        
        for i in range(0, total_users, batch_size):
            batch_users = []
            for j in range(batch_size):
                user = User(
                    email=f'perf_user_{i+j}@test.com',
                    full_name=f'Performance User {i+j}',
                    role='Engineer',
                    status='Active'
                )
                user.set_password('password123')
                batch_users.append(user)
            
            db_session.add_all(batch_users)
            users.extend(batch_users)
        
        db_session.commit()
        creation_time = time.time() - start_time
        
        print(f"Created {total_users} users in {creation_time:.2f} seconds")
        
        # Test various query patterns
        query_tests = [
            ("Simple filter by role", lambda: User.query.filter_by(role='Engineer').all()),
            ("Filter by status", lambda: User.query.filter_by(status='Active').all()),
            ("Complex filter", lambda: User.query.filter(
                User.role == 'Engineer', 
                User.status == 'Active'
            ).all()),
            ("Count query", lambda: User.query.filter_by(role='Engineer').count()),
            ("Paginated query", lambda: User.query.filter_by(role='Engineer').limit(50).all()),
            ("Ordered query", lambda: User.query.order_by(User.full_name).limit(100).all())
        ]
        
        for test_name, query_func in query_tests:
            start_time = time.time()
            result = query_func()
            query_time = time.time() - start_time
            
            print(f"{test_name}: {query_time:.3f}s ({len(result) if hasattr(result, '__len__') else result} results)")
            
            # Performance assertions
            assert query_time < 2.0, f"{test_name} took too long: {query_time:.3f}s"
    
    def test_report_creation_performance(self, db_session, admin_user):
        """Test report creation performance."""
        num_reports = 500
        
        start_time = time.time()
        
        reports = []
        for i in range(num_reports):
            report = Report(
                id=f'perf-report-{i:04d}',
                type='SAT',
                status='DRAFT',
                document_title=f'Performance Test Report {i}',
                document_reference=f'PERF-{i:04d}',
                project_reference=f'PROJ-PERF-{i:04d}',
                client_name=f'Performance Client {i % 10}',
                user_email=admin_user.email,
                version='R0'
            )
            reports.append(report)
        
        db_session.add_all(reports)
        db_session.commit()
        
        creation_time = time.time() - start_time
        
        print(f"Created {num_reports} reports in {creation_time:.2f} seconds")
        print(f"Average: {(creation_time / num_reports) * 1000:.2f}ms per report")
        
        # Performance assertions
        assert creation_time < 30.0, f"Report creation took too long: {creation_time:.2f}s"
        assert (creation_time / num_reports) < 0.1, "Individual report creation too slow"
    
    def test_concurrent_database_operations(self, db_session, admin_user):
        """Test concurrent database operations."""
        num_threads = 10
        operations_per_thread = 50
        
        def create_reports_thread(thread_id):
            """Create reports in a separate thread."""
            thread_reports = []
            for i in range(operations_per_thread):
                report = Report(
                    id=f'concurrent-{thread_id}-{i:03d}',
                    type='SAT',
                    status='DRAFT',
                    document_title=f'Concurrent Test Report {thread_id}-{i}',
                    user_email=admin_user.email,
                    version='R0'
                )
                thread_reports.append(report)
            
            # Use separate session for thread safety
            from models import db
            db.session.add_all(thread_reports)
            db.session.commit()
            
            return len(thread_reports)
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(create_reports_thread, thread_id) 
                for thread_id in range(num_threads)
            ]
            
            total_created = 0
            for future in as_completed(futures):
                total_created += future.result()
        
        concurrent_time = time.time() - start_time
        
        print(f"Created {total_created} reports concurrently in {concurrent_time:.2f} seconds")
        print(f"Throughput: {total_created / concurrent_time:.2f} reports/second")
        
        # Verify all reports were created
        created_reports = Report.query.filter(Report.id.like('concurrent-%')).count()
        assert created_reports == total_created
        
        # Performance assertions
        assert concurrent_time < 60.0, f"Concurrent operations took too long: {concurrent_time:.2f}s"
    
    def test_complex_query_performance(self, db_session, admin_user):
        """Test performance of complex queries with joins."""
        # Create test data with relationships
        num_reports = 200
        
        reports = []
        sat_reports = []
        
        for i in range(num_reports):
            report = ReportFactory(
                user_email=admin_user.email,
                id=f'complex-query-{i:04d}'
            )
            reports.append(report)
            
            sat_report = SATReport(
                report_id=report.id,
                data_json='{"test": "data"}',
                date=f'2024-01-{(i % 28) + 1:02d}',
                purpose=f'Performance test purpose {i}'
            )
            sat_reports.append(sat_report)
        
        db_session.add_all(reports + sat_reports)
        db_session.commit()
        
        # Test complex queries
        complex_queries = [
            (
                "Join with SAT reports",
                lambda: db_session.query(Report).join(SATReport).filter(
                    Report.status == 'DRAFT'
                ).all()
            ),
            (
                "Subquery with count",
                lambda: db_session.query(Report).filter(
                    Report.id.in_(
                        db_session.query(SATReport.report_id).filter(
                            SATReport.date.like('2024-01-%')
                        )
                    )
                ).all()
            ),
            (
                "Aggregation query",
                lambda: db_session.query(
                    Report.status, 
                    db.func.count(Report.id)
                ).group_by(Report.status).all()
            ),
            (
                "Date range query",
                lambda: db_session.query(Report).filter(
                    Report.created_at >= '2024-01-01'
                ).order_by(Report.created_at.desc()).limit(50).all()
            )
        ]
        
        for query_name, query_func in complex_queries:
            start_time = time.time()
            result = query_func()
            query_time = time.time() - start_time
            
            print(f"{query_name}: {query_time:.3f}s ({len(result)} results)")
            
            # Performance assertions
            assert query_time < 5.0, f"{query_name} took too long: {query_time:.3f}s"
    
    def test_notification_performance(self, db_session):
        """Test notification system performance."""
        num_users = 100
        notifications_per_user = 50
        
        # Create users
        users = []
        for i in range(num_users):
            user = UserFactory(email=f'notify_user_{i}@test.com')
            users.append(user)
        
        db_session.commit()
        
        # Create notifications
        start_time = time.time()
        
        notifications = []
        for user in users:
            for j in range(notifications_per_user):
                notification = Notification(
                    user_email=user.email,
                    title=f'Performance Test Notification {j}',
                    message=f'Test message {j} for user {user.email}',
                    type='approval_request',
                    related_submission_id=f'test-{j}'
                )
                notifications.append(notification)
        
        db_session.add_all(notifications)
        db_session.commit()
        
        creation_time = time.time() - start_time
        total_notifications = len(notifications)
        
        print(f"Created {total_notifications} notifications in {creation_time:.2f} seconds")
        
        # Test notification queries
        query_start = time.time()
        
        # Get unread notifications for random user
        test_user = users[50]
        unread_notifications = Notification.query.filter_by(
            user_email=test_user.email,
            read=False
        ).all()
        
        query_time = time.time() - query_start
        
        print(f"Queried {len(unread_notifications)} notifications in {query_time:.3f}s")
        
        # Performance assertions
        assert creation_time < 30.0, f"Notification creation took too long: {creation_time:.2f}s"
        assert query_time < 1.0, f"Notification query took too long: {query_time:.3f}s"
    
    def test_database_connection_pool_performance(self, app, db_session):
        """Test database connection pool performance."""
        num_concurrent_requests = 20
        
        def database_operation(operation_id):
            """Perform database operation."""
            with app.app_context():
                # Simulate typical database operations
                user_count = User.query.count()
                report_count = Report.query.count()
                
                # Create a small record
                test_user = User(
                    email=f'pool_test_{operation_id}@test.com',
                    full_name=f'Pool Test User {operation_id}',
                    role='Engineer'
                )
                test_user.set_password('password')
                
                db.session.add(test_user)
                db.session.commit()
                
                return user_count, report_count
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
            futures = [
                executor.submit(database_operation, i) 
                for i in range(num_concurrent_requests)
            ]
            
            results = []
            for future in as_completed(futures):
                results.append(future.result())
        
        pool_test_time = time.time() - start_time
        
        print(f"Completed {num_concurrent_requests} concurrent DB operations in {pool_test_time:.2f}s")
        print(f"Average time per operation: {(pool_test_time / num_concurrent_requests) * 1000:.2f}ms")
        
        # Verify all operations completed
        assert len(results) == num_concurrent_requests
        
        # Performance assertions
        assert pool_test_time < 30.0, f"Connection pool test took too long: {pool_test_time:.2f}s"
    
    def test_bulk_operations_performance(self, db_session):
        """Test bulk database operations performance."""
        num_records = 1000
        
        # Test bulk insert
        start_time = time.time()
        
        users_data = []
        for i in range(num_records):
            user_data = {
                'email': f'bulk_user_{i}@test.com',
                'full_name': f'Bulk User {i}',
                'role': 'Engineer',
                'status': 'Active'
            }
            users_data.append(user_data)
        
        # Use bulk insert
        db_session.execute(
            User.__table__.insert(),
            users_data
        )
        db_session.commit()
        
        bulk_insert_time = time.time() - start_time
        
        print(f"Bulk inserted {num_records} users in {bulk_insert_time:.2f} seconds")
        
        # Test bulk update
        start_time = time.time()
        
        db_session.query(User).filter(
            User.email.like('bulk_user_%')
        ).update({'status': 'Pending'})
        db_session.commit()
        
        bulk_update_time = time.time() - start_time
        
        print(f"Bulk updated {num_records} users in {bulk_update_time:.2f} seconds")
        
        # Test bulk delete
        start_time = time.time()
        
        deleted_count = db_session.query(User).filter(
            User.email.like('bulk_user_%')
        ).delete()
        db_session.commit()
        
        bulk_delete_time = time.time() - start_time
        
        print(f"Bulk deleted {deleted_count} users in {bulk_delete_time:.2f} seconds")
        
        # Performance assertions
        assert bulk_insert_time < 10.0, f"Bulk insert took too long: {bulk_insert_time:.2f}s"
        assert bulk_update_time < 5.0, f"Bulk update took too long: {bulk_update_time:.2f}s"
        assert bulk_delete_time < 5.0, f"Bulk delete took too long: {bulk_delete_time:.2f}s"


@pytest.mark.performance
class TestMemoryPerformance:
    """Test memory usage and performance."""
    
    def test_memory_usage_large_dataset(self, db_session, admin_user):
        """Test memory usage with large datasets."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create large dataset
        num_reports = 1000
        reports = []
        
        for i in range(num_reports):
            report = ReportFactory(
                user_email=admin_user.email,
                id=f'memory-test-{i:04d}'
            )
            reports.append(report)
        
        db_session.add_all(reports)
        db_session.commit()
        
        # Query large dataset
        all_reports = Report.query.filter(Report.id.like('memory-test-%')).all()
        
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory
        
        print(f"Initial memory: {initial_memory:.2f} MB")
        print(f"Peak memory: {peak_memory:.2f} MB")
        print(f"Memory increase: {memory_increase:.2f} MB")
        print(f"Memory per report: {memory_increase / num_reports * 1024:.2f} KB")
        
        # Memory usage should be reasonable
        assert memory_increase < 500, f"Memory usage too high: {memory_increase:.2f} MB"
        
        # Clean up
        del all_reports
        del reports
    
    def test_query_result_streaming(self, db_session, admin_user):
        """Test streaming large query results to manage memory."""
        # Create test data
        num_reports = 2000
        
        reports = []
        for i in range(num_reports):
            report = Report(
                id=f'stream-test-{i:04d}',
                type='SAT',
                status='DRAFT',
                document_title=f'Stream Test Report {i}',
                user_email=admin_user.email,
                version='R0'
            )
            reports.append(report)
        
        db_session.add_all(reports)
        db_session.commit()
        
        # Test streaming query results
        start_time = time.time()
        
        processed_count = 0
        batch_size = 100
        
        # Process in batches to manage memory
        for offset in range(0, num_reports, batch_size):
            batch_reports = Report.query.filter(
                Report.id.like('stream-test-%')
            ).offset(offset).limit(batch_size).all()
            
            # Simulate processing
            for report in batch_reports:
                processed_count += 1
            
            # Clear batch from memory
            del batch_reports
        
        streaming_time = time.time() - start_time
        
        print(f"Processed {processed_count} reports in batches in {streaming_time:.2f} seconds")
        
        assert processed_count == num_reports
        assert streaming_time < 30.0, f"Streaming processing took too long: {streaming_time:.2f}s"