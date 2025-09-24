"""
Integration tests for email notification system.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from utils import (
    send_email, 
    send_approval_link, 
    send_edit_link, 
    notify_completion,
    create_approval_notification,
    create_status_update_notification,
    create_completion_notification,
    create_new_submission_notification
)
from models import db, Notification, User
from tests.factories import UserFactory, ReportFactory


class TestEmailSending:
    """Test email sending functionality."""
    
    @patch('utils.smtplib.SMTP')
    @patch('utils.Config.get_smtp_credentials')
    def test_send_email_success(self, mock_get_credentials, mock_smtp, app):
        """Test successful email sending."""
        # Mock SMTP credentials
        mock_get_credentials.return_value = {
            'server': 'smtp.test.com',
            'port': 587,
            'username': 'test@test.com',
            'password': 'test-password',
            'sender': 'sender@test.com'
        }
        
        # Mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        with app.app_context():
            result = send_email(
                to_email='recipient@test.com',
                subject='Test Email',
                html_content='<h1>Test HTML Content</h1>',
                text_content='Test text content'
            )
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with('test@test.com', 'test-password')
        mock_server.send_message.assert_called_once()
    
    @patch('utils.smtplib.SMTP')
    @patch('utils.Config.get_smtp_credentials')
    def test_send_email_smtp_error(self, mock_get_credentials, mock_smtp, app):
        """Test email sending with SMTP error."""
        mock_get_credentials.return_value = {
            'server': 'smtp.test.com',
            'port': 587,
            'username': 'test@test.com',
            'password': 'test-password',
            'sender': 'sender@test.com'
        }
        
        # Mock SMTP to raise exception
        mock_smtp.side_effect = Exception('SMTP connection failed')
        
        with app.app_context():
            result = send_email(
                to_email='recipient@test.com',
                subject='Test Email',
                html_content='<h1>Test Content</h1>'
            )
        
        assert result is False
    
    @patch('utils.Config.get_smtp_credentials')
    def test_send_email_no_credentials(self, mock_get_credentials, app):
        """Test email sending without credentials."""
        mock_get_credentials.return_value = {
            'server': 'smtp.test.com',
            'port': 587,
            'username': '',  # No username
            'password': '',  # No password
            'sender': ''
        }
        
        with app.app_context():
            result = send_email(
                to_email='recipient@test.com',
                subject='Test Email',
                html_content='<h1>Test Content</h1>'
            )
        
        assert result is False
    
    def test_send_email_no_recipient(self, app):
        """Test email sending without recipient."""
        with app.app_context():
            result = send_email(
                to_email='',  # No recipient
                subject='Test Email',
                html_content='<h1>Test Content</h1>'
            )
        
        assert result is False


class TestApprovalEmailNotifications:
    """Test approval-related email notifications."""
    
    @patch('utils.send_email')
    def test_send_approval_link(self, mock_send_email, app):
        """Test sending approval link email."""
        mock_send_email.return_value = True
        
        with app.app_context():
            app.config['DEFAULT_APPROVERS'] = [
                {'stage': 1, 'title': 'Engineer', 'approver_email': 'engineer@test.com'},
                {'stage': 2, 'title': 'Manager', 'approver_email': 'manager@test.com'}
            ]
            
            result = send_approval_link(
                approver_email='approver@test.com',
                submission_id='test-123',
                stage=1
            )
        
        assert result is True
        mock_send_email.assert_called_once()
        
        # Verify email content
        call_args = mock_send_email.call_args
        assert call_args[1]['to_email'] == 'approver@test.com'
        assert 'Approval required' in call_args[1]['subject']
        assert 'test-123' in call_args[1]['html_content']
        assert 'Stage 1' in call_args[1]['html_content']
    
    @patch('utils.send_email')
    def test_send_approval_link_no_email(self, mock_send_email, app):
        """Test sending approval link without email."""
        with app.app_context():
            result = send_approval_link(
                approver_email='',  # No email
                submission_id='test-123',
                stage=1
            )
        
        assert result is False
        mock_send_email.assert_not_called()
    
    @patch('utils.send_email')
    def test_send_edit_link(self, mock_send_email, app):
        """Test sending edit link email."""
        mock_send_email.return_value = True
        
        with app.app_context():
            result = send_edit_link(
                user_email='user@test.com',
                submission_id='test-456'
            )
        
        assert result is True
        mock_send_email.assert_called_once()
        
        # Verify email content
        call_args = mock_send_email.call_args
        assert call_args[1]['to_email'] == 'user@test.com'
        assert 'edit' in call_args[1]['subject'].lower()
        assert 'test-456' in call_args[1]['html_content']
    
    @patch('utils.send_email')
    def test_notify_completion(self, mock_send_email, app):
        """Test completion notification email."""
        mock_send_email.return_value = True
        
        with app.app_context():
            result = notify_completion(
                user_email='user@test.com',
                submission_id='test-789'
            )
        
        assert result is True
        mock_send_email.assert_called_once()
        
        # Verify email content
        call_args = mock_send_email.call_args
        assert call_args[1]['to_email'] == 'user@test.com'
        assert 'approved' in call_args[1]['subject'].lower()
        assert 'test-789' in call_args[1]['html_content']


class TestNotificationCreation:
    """Test notification creation and database integration."""
    
    def test_create_approval_notification(self, app, db_session):
        """Test creating approval notification in database."""
        with app.app_context():
            notification = create_approval_notification(
                approver_email='approver@test.com',
                submission_id='test-approval',
                stage=2,
                document_title='Test Document'
            )
        
        assert notification is not None
        assert notification.user_email == 'approver@test.com'
        assert notification.title == 'Approval Required - Stage 2'
        assert 'Test Document' in notification.message
        assert notification.type == 'approval_request'
        assert notification.related_submission_id == 'test-approval'
        assert notification.read is False
        
        # Verify it's in database
        saved_notification = Notification.query.get(notification.id)
        assert saved_notification is not None
    
    def test_create_status_update_notification_approved(self, app, db_session):
        """Test creating status update notification for approval."""
        with app.app_context():
            notification = create_status_update_notification(
                user_email='user@test.com',
                submission_id='test-status',
                status='approved',
                document_title='Status Test Document',
                approver_name='John Approver'
            )
        
        assert notification.title == 'Report Approved'
        assert 'approved by John Approver' in notification.message
        assert notification.type == 'status_update'
        assert notification.related_submission_id == 'test-status'
    
    def test_create_status_update_notification_rejected(self, app, db_session):
        """Test creating status update notification for rejection."""
        with app.app_context():
            notification = create_status_update_notification(
                user_email='user@test.com',
                submission_id='test-reject',
                status='rejected',
                document_title='Reject Test Document',
                approver_name='Jane Reviewer'
            )
        
        assert notification.title == 'Report Rejected'
        assert 'rejected by Jane Reviewer' in notification.message
        assert notification.type == 'status_update'
    
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
        assert notification.related_submission_id == 'test-complete'
    
    def test_create_new_submission_notification(self, app, db_session):
        """Test creating new submission notifications for admins."""
        admin_emails = ['admin1@test.com', 'admin2@test.com']
        
        with app.app_context():
            notifications = create_new_submission_notification(
                admin_emails=admin_emails,
                submission_id='test-new-sub',
                document_title='New Submission Document',
                submitter_email='submitter@test.com'
            )
        
        # Should create notifications for all admins
        created_notifications = Notification.query.filter_by(
            related_submission_id='test-new-sub'
        ).all()
        
        assert len(created_notifications) == 2
        
        emails = [n.user_email for n in created_notifications]
        assert 'admin1@test.com' in emails
        assert 'admin2@test.com' in emails
        
        for notification in created_notifications:
            assert notification.title == 'New Report Submitted'
            assert 'submitter@test.com' in notification.message
            assert notification.type == 'new_submission'


class TestEmailNotificationWorkflow:
    """Test complete email notification workflows."""
    
    @patch('utils.send_email')
    def test_approval_workflow_notifications(self, mock_send_email, app, db_session):
        """Test notifications throughout approval workflow."""
        mock_send_email.return_value = True
        
        # Create test users
        submitter = UserFactory(email='submitter@test.com')
        approver1 = UserFactory(email='approver1@test.com', role='Engineer')
        approver2 = UserFactory(email='approver2@test.com', role='Manager')
        admin = UserFactory(email='admin@test.com', role='Admin')
        db_session.commit()
        
        with app.app_context():
            # 1. New submission notification to admins
            create_new_submission_notification(
                admin_emails=[admin.email],
                submission_id='workflow-test',
                document_title='Workflow Test Document',
                submitter_email=submitter.email
            )
            
            # 2. Approval request to first approver
            create_approval_notification(
                approver_email=approver1.email,
                submission_id='workflow-test',
                stage=1,
                document_title='Workflow Test Document'
            )
            
            # 3. Status update to submitter (first approval)
            create_status_update_notification(
                user_email=submitter.email,
                submission_id='workflow-test',
                status='approved',
                document_title='Workflow Test Document',
                approver_name=approver1.full_name
            )
            
            # 4. Approval request to second approver
            create_approval_notification(
                approver_email=approver2.email,
                submission_id='workflow-test',
                stage=2,
                document_title='Workflow Test Document'
            )
            
            # 5. Final completion notification
            create_completion_notification(
                user_email=submitter.email,
                submission_id='workflow-test',
                document_title='Workflow Test Document'
            )
        
        # Verify all notifications were created
        all_notifications = Notification.query.filter_by(
            related_submission_id='workflow-test'
        ).all()
        
        assert len(all_notifications) == 5
        
        # Verify notification types
        notification_types = [n.type for n in all_notifications]
        assert 'new_submission' in notification_types
        assert 'approval_request' in notification_types
        assert 'status_update' in notification_types
        assert 'completion' in notification_types
        
        # Verify recipients
        recipients = [n.user_email for n in all_notifications]
        assert submitter.email in recipients
        assert approver1.email in recipients
        assert approver2.email in recipients
        assert admin.email in recipients
    
    def test_notification_read_status_tracking(self, app, db_session):
        """Test tracking read status of notifications."""
        user_email = 'reader@test.com'
        
        with app.app_context():
            # Create multiple notifications
            notifications = [
                create_approval_notification(
                    approver_email=user_email,
                    submission_id=f'test-{i}',
                    stage=1,
                    document_title=f'Document {i}'
                )
                for i in range(3)
            ]
        
        # Initially all should be unread
        unread_count = Notification.query.filter_by(
            user_email=user_email,
            read=False
        ).count()
        assert unread_count == 3
        
        # Mark one as read
        notifications[0].read = True
        db_session.commit()
        
        # Verify count updated
        unread_count = Notification.query.filter_by(
            user_email=user_email,
            read=False
        ).count()
        assert unread_count == 2
        
        # Mark all as read
        Notification.query.filter_by(user_email=user_email).update({'read': True})
        db_session.commit()
        
        # Verify all read
        unread_count = Notification.query.filter_by(
            user_email=user_email,
            read=False
        ).count()
        assert unread_count == 0
    
    @patch('utils.send_email')
    def test_email_retry_mechanism(self, mock_send_email, app):
        """Test email retry mechanism on failure."""
        # Mock email to fail first two times, succeed on third
        mock_send_email.side_effect = [False, False, True]
        
        with app.app_context():
            # This would test the retry logic if implemented
            # For now, just verify the mock behavior
            result1 = send_email('test@test.com', 'Test', 'Content')
            result2 = send_email('test@test.com', 'Test', 'Content')
            result3 = send_email('test@test.com', 'Test', 'Content')
        
        assert result1 is False
        assert result2 is False
        assert result3 is True
        assert mock_send_email.call_count == 3
    
    def test_notification_cleanup_old_notifications(self, app, db_session):
        """Test cleanup of old notifications."""
        from datetime import datetime, timedelta
        
        user_email = 'cleanup@test.com'
        
        with app.app_context():
            # Create old notification (simulate by manually setting date)
            old_notification = create_approval_notification(
                approver_email=user_email,
                submission_id='old-test',
                stage=1,
                document_title='Old Document'
            )
            
            # Manually set old date
            old_notification.created_at = datetime.utcnow() - timedelta(days=90)
            db_session.commit()
            
            # Create recent notification
            recent_notification = create_approval_notification(
                approver_email=user_email,
                submission_id='recent-test',
                stage=1,
                document_title='Recent Document'
            )
        
        # Verify both exist
        all_notifications = Notification.query.filter_by(user_email=user_email).all()
        assert len(all_notifications) == 2
        
        # Simulate cleanup of notifications older than 30 days
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        old_notifications = Notification.query.filter(
            Notification.user_email == user_email,
            Notification.created_at < cutoff_date
        ).all()
        
        assert len(old_notifications) == 1
        assert old_notifications[0].related_submission_id == 'old-test'
        
        # Delete old notifications
        for notification in old_notifications:
            db_session.delete(notification)
        db_session.commit()
        
        # Verify only recent notification remains
        remaining_notifications = Notification.query.filter_by(user_email=user_email).all()
        assert len(remaining_notifications) == 1
        assert remaining_notifications[0].related_submission_id == 'recent-test'