"""
Unit tests for utility functions.
"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from utils import (
    get_unread_count, 
    create_approval_notification,
    create_status_update_notification,
    create_completion_notification,
    load_submissions,
    save_submissions,
    send_email,
    process_table_rows,
    handle_image_removals,
    setup_approval_workflow,
    setup_approval_workflow_db
)
from models import Notification, Report


class TestNotificationUtils:
    """Test cases for notification utility functions."""
    
    def test_get_unread_count_with_user_email(self, app, db_session):
        """Test getting unread count with specific user email."""
        # Create test notifications
        Notification.create_notification(
            user_email='test@example.com',
            title='Test 1',
            message='Message 1',
            notification_type='approval_request'
        )
        Notification.create_notification(
            user_email='test@example.com',
            title='Test 2',
            message='Message 2',
            notification_type='status_update'
        )
        # Create read notification
        read_notification = Notification.create_notification(
            user_email='test@example.com',
            title='Test 3',
            message='Message 3',
            notification_type='completion'
        )
        read_notification.read = True
        db_session.commit()
        
        with app.app_context():
            count = get_unread_count('test@example.com')
            assert count == 2
    
    def test_get_unread_count_with_current_user(self, app, db_session, admin_user):
        """Test getting unread count with current user."""
        # Create test notification
        Notification.create_notification(
            user_email=admin_user.email,
            title='Test',
            message='Message',
            notification_type='approval_request'
        )
        
        with app.app_context():
            with patch('utils.current_user', admin_user):
                count = get_unread_count()
                assert count == 1
    
    def test_get_unread_count_no_user(self, app, db_session):
        """Test getting unread count with no user."""
        with app.app_context():
            with patch('utils.current_user') as mock_user:
                mock_user.is_authenticated = False
                count = get_unread_count()
                assert count == 0
    
    def test_create_approval_notification(self, app, db_session):
        """Test creating approval notification."""
        with app.app_context():
            notification = create_approval_notification(
                approver_email='approver@test.com',
                submission_id='test-123',
                stage=1,
                document_title='Test Document'
            )
            
            assert notification is not None
            assert notification.user_email == 'approver@test.com'
            assert notification.title == 'Approval Required - Stage 1'
            assert 'Test Document' in notification.message
            assert notification.type == 'approval_request'
            assert notification.related_submission_id == 'test-123'
    
    def test_create_status_update_notification_approved(self, app, db_session):
        """Test creating status update notification for approval."""
        with app.app_context():
            notification = create_status_update_notification(
                user_email='user@test.com',
                submission_id='test-456',
                status='approved',
                document_title='Test Document',
                approver_name='John Doe'
            )
            
            assert notification.title == 'Report Approved'
            assert 'approved by John Doe' in notification.message
            assert notification.type == 'status_update'
    
    def test_create_status_update_notification_rejected(self, app, db_session):
        """Test creating status update notification for rejection."""
        with app.app_context():
            notification = create_status_update_notification(
                user_email='user@test.com',
                submission_id='test-789',
                status='rejected',
                document_title='Test Document',
                approver_name='Jane Smith'
            )
            
            assert notification.title == 'Report Rejected'
            assert 'rejected by Jane Smith' in notification.message
    
    def test_create_completion_notification(self, app, db_session):
        """Test creating completion notification."""
        with app.app_context():
            notification = create_completion_notification(
                user_email='user@test.com',
                submission_id='test-complete',
                document_title='Completed Document'
            )
            
            assert notification.title == 'Report Completed'
            assert 'fully approved' in notification.message
            assert notification.type == 'completion'


class TestFileOperations:
    """Test cases for file operation utilities."""
    
    def test_load_submissions_existing_file(self, app):
        """Test loading submissions from existing file."""
        test_data = {
            'submission-1': {'title': 'Test 1'},
            'submission-2': {'title': 'Test 2'}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(test_data, f)
            temp_file = f.name
        
        try:
            with app.app_context():
                app.config['SUBMISSIONS_FILE'] = temp_file
                result = load_submissions()
                
                assert result == test_data
                assert len(result) == 2
        finally:
            os.unlink(temp_file)
    
    def test_load_submissions_nonexistent_file(self, app):
        """Test loading submissions from non-existent file."""
        with app.app_context():
            app.config['SUBMISSIONS_FILE'] = '/nonexistent/file.json'
            result = load_submissions()
            assert result == {}
    
    def test_load_submissions_invalid_json(self, app):
        """Test loading submissions from file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('invalid json content')
            temp_file = f.name
        
        try:
            with app.app_context():
                app.config['SUBMISSIONS_FILE'] = temp_file
                result = load_submissions()
                assert result == {}
        finally:
            os.unlink(temp_file)
    
    def test_save_submissions(self, app):
        """Test saving submissions to file."""
        test_data = {
            'submission-1': {'title': 'Test 1', 'status': 'draft'},
            'submission-2': {'title': 'Test 2', 'status': 'approved'}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = os.path.join(temp_dir, 'test_submissions.json')
            
            with app.app_context():
                app.config['SUBMISSIONS_FILE'] = temp_file
                result = save_submissions(test_data)
                
                assert result is True
                assert os.path.exists(temp_file)
                
                # Verify content
                with open(temp_file, 'r') as f:
                    saved_data = json.load(f)
                    assert saved_data == test_data


class TestEmailFunctions:
    """Test cases for email utility functions."""
    
    @patch('utils.smtplib.SMTP')
    @patch('utils.Config.get_smtp_credentials')
    def test_send_email_success(self, mock_get_credentials, mock_smtp):
        """Test successful email sending."""
        # Mock SMTP credentials
        mock_get_credentials.return_value = {
            'server': 'smtp.gmail.com',
            'port': 587,
            'username': 'test@gmail.com',
            'password': 'test-password',
            'sender': 'test@gmail.com'
        }
        
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        result = send_email(
            to_email='recipient@test.com',
            subject='Test Subject',
            html_content='<p>Test HTML content</p>',
            text_content='Test text content'
        )
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@gmail.com', 'test-password')
        mock_server.send_message.assert_called_once()
    
    @patch('utils.smtplib.SMTP')
    @patch('utils.Config.get_smtp_credentials')
    def test_send_email_no_credentials(self, mock_get_credentials, mock_smtp):
        """Test email sending with missing credentials."""
        mock_get_credentials.return_value = {
            'server': 'smtp.gmail.com',
            'port': 587,
            'username': '',
            'password': '',
            'sender': ''
        }
        
        result = send_email(
            to_email='recipient@test.com',
            subject='Test Subject',
            html_content='<p>Test content</p>'
        )
        
        assert result is False
        mock_smtp.assert_not_called()
    
    def test_send_email_no_recipient(self):
        """Test email sending with no recipient."""
        result = send_email(
            to_email='',
            subject='Test Subject',
            html_content='<p>Test content</p>'
        )
        
        assert result is False


class TestFormProcessing:
    """Test cases for form processing utilities."""
    
    def test_process_table_rows(self):
        """Test processing table rows from form data."""
        # Mock form data
        form_data = MagicMock()
        form_data.getlist.side_effect = lambda field: {
            'tag_number': ['TAG001', 'TAG002', 'TAG003'],
            'description': ['Pump 1', 'Valve 2', ''],
            'location': ['Area A', 'Area B', 'Area C']
        }.get(field, [])
        
        field_mappings = {
            'tag_number': 'tag',
            'description': 'desc',
            'location': 'loc'
        }
        
        result = process_table_rows(form_data, field_mappings)
        
        assert len(result) == 2  # Third row should be excluded (empty description)
        assert result[0] == {'tag': 'TAG001', 'desc': 'Pump 1', 'loc': 'Area A'}
        assert result[1] == {'tag': 'TAG002', 'desc': 'Valve 2', 'loc': 'Area B'}
    
    def test_process_table_rows_empty_data(self):
        """Test processing table rows with empty data."""
        form_data = MagicMock()
        form_data.getlist.return_value = []
        
        field_mappings = {'field1': 'output1', 'field2': 'output2'}
        
        result = process_table_rows(form_data, field_mappings)
        
        assert len(result) == 1  # Should return one blank row
        assert result[0] == {'output1': '', 'output2': ''}
    
    @patch('utils.os.path.exists')
    @patch('utils.os.remove')
    @patch('utils.current_app')
    def test_handle_image_removals(self, mock_app, mock_remove, mock_exists):
        """Test handling image removals."""
        mock_app.static_folder = '/static'
        mock_exists.return_value = True
        
        form_data = MagicMock()
        form_data.getlist.return_value = [
            '/static/uploads/image1.png',
            '/static/uploads/image2.jpg'
        ]
        
        url_list = [
            '/static/uploads/image1.png',
            '/static/uploads/image2.jpg',
            '/static/uploads/image3.png'
        ]
        
        handle_image_removals(form_data, 'removed_images', url_list)
        
        # Verify images were removed from list
        assert len(url_list) == 1
        assert '/static/uploads/image3.png' in url_list
        
        # Verify files were deleted
        assert mock_remove.call_count == 2


class TestApprovalWorkflow:
    """Test cases for approval workflow utilities."""
    
    def test_setup_approval_workflow_new_submission(self, app):
        """Test setting up approval workflow for new submission."""
        with app.app_context():
            app.config['DEFAULT_APPROVERS'] = [
                {'stage': 1, 'approver_email': 'approver1@test.com', 'title': 'Engineer'},
                {'stage': 2, 'approver_email': 'approver2@test.com', 'title': 'Manager'}
            ]
            
            submissions = {}
            submission_id = 'new-submission'
            
            approvals, locked = setup_approval_workflow(
                submission_id, 
                submissions,
                approver_emails=['custom1@test.com', 'custom2@test.com']
            )
            
            assert len(approvals) == 2
            assert approvals[0]['stage'] == 1
            assert approvals[0]['approver_email'] == 'custom1@test.com'
            assert approvals[0]['status'] == 'pending'
            assert approvals[1]['approver_email'] == 'custom2@test.com'
            assert locked is False
    
    def test_setup_approval_workflow_existing_submission(self, app):
        """Test setting up approval workflow for existing submission."""
        with app.app_context():
            existing_approvals = [
                {
                    'stage': 1,
                    'approver_email': 'old1@test.com',
                    'title': 'Engineer',
                    'status': 'approved',
                    'timestamp': '2024-01-01T10:00:00'
                },
                {
                    'stage': 2,
                    'approver_email': 'old2@test.com',
                    'title': 'Manager',
                    'status': 'pending',
                    'timestamp': None
                }
            ]
            
            submissions = {
                'existing-submission': {
                    'approvals': existing_approvals
                }
            }
            
            approvals, locked = setup_approval_workflow(
                'existing-submission',
                submissions,
                approver_emails=['new1@test.com', 'new2@test.com']
            )
            
            assert len(approvals) == 2
            assert approvals[0]['status'] == 'approved'  # Should remain approved
            assert approvals[0]['approver_email'] == 'old1@test.com'  # Should not change
            assert approvals[1]['approver_email'] == 'new2@test.com'  # Should update pending
            assert locked is True  # Should be locked due to stage 2 approval
    
    def test_setup_approval_workflow_db_new_report(self, app, db_session, admin_user):
        """Test setting up approval workflow for new database report."""
        with app.app_context():
            app.config['DEFAULT_APPROVERS'] = [
                {'stage': 1, 'approver_email': 'approver1@test.com', 'title': 'Engineer'}
            ]
            
            report = Report(
                id='test-report',
                type='SAT',
                user_email=admin_user.email,
                approvals_json=None
            )
            db_session.add(report)
            db_session.commit()
            
            approvals, locked = setup_approval_workflow_db(
                report,
                approver_emails=['custom@test.com']
            )
            
            assert len(approvals) == 1
            assert approvals[0]['approver_email'] == 'custom@test.com'
            assert approvals[0]['status'] == 'pending'
            assert locked is False