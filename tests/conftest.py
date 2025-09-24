"""
Pytest configuration and shared fixtures for the SAT Report Generator test suite.
"""
import os
import tempfile
import pytest
from flask import Flask
from models import db, User, Report, SATReport
from app import create_app
from app_config import Config


class TestConfig(Config):
    """Test configuration class."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test-secret-key'
    UPLOAD_FOLDER = tempfile.mkdtemp()
    OUTPUT_DIR = tempfile.mkdtemp()
    SUBMISSIONS_FILE = os.path.join(tempfile.mkdtemp(), 'test_submissions.json')
    SIGNATURES_FOLDER = tempfile.mkdtemp()
    UPLOAD_ROOT = tempfile.mkdtemp()
    SMTP_SERVER = 'localhost'
    SMTP_PORT = 587
    SMTP_USERNAME = 'test@example.com'
    SMTP_PASSWORD = 'test-password'
    ENABLE_PDF_EXPORT = False
    USE_HTTPS = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


@pytest.fixture(scope='session')
def app():
    """Create application for the tests."""
    app = create_app(config_obj=TestConfig)
    
    # Create application context
    ctx = app.app_context()
    ctx.push()
    
    yield app
    
    ctx.pop()


@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture(scope='function')
def db_session(app):
    """Create a database session for testing."""
    with app.app_context():
        # Create all tables
        db.create_all()
    
    yield db.session
    
    # Clean up after test
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    user = User(
        email='admin@test.com',
        full_name='Test Admin',
        role='Admin',
        status='Active'
    )
    user.set_password('admin123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def engineer_user(db_session):
    """Create an engineer user for testing."""
    user = User(
        email='engineer@test.com',
        full_name='Test Engineer',
        role='Engineer',
        status='Active'
    )
    user.set_password('engineer123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def pm_user(db_session):
    """Create a PM user for testing."""
    user = User(
        email='pm@test.com',
        full_name='Test PM',
        role='PM',
        status='Active'
    )
    user.set_password('pm123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def authenticated_client(client, admin_user):
    """Create an authenticated test client."""
    with client.session_transaction() as sess:
        sess['user_id'] = admin_user.id
        sess['_fresh'] = True
    return client


@pytest.fixture
def sample_report(db_session, admin_user):
    """Create a sample report for testing."""
    report = Report(
        id='test-report-123',
        type='SAT',
        status='DRAFT',
        document_title='Test SAT Report',
        document_reference='TEST-001',
        project_reference='PROJECT-001',
        client_name='Test Client',
        revision='R0',
        prepared_by='Test Engineer',
        user_email=admin_user.email,
        version='R0'
    )
    db_session.add(report)
    
    sat_report = SATReport(
        report_id=report.id,
        data_json='{"test": "data"}',
        date='2024-01-01',
        purpose='Testing purposes',
        scope='Test scope'
    )
    db_session.add(sat_report)
    db_session.commit()
    
    return report


@pytest.fixture
def sample_sat_data():
    """Sample SAT report data for testing."""
    return {
        'context': {
            'DOCUMENT_TITLE': 'Test SAT Report',
            'DOCUMENT_REFERENCE': 'TEST-001',
            'PROJECT_REFERENCE': 'PROJECT-001',
            'CLIENT_NAME': 'Test Client',
            'REVISION': 'R0',
            'PREPARED_BY': 'Test Engineer',
            'DATE': '2024-01-01',
            'PURPOSE': 'Testing purposes',
            'SCOPE': 'Test scope'
        },
        'test_data': {
            'test_name': 'Sample Test',
            'test_result': 'PASS',
            'comments': 'Test completed successfully'
        }
    }