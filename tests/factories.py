"""
Factory classes for generating test data using factory-boy.
"""
import factory
import json
from datetime import datetime
from models import db, User, Report, SATReport, Notification, SystemSettings


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    email = factory.Sequence(lambda n: f'user{n}@test.com')
    full_name = factory.Faker('name')
    role = factory.Iterator(['Admin', 'Engineer', 'Automation Manager', 'PM'])
    status = 'Active'
    created_date = factory.LazyFunction(datetime.utcnow)
    
    @factory.post_generation
    def set_password(obj, create, extracted, **kwargs):
        """Set password after user creation."""
        if not create:
            return
        
        password = extracted or 'password123'
        obj.set_password(password)


class AdminUserFactory(UserFactory):
    """Factory for creating Admin users."""
    role = 'Admin'
    email = factory.Sequence(lambda n: f'admin{n}@test.com')


class EngineerUserFactory(UserFactory):
    """Factory for creating Engineer users."""
    role = 'Engineer'
    email = factory.Sequence(lambda n: f'engineer{n}@test.com')


class PMUserFactory(UserFactory):
    """Factory for creating PM users."""
    role = 'PM'
    email = factory.Sequence(lambda n: f'pm{n}@test.com')


class ReportFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating Report instances."""
    
    class Meta:
        model = Report
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    id = factory.Sequence(lambda n: f'report-{n:04d}')
    type = 'SAT'
    status = 'DRAFT'
    document_title = factory.Faker('sentence', nb_words=4)
    document_reference = factory.Sequence(lambda n: f'DOC-{n:04d}')
    project_reference = factory.Sequence(lambda n: f'PROJ-{n:04d}')
    client_name = factory.Faker('company')
    revision = 'R0'
    prepared_by = factory.Faker('name')
    user_email = factory.SubFactory(UserFactory)
    version = 'R0'
    locked = False
    approval_notification_sent = False
    
    @factory.lazy_attribute
    def user_email(self):
        """Generate user email for the report."""
        return UserFactory().email
    
    @factory.post_generation
    def approvals(obj, create, extracted, **kwargs):
        """Set up approval workflow after creation."""
        if not create:
            return
        
        if extracted:
            obj.approvals_json = json.dumps(extracted)
        else:
            # Default approval workflow
            default_approvals = [
                {
                    'stage': 1,
                    'approver_email': 'approver1@test.com',
                    'title': 'Engineer',
                    'status': 'pending',
                    'timestamp': None,
                    'signature': None,
                    'comment': ''
                },
                {
                    'stage': 2,
                    'approver_email': 'approver2@test.com',
                    'title': 'Manager',
                    'status': 'pending',
                    'timestamp': None,
                    'signature': None,
                    'comment': ''
                }
            ]
            obj.approvals_json = json.dumps(default_approvals)


class ApprovedReportFactory(ReportFactory):
    """Factory for creating approved reports."""
    status = 'APPROVED'
    locked = True
    
    @factory.post_generation
    def approvals(obj, create, extracted, **kwargs):
        """Set up approved workflow."""
        if not create:
            return
        
        approved_workflow = [
            {
                'stage': 1,
                'approver_email': 'approver1@test.com',
                'title': 'Engineer',
                'status': 'approved',
                'timestamp': datetime.utcnow().isoformat(),
                'signature': 'John Engineer',
                'comment': 'Approved - looks good'
            },
            {
                'stage': 2,
                'approver_email': 'approver2@test.com',
                'title': 'Manager',
                'status': 'approved',
                'timestamp': datetime.utcnow().isoformat(),
                'signature': 'Jane Manager',
                'comment': 'Final approval granted'
            }
        ]
        obj.approvals_json = json.dumps(approved_workflow)


class SATReportFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating SATReport instances."""
    
    class Meta:
        model = SATReport
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    report = factory.SubFactory(ReportFactory)
    report_id = factory.SelfAttribute('report.id')
    date = factory.Faker('date')
    purpose = factory.Faker('sentence', nb_words=8)
    scope = factory.Faker('text', max_nb_chars=200)
    
    @factory.lazy_attribute
    def data_json(self):
        """Generate comprehensive SAT data."""
        return json.dumps({
            'context': {
                'DOCUMENT_TITLE': self.report.document_title,
                'DOCUMENT_REFERENCE': self.report.document_reference,
                'PROJECT_REFERENCE': self.report.project_reference,
                'CLIENT_NAME': self.report.client_name,
                'REVISION': self.report.revision,
                'PREPARED_BY': self.report.prepared_by,
                'DATE': self.date,
                'PURPOSE': self.purpose,
                'SCOPE': self.scope
            },
            'test_results': [
                {
                    'test_name': 'System Startup Test',
                    'expected_result': 'System starts within 30 seconds',
                    'actual_result': 'System started in 25 seconds',
                    'status': 'PASS',
                    'comments': 'Test completed successfully'
                },
                {
                    'test_name': 'Communication Test',
                    'expected_result': 'All devices respond to ping',
                    'actual_result': 'All devices responded',
                    'status': 'PASS',
                    'comments': 'Network communication verified'
                }
            ],
            'equipment_list': [
                {
                    'tag_number': 'PLC-001',
                    'description': 'Main PLC Controller',
                    'manufacturer': 'Allen Bradley',
                    'model': 'CompactLogix 5380'
                }
            ]
        })
    
    @factory.lazy_attribute
    def scada_image_urls(self):
        """Generate sample SCADA image URLs."""
        return json.dumps([
            '/static/uploads/scada_overview.png',
            '/static/uploads/scada_alarms.png'
        ])
    
    @factory.lazy_attribute
    def trends_image_urls(self):
        """Generate sample trends image URLs."""
        return json.dumps([
            '/static/uploads/trend_temperature.png',
            '/static/uploads/trend_pressure.png'
        ])
    
    @factory.lazy_attribute
    def alarm_image_urls(self):
        """Generate sample alarm image URLs."""
        return json.dumps([
            '/static/uploads/alarm_history.png'
        ])


class NotificationFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating Notification instances."""
    
    class Meta:
        model = Notification
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    user_email = factory.Faker('email')
    title = factory.Faker('sentence', nb_words=4)
    message = factory.Faker('text', max_nb_chars=200)
    type = factory.Iterator([
        'approval_request', 
        'status_update', 
        'completion', 
        'new_submission'
    ])
    related_submission_id = factory.Sequence(lambda n: f'submission-{n:04d}')
    read = False
    created_at = factory.LazyFunction(datetime.utcnow)
    action_url = factory.Faker('url')


class ApprovalNotificationFactory(NotificationFactory):
    """Factory for creating approval request notifications."""
    type = 'approval_request'
    title = 'Approval Required - Stage 1'
    
    @factory.lazy_attribute
    def message(self):
        return f"SAT Report requires your approval."


class StatusUpdateNotificationFactory(NotificationFactory):
    """Factory for creating status update notifications."""
    type = 'status_update'
    title = factory.Iterator(['Report Approved', 'Report Rejected', 'Status Updated'])


class SystemSettingsFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating SystemSettings instances."""
    
    class Meta:
        model = SystemSettings
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = 'commit'
    
    key = factory.Sequence(lambda n: f'setting_key_{n}')
    value = factory.Faker('word')
    updated_at = factory.LazyFunction(datetime.utcnow)


# Batch factories for creating multiple instances
class BatchUserFactory:
    """Factory for creating batches of users."""
    
    @staticmethod
    def create_team(size=5):
        """Create a team with mixed roles."""
        users = []
        users.append(AdminUserFactory())  # At least one admin
        
        for _ in range(size - 1):
            users.append(UserFactory())
        
        return users
    
    @staticmethod
    def create_approval_chain():
        """Create users for a typical approval chain."""
        return [
            EngineerUserFactory(email='engineer@test.com'),
            UserFactory(role='Automation Manager', email='manager@test.com'),
            PMUserFactory(email='pm@test.com')
        ]


class BatchReportFactory:
    """Factory for creating batches of reports."""
    
    @staticmethod
    def create_workflow_reports(user_email='test@example.com'):
        """Create reports in different workflow stages."""
        return [
            ReportFactory(user_email=user_email, status='DRAFT'),
            ReportFactory(user_email=user_email, status='PENDING'),
            ApprovedReportFactory(user_email=user_email),
            ReportFactory(user_email=user_email, status='REJECTED')
        ]
    
    @staticmethod
    def create_reports_with_sat_data(count=3):
        """Create reports with associated SAT data."""
        reports = []
        for _ in range(count):
            report = ReportFactory()
            SATReportFactory(report=report)
            reports.append(report)
        return reports


# Trait factories for specific scenarios
class TraitFactory:
    """Factory traits for specific test scenarios."""
    
    @staticmethod
    def pending_approval_report():
        """Create a report pending approval."""
        return ReportFactory(
            status='PENDING',
            approvals=[
                {
                    'stage': 1,
                    'approver_email': 'approver@test.com',
                    'status': 'pending',
                    'timestamp': None
                }
            ]
        )
    
    @staticmethod
    def rejected_report():
        """Create a rejected report."""
        return ReportFactory(
            status='REJECTED',
            approvals=[
                {
                    'stage': 1,
                    'approver_email': 'approver@test.com',
                    'status': 'rejected',
                    'timestamp': datetime.utcnow().isoformat(),
                    'comment': 'Needs revision'
                }
            ]
        )
    
    @staticmethod
    def locked_report():
        """Create a locked report (in approval process)."""
        return ReportFactory(
            locked=True,
            status='PENDING'
        )