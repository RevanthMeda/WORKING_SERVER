"""
Integration tests for database operations.
"""
import pytest
import json
from datetime import datetime, timedelta
from models import (
    db, User, Report, SATReport, SystemSettings, 
    Notification, ReportVersion, ReportComment, AuditLog
)
from tests.factories import (
    UserFactory, ReportFactory, SATReportFactory, 
    NotificationFactory, ApprovedReportFactory
)


class TestUserDatabaseOperations:
    """Test database operations for User model."""
    
    def test_user_crud_operations(self, db_session):
        """Test Create, Read, Update, Delete operations for User."""
        # Create
        user = User(
            email='crud@test.com',
            full_name='CRUD Test User',
            role='Engineer',
            status='Active'
        )
        user.set_password('password123')
        db_session.add(user)
        db_session.commit()
        
        user_id = user.id
        assert user_id is not None
        
        # Read
        retrieved_user = User.query.get(user_id)
        assert retrieved_user is not None
        assert retrieved_user.email == 'crud@test.com'
        assert retrieved_user.check_password('password123')
        
        # Update
        retrieved_user.full_name = 'Updated Name'
        retrieved_user.status = 'Disabled'
        db_session.commit()
        
        updated_user = User.query.get(user_id)
        assert updated_user.full_name == 'Updated Name'
        assert updated_user.status == 'Disabled'
        
        # Delete
        db_session.delete(updated_user)
        db_session.commit()
        
        deleted_user = User.query.get(user_id)
        assert deleted_user is None
    
    def test_user_query_operations(self, db_session):
        """Test various query operations on User model."""
        # Create test users
        users = [
            UserFactory(role='Admin', status='Active'),
            UserFactory(role='Engineer', status='Active'),
            UserFactory(role='Engineer', status='Pending'),
            UserFactory(role='PM', status='Disabled')
        ]
        db_session.commit()
        
        # Query by role
        engineers = User.query.filter_by(role='Engineer').all()
        assert len(engineers) == 2
        
        # Query by status
        active_users = User.query.filter_by(status='Active').all()
        assert len(active_users) == 2
        
        # Complex query
        active_engineers = User.query.filter_by(
            role='Engineer', 
            status='Active'
        ).all()
        assert len(active_engineers) == 1
        
        # Query with ordering
        ordered_users = User.query.order_by(User.full_name).all()
        assert len(ordered_users) >= 4
    
    def test_user_password_operations(self, db_session):
        """Test password-related database operations."""
        user = UserFactory()
        original_hash = user.password_hash
        
        # Change password
        user.set_password('new_password')
        db_session.commit()
        
        # Verify password changed
        assert user.password_hash != original_hash
        assert user.check_password('new_password')
        assert not user.check_password('password123')  # Old password
    
    def test_user_unique_constraints(self, db_session):
        """Test unique constraints on User model."""
        # Create first user
        user1 = UserFactory(email='unique@test.com')
        db_session.commit()
        
        # Try to create second user with same email
        user2 = User(
            email='unique@test.com',  # Duplicate email
            full_name='Another User',
            role='Engineer'
        )
        user2.set_password('password')
        db_session.add(user2)
        
        # Should raise integrity error
        with pytest.raises(Exception):  # SQLAlchemy IntegrityError
            db_session.commit()


