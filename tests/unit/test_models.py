"""
Unit tests for database models.
"""
import pytest
import json
from datetime import datetime
from models import User, Report, SATReport, SystemSettings, Notification


class TestUser:
    """Test cases for User model."""
    
    def test_user_creation(self, db_session):
        """Test creating a new user."""
        user = User(
            email='test@example.com',
            full_name='Test User',
            role='Engineer',
            status='Active'
        )
        user.set_password('password123')
        
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.email == 'test@example.com'
        assert user.full_name == 'Test User'
        assert user.role == 'Engineer'
        assert user.status == 'Active'
        assert user.is_active is True
    
    def test_password_hashing(self, db_session):
        """Test password hashing and verification."""
        user = User(
            email='test@example.com',
            full_name='Test User'
        )
        password = 'secure_password123'
        user.set_password(password)
        
        # Password should be hashed
        assert user.password_hash != password
        assert user.password_hash is not None
        
        # Should verify correct password
        assert user.check_password(password) is True
        
        # Should reject incorrect password
        assert user.check_password('wrong_password') is False
    
    def test_user_is_active_property(self, db_session):
        """Test the is_active property."""
        # Active user
        active_user = User(
            email='active@example.com',
            full_name='Active User',
            status='Active'
        )
        assert active_user.is_active is True
        
        # Pending user
        pending_user = User(
            email='pending@example.com',
            full_name='Pending User',
            status='Pending'
        )
        assert pending_user.is_active is False
        
        # Disabled user
        disabled_user = User(
            email='disabled@example.com',
            full_name='Disabled User',
            status='Disabled'
        )
        assert disabled_user.is_active is False
    
    def test_user_repr(self, db_session):
        """Test user string representation."""
        user = User(email='test@example.com', full_name='Test User')
        assert repr(user) == '<User test@example.com>'


class TestReport:
    """Test cases for Report model."""
    
    def test_report_creation(self, db_session, admin_user):
        """Test creating a new report."""
        report = Report(
            id='test-123',
            type='SAT',
            status='DRAFT',
            document_title='Test Report',
            document_reference='TEST-001',
            project_reference='PROJ-001',
            client_name='Test Client',
            revision='R0',
            prepared_by='Test Engineer',
            user_email=admin_user.email,
            version='R0'
        )
        
        db_session.add(report)
        db_session.commit()
        
        assert report.id == 'test-123'
        assert report.type == 'SAT'
        assert report.status == 'DRAFT'
        assert report.document_title == 'Test Report'
        assert report.locked is False
        assert report.created_at is not None
        assert report.updated_at is not None
    
    def test_report_approvals_json(self, db_session, admin_user):
        """Test storing and retrieving approvals as JSON."""
        report = Report(
            id='test-456',
            type='SAT',
            user_email=admin_user.email
        )
        
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
        db_session.add(report)
        db_session.commit()
        
        # Retrieve and verify
        retrieved_report = Report.query.get('test-456')
        retrieved_approvals = json.loads(retrieved_report.approvals_json)
        
        assert len(retrieved_approvals) == 2
        assert retrieved_approvals[0]['stage'] == 1
        assert retrieved_approvals[1]['approver_email'] == 'approver2@test.com'
    
    def test_report_repr(self, db_session, admin_user):
        """Test report string representation."""
        report = Report(
            id='test-789',
            type='SAT',
            document_title='Test Report',
            user_email=admin_user.email
        )
        expected = '<Report test-789: SAT - Test Report>'
        assert repr(report) == expected


class TestSATReport:
    """Test cases for SATReport model."""
    
    def test_sat_report_creation(self, db_session, sample_report):
        """Test creating a SAT report."""
        sat_data = {
            'test_results': [
                {'name': 'Test 1', 'result': 'PASS'},
                {'name': 'Test 2', 'result': 'FAIL'}
            ]
        }
        
        sat_report = SATReport(
            report_id=sample_report.id,
            data_json=json.dumps(sat_data),
            date='2024-01-15',
            purpose='System acceptance testing',
            scope='Full system validation'
        )
        
        db_session.add(sat_report)
        db_session.commit()
        
        assert sat_report.id is not None
        assert sat_report.report_id == sample_report.id
        assert sat_report.date == '2024-01-15'
        assert sat_report.purpose == 'System acceptance testing'
        
        # Verify JSON data
        retrieved_data = json.loads(sat_report.data_json)
        assert len(retrieved_data['test_results']) == 2
        assert retrieved_data['test_results'][0]['result'] == 'PASS'
    
    def test_sat_report_image_urls(self, db_session, sample_report):
        """Test storing image URLs as JSON."""
        image_urls = [
            '/static/uploads/scada1.png',
            '/static/uploads/scada2.png'
        ]
        
        sat_report = SATReport(
            report_id=sample_report.id,
            data_json='{}',
            scada_image_urls=json.dumps(image_urls)
        )
        
        db_session.add(sat_report)
        db_session.commit()
        
        # Retrieve and verify
        retrieved_urls = json.loads(sat_report.scada_image_urls)
        assert len(retrieved_urls) == 2
        assert '/static/uploads/scada1.png' in retrieved_urls
    
    def test_sat_report_relationship(self, db_session, sample_report):
        """Test relationship between Report and SATReport."""
        # The sample_report fixture already creates a SATReport
        assert sample_report.sat_report is not None
        assert sample_report.sat_report.report_id == sample_report.id
        assert sample_report.sat_report.parent_report == sample_report


class TestSystemSettings:
    """Test cases for SystemSettings model."""
    
    def test_get_setting_existing(self, db_session):
        """Test getting an existing setting."""
        setting = SystemSettings(key='test_key', value='test_value')
        db_session.add(setting)
        db_session.commit()
        
        result = SystemSettings.get_setting('test_key')
        assert result == 'test_value'
    
    def test_get_setting_nonexistent(self, db_session):
        """Test getting a non-existent setting with default."""
        result = SystemSettings.get_setting('nonexistent_key', 'default_value')
        assert result == 'default_value'
    
    def test_set_setting_new(self, db_session):
        """Test setting a new setting."""
        SystemSettings.set_setting('new_key', 'new_value')
        
        setting = SystemSettings.query.filter_by(key='new_key').first()
        assert setting is not None
        assert setting.value == 'new_value'
        assert setting.updated_at is not None
    
    def test_set_setting_update(self, db_session):
        """Test updating an existing setting."""
        # Create initial setting
        setting = SystemSettings(key='update_key', value='old_value')
        db_session.add(setting)
        db_session.commit()
        
        original_updated_at = setting.updated_at
        
        # Update the setting
        SystemSettings.set_setting('update_key', 'new_value')
        
        # Verify update
        updated_setting = SystemSettings.query.filter_by(key='update_key').first()
        assert updated_setting.value == 'new_value'
        assert updated_setting.updated_at > original_updated_at


class TestNotification:
    """Test cases for Notification model."""
    
    def test_notification_creation(self, db_session):
        """Test creating a notification."""
        notification = Notification(
            user_email='user@test.com',
            title='Test Notification',
            message='This is a test notification',
            type='approval_request',
            related_submission_id='test-123'
        )
        
        db_session.add(notification)
        db_session.commit()
        
        assert notification.id is not None
        assert notification.user_email == 'user@test.com'
        assert notification.title == 'Test Notification'
        assert notification.read is False
        assert notification.created_at is not None
    
    def test_notification_to_dict(self, db_session):
        """Test converting notification to dictionary."""
        notification = Notification(
            user_email='user@test.com',
            title='Test Notification',
            message='Test message',
            type='status_update',
            related_submission_id='test-456',
            action_url='/test/url'
        )
        
        db_session.add(notification)
        db_session.commit()
        
        result = notification.to_dict()
        
        assert result['title'] == 'Test Notification'
        assert result['message'] == 'Test message'
        assert result['notification_type'] == 'status_update'
        assert result['submission_id'] == 'test-456'
        assert result['action_url'] == '/test/url'
        assert result['read'] is False
        assert 'created_at' in result
    
    def test_create_notification_static_method(self, db_session):
        """Test the static create_notification method."""
        notification = Notification.create_notification(
            user_email='test@example.com',
            title='Static Test',
            message='Created via static method',
            notification_type='completion',
            submission_id='static-123',
            action_url='/static/url'
        )
        
        assert notification.id is not None
        assert notification.user_email == 'test@example.com'
        assert notification.title == 'Static Test'
        assert notification.type == 'completion'
        
        # Verify it was saved to database
        saved_notification = Notification.query.get(notification.id)
        assert saved_notification is not None
        assert saved_notification.message == 'Created via static method'