class TestReportDatabaseOperations:
    """Test database operations for Report model."""
    
    def test_report_crud_operations(self, db_session, admin_user):
        """Test CRUD operations for Report model."""
        # Create
        report = Report(
            id='test-report-crud',
            type='SAT',
            status='DRAFT',
            document_title='CRUD Test Report',
            user_email=admin_user.email,
            version='R0'
        )
        db_session.add(report)
        db_session.commit()
        
        # Read
        retrieved_report = Report.query.get('test-report-crud')
        assert retrieved_report is not None
        assert retrieved_report.document_title == 'CRUD Test Report'
        
        # Update
        retrieved_report.status = 'PENDING'
        retrieved_report.locked = True
        db_session.commit()
        
        updated_report = Report.query.get('test-report-crud')
        assert updated_report.status == 'PENDING'
        assert updated_report.locked is True
        
        # Delete (cascade should handle related records)
        db_session.delete(updated_report)
        db_session.commit()
        
        deleted_report = Report.query.get('test-report-crud')
        assert deleted_report is None
    
    def test_report_sat_relationship(self, db_session, admin_user):
        """Test relationship between Report and SATReport."""
        # Create report
        report = ReportFactory(user_email=admin_user.email)
        
        # Create associated SAT report
        sat_report = SATReportFactory(report=report)
        db_session.commit()
        
        # Test forward relationship
        assert report.sat_report is not None
        assert report.sat_report.id == sat_report.id
        
        # Test backward relationship
        assert sat_report.parent_report is not None
        assert sat_report.parent_report.id == report.id
        
        # Test cascade delete
        report_id = report.id
        sat_id = sat_report.id
        
        db_session.delete(report)
        db_session.commit()
        
        # Both should be deleted
        assert Report.query.get(report_id) is None
        assert SATReport.query.get(sat_id) is None
    
    def test_report_approvals_json_operations(self, db_session, admin_user):
        """Test JSON operations for approval workflow."""
        report = ReportFactory(user_email=admin_user.email)
        
        # Set approval workflow
        approvals = [
            {
                'stage': 1,
                'approver_email': 'approver1@test.com',
                'status': 'pending',
                'timestamp': None
            },
            {
                'stage': 2,
                'approver_email': 'approver2@test.com',
                'status': 'pending',
                'timestamp': None
            }
        ]
        
        report.approvals_json = json.dumps(approvals)
        db_session.commit()
        
        # Retrieve and modify
        retrieved_report = Report.query.get(report.id)
        stored_approvals = json.loads(retrieved_report.approvals_json)
        
        # Update first approval
        stored_approvals[0]['status'] = 'approved'
        stored_approvals[0]['timestamp'] = datetime.utcnow().isoformat()
        
        retrieved_report.approvals_json = json.dumps(stored_approvals)
        db_session.commit()
        
        # Verify update
        final_report = Report.query.get(report.id)
        final_approvals = json.loads(final_report.approvals_json)
        assert final_approvals[0]['status'] == 'approved'
        assert final_approvals[1]['status'] == 'pending'
    
    def test_report_query_operations(self, db_session, admin_user):
        """Test various query operations on Report model."""
        # Create test reports
        reports = [
            ReportFactory(user_email=admin_user.email, status='DRAFT', type='SAT'),
            ReportFactory(user_email=admin_user.email, status='PENDING', type='SAT'),
            ApprovedReportFactory(user_email=admin_user.email, type='SAT'),
            ReportFactory(user_email='other@test.com', status='DRAFT', type='FDS')
        ]
        db_session.commit()
        
        # Query by user
        user_reports = Report.query.filter_by(user_email=admin_user.email).all()
        assert len(user_reports) == 3
        
        # Query by status
        draft_reports = Report.query.filter_by(status='DRAFT').all()
        assert len(draft_reports) == 2
        
        # Query by type
        sat_reports = Report.query.filter_by(type='SAT').all()
        assert len(sat_reports) == 3
        
        # Complex query with date range
        recent_reports = Report.query.filter(
            Report.created_at >= datetime.utcnow() - timedelta(days=1)
        ).all()
        assert len(recent_reports) == 4  # All created recently


class TestSATReportDatabaseOperations:
    """Test database operations for SATReport model."""
    
    def test_sat_report_data_json_operations(self, db_session, sample_report):
        """Test JSON data operations in SATReport."""
        # Create SAT report with complex data
        test_data = {
            'context': {
                'DOCUMENT_TITLE': 'Test SAT',
                'PROJECT_REFERENCE': 'PROJ-001'
            },
            'test_results': [
                {
                    'test_name': 'Startup Test',
                    'result': 'PASS',
                    'comments': 'System started successfully'
                },
                {
                    'test_name': 'Communication Test',
                    'result': 'FAIL',
                    'comments': 'Timeout on device 3'
                }
            ],
            'equipment_list': [
                {
                    'tag': 'PLC-001',
                    'description': 'Main Controller',
                    'status': 'Operational'
                }
            ]
        }
        
        sat_report = SATReport(
            report_id=sample_report.id,
            data_json=json.dumps(test_data),
            date='2024-01-15',
            purpose='System validation'
        )
        db_session.add(sat_report)
        db_session.commit()
        
        # Retrieve and verify JSON data
        retrieved_sat = SATReport.query.filter_by(report_id=sample_report.id).first()
        stored_data = json.loads(retrieved_sat.data_json)
        
        assert stored_data['context']['DOCUMENT_TITLE'] == 'Test SAT'
        assert len(stored_data['test_results']) == 2
        assert stored_data['test_results'][0]['result'] == 'PASS'
        assert stored_data['test_results'][1]['result'] == 'FAIL'
        assert len(stored_data['equipment_list']) == 1
    
    def test_sat_report_image_urls_operations(self, db_session, sample_report):
        """Test image URL JSON operations."""
        image_urls = [
            '/static/uploads/scada1.png',
            '/static/uploads/scada2.png',
            '/static/uploads/trends1.png'
        ]
        
        sat_report = SATReport(
            report_id=sample_report.id,
            data_json='{}',
            scada_image_urls=json.dumps(image_urls[:2]),
            trends_image_urls=json.dumps([image_urls[2]]),
            alarm_image_urls=json.dumps([])
        )
        db_session.add(sat_report)
        db_session.commit()
        
        # Retrieve and verify
        retrieved_sat = SATReport.query.filter_by(report_id=sample_report.id).first()
        
        scada_urls = json.loads(retrieved_sat.scada_image_urls)
        trends_urls = json.loads(retrieved_sat.trends_image_urls)
        alarm_urls = json.loads(retrieved_sat.alarm_image_urls)
        
        assert len(scada_urls) == 2
        assert len(trends_urls) == 1
        assert len(alarm_urls) == 0
        assert '/static/uploads/scada1.png' in scada_urls


class TestSystemSettingsDatabaseOperations:
    """Test database operations for SystemSettings model."""
    
    def test_system_settings_crud(self, db_session):
        """Test CRUD operations for SystemSettings."""
        # Test set_setting (create)
        SystemSettings.set_setting('test_key', 'test_value')
        
        setting = SystemSettings.query.filter_by(key='test_key').first()
        assert setting is not None
        assert setting.value == 'test_value'
        
        # Test get_setting
        value = SystemSettings.get_setting('test_key')
        assert value == 'test_value'
        
        # Test get_setting with default
        default_value = SystemSettings.get_setting('nonexistent_key', 'default')
        assert default_value == 'default'
        
        # Test set_setting (update)
        original_updated_at = setting.updated_at
        SystemSettings.set_setting('test_key', 'updated_value')
        
        updated_setting = SystemSettings.query.filter_by(key='test_key').first()
        assert updated_setting.value == 'updated_value'
        assert updated_setting.updated_at > original_updated_at
    
    def test_system_settings_multiple_keys(self, db_session):
        """Test operations with multiple system settings."""
        settings_data = {
            'company_name': 'Test Company',
            'max_file_size': '10MB',
            'email_notifications': 'true',
            'backup_frequency': 'daily'
        }
        
        # Create multiple settings
        for key, value in settings_data.items():
            SystemSettings.set_setting(key, value)
        
        # Verify all settings
        for key, expected_value in settings_data.items():
            actual_value = SystemSettings.get_setting(key)
            assert actual_value == expected_value
        
        # Verify count
        total_settings = SystemSettings.query.count()
        assert total_settings >= len(settings_data)


class TestNotificationDatabaseOperations:
    """Test database operations for Notification model."""
    
    def test_notification_crud_operations(self, db_session):
        """Test CRUD operations for Notification model."""
        # Create
        notification = Notification.create_notification(
            user_email='test@example.com',
            title='Test Notification',
            message='This is a test message',
            notification_type='approval_request',
            submission_id='test-123',
            action_url='/test/url'
        )
        
        notification_id = notification.id
        assert notification_id is not None
        
        # Read
        retrieved_notification = Notification.query.get(notification_id)
        assert retrieved_notification.title == 'Test Notification'
        assert retrieved_notification.read is False
        
        # Update
        retrieved_notification.read = True
        db_session.commit()
        
        updated_notification = Notification.query.get(notification_id)
        assert updated_notification.read is True
        
        # Delete
        db_session.delete(updated_notification)
        db_session.commit()
        
        deleted_notification = Notification.query.get(notification_id)
        assert deleted_notification is None
    
    def test_notification_query_operations(self, db_session):
        """Test query operations for notifications."""
        # Create test notifications
        notifications = [
            NotificationFactory(user_email='user1@test.com', read=False),
            NotificationFactory(user_email='user1@test.com', read=True),
            NotificationFactory(user_email='user2@test.com', read=False),
            NotificationFactory(user_email='user1@test.com', read=False, type='approval_request')
        ]
        db_session.commit()
        
        # Query unread notifications for user1
        unread_user1 = Notification.query.filter_by(
            user_email='user1@test.com',
            read=False
        ).all()
        assert len(unread_user1) == 2
        
        # Query by notification type
        approval_notifications = Notification.query.filter_by(
            type='approval_request'
        ).all()
        assert len(approval_notifications) >= 1
        
        # Query recent notifications
        recent_notifications = Notification.query.filter(
            Notification.created_at >= datetime.utcnow() - timedelta(hours=1)
        ).all()
        assert len(recent_notifications) == 4
    
    def test_notification_to_dict_method(self, db_session):
        """Test the to_dict method of Notification."""
        notification = NotificationFactory(
            title='Dict Test',
            message='Test message',
            type='status_update',
            action_url='/test/action'
        )
        db_session.commit()
        
        result_dict = notification.to_dict()
        
        assert result_dict['title'] == 'Dict Test'
        assert result_dict['message'] == 'Test message'
        assert result_dict['notification_type'] == 'status_update'
        assert result_dict['action_url'] == '/test/action'
        assert result_dict['read'] is False
        assert 'created_at' in result_dict


class TestDatabaseTransactions:
    """Test database transaction handling."""
    
    def test_transaction_rollback(self, db_session, admin_user):
        """Test transaction rollback on error."""
        initial_user_count = User.query.count()
        
        try:
            # Start a transaction
            new_user = User(
                email='transaction@test.com',
                full_name='Transaction Test',
                role='Engineer'
            )
            new_user.set_password('password')
            db_session.add(new_user)
            
            # This should cause an error (duplicate email)
            duplicate_user = User(
                email=admin_user.email,  # Duplicate email
                full_name='Duplicate User',
                role='Admin'
            )
            duplicate_user.set_password('password')
            db_session.add(duplicate_user)
            
            db_session.commit()
            
        except Exception:
            db_session.rollback()
        
        # Verify rollback - no new users should be added
        final_user_count = User.query.count()
        assert final_user_count == initial_user_count
    
    def test_bulk_operations(self, db_session):
        """Test bulk database operations."""
        # Bulk insert
        users_data = [
            {'email': f'bulk{i}@test.com', 'full_name': f'Bulk User {i}', 'role': 'Engineer'}
            for i in range(5)
        ]
        
        users = []
        for data in users_data:
            user = User(**data)
            user.set_password('password')
            users.append(user)
        
        db_session.add_all(users)
        db_session.commit()
        
        # Verify bulk insert
        bulk_users = User.query.filter(User.email.like('bulk%@test.com')).all()
        assert len(bulk_users) == 5
        
        # Bulk update
        User.query.filter(User.email.like('bulk%@test.com')).update(
            {'status': 'Pending'}
        )
        db_session.commit()
        
        # Verify bulk update
        pending_users = User.query.filter_by(status='Pending').all()
        assert len(pending_users) >= 5
        
        # Bulk delete
        User.query.filter(User.email.like('bulk%@test.com')).delete()
        db_session.commit()
        
        # Verify bulk delete
        remaining_bulk_users = User.query.filter(User.email.like('bulk%@test.com')).all()
        assert len(remaining_bulk_users) == 0