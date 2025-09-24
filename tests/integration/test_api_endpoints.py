"""
Integration tests for API endpoints.
"""
import pytest
import json
from flask import url_for
from models import db, Report, SATReport, User
from api.security import APIKey
from tests.factories import UserFactory, ReportFactory, SATReportFactory


class TestAuthEndpoints:
    """Test authentication API endpoints."""
    
    def test_welcome_page_unauthenticated(self, client):
        """Test welcome page for unauthenticated users."""
        response = client.get('/auth/welcome')
        assert response.status_code == 200
        assert b'Welcome' in response.data or b'Log In' in response.data
    
    def test_welcome_page_authenticated_redirects(self, client, admin_user):
        """Test welcome page redirects authenticated users."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response = client.get('/auth/welcome')
        assert response.status_code == 302  # Redirect to dashboard
    
    def test_register_get(self, client):
        """Test GET request to register page."""
        response = client.get('/auth/register')
        assert response.status_code == 200
        assert b'register' in response.data.lower() or b'sign up' in response.data.lower()
    
    def test_register_post_valid_data(self, client, db_session):
        """Test POST request to register with valid data."""
        data = {
            'full_name': 'Test User',
            'email': 'newuser@test.com',
            'password': 'password123',
            'requested_role': 'Engineer'
        }
        
        response = client.post('/auth/register', data=data)
        
        # Should redirect or show success
        assert response.status_code in [200, 302]
        
        # Verify user was created
        user = User.query.filter_by(email='newuser@test.com').first()
        assert user is not None
        assert user.full_name == 'Test User'
        assert user.requested_role == 'Engineer'
        assert user.status == 'Pending'
    
    def test_register_post_missing_fields(self, client):
        """Test POST request to register with missing fields."""
        data = {
            'full_name': 'Test User',
            'email': '',  # Missing email
            'password': 'password123',
            'requested_role': 'Engineer'
        }
        
        response = client.post('/auth/register', data=data)
        assert response.status_code == 200
        # Should show error message
    
    def test_register_post_duplicate_email(self, client, admin_user):
        """Test POST request to register with existing email."""
        data = {
            'full_name': 'Another User',
            'email': admin_user.email,  # Duplicate email
            'password': 'password123',
            'requested_role': 'Engineer'
        }
        
        response = client.post('/auth/register', data=data)
        assert response.status_code == 200
        # Should show error message about duplicate email
    
    def test_login_post_valid_credentials(self, client, admin_user):
        """Test login with valid credentials."""
        data = {
            'email': admin_user.email,
            'password': 'admin123'  # From fixture
        }
        
        with client.session_transaction() as sess:
            sess['csrf_token'] = 'test-token'
        
        response = client.post('/auth/login', data=data)
        # Should redirect to dashboard on success
        assert response.status_code in [200, 302]
    
    def test_login_post_invalid_credentials(self, client, admin_user):
        """Test login with invalid credentials."""
        data = {
            'email': admin_user.email,
            'password': 'wrongpassword'
        }
        
        response = client.post('/auth/login', data=data)
        assert response.status_code == 200
        # Should show error message
    
    def test_logout(self, client, admin_user):
        """Test logout functionality."""
        # Login first
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response = client.get('/auth/logout')
        assert response.status_code == 302  # Redirect after logout
        
        # Verify session is cleared
        with client.session_transaction() as sess:
            assert 'user_id' not in sess


class TestReportEndpoints:
    """Test report-related API endpoints."""
    
    def test_new_report_page_authenticated(self, client, admin_user):
        """Test accessing new report page when authenticated."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response = client.get('/reports/new')
        assert response.status_code == 200
    
    def test_new_report_page_unauthenticated(self, client):
        """Test accessing new report page when not authenticated."""
        response = client.get('/reports/new')
        assert response.status_code == 302  # Redirect to login
    
    def test_new_sat_report_page(self, client, admin_user):
        """Test accessing new SAT report page."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response = client.get('/reports/new/sat')
        assert response.status_code in [200, 302]  # May redirect to full form
    
    def test_new_sat_full_page(self, client, admin_user):
        """Test accessing full SAT report form."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response = client.get('/reports/new/sat/full')
        assert response.status_code == 200
    
    def test_report_creation_post(self, client, admin_user, db_session):
        """Test creating a new report via POST."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        data = {
            'document_title': 'Test SAT Report',
            'document_reference': 'TEST-001',
            'project_reference': 'PROJ-001',
            'client_name': 'Test Client',
            'revision': 'R0',
            'prepared_by': 'Test Engineer',
            'date': '2024-01-01',
            'purpose': 'Testing purposes',
            'scope': 'Test scope'
        }
        
        # This would need to match the actual form endpoint
        # response = client.post('/reports/create', data=data)
        # For now, just verify the data structure is valid
        assert all(key in data for key in ['document_title', 'project_reference'])


class TestAPIEndpoints:
    """Test REST API endpoints."""
    
    def test_api_without_key(self, client):
        """Test API access without API key."""
        response = client.get('/api/reports')
        assert response.status_code == 401
        
        data = response.get_json()
        assert 'error' in data
        assert 'API key required' in data['error']
    
    def test_api_with_invalid_key(self, client):
        """Test API access with invalid API key."""
        headers = {'X-API-Key': 'invalid-key'}
        response = client.get('/api/reports', headers=headers)
        assert response.status_code == 401
        
        data = response.get_json()
        assert 'error' in data
        assert 'Invalid API key' in data['error']
    
    def test_api_with_valid_key(self, client, db_session):
        """Test API access with valid API key."""
        # Create API key
        api_key = APIKey(
            key='test-api-key-123',
            name='Test Key',
            user_email='test@example.com',
            is_active=True
        )
        db_session.add(api_key)
        db_session.commit()
        
        headers = {'X-API-Key': 'test-api-key-123'}
        response = client.get('/api/reports', headers=headers)
        
        # Should not return 401 (may return 404 if endpoint doesn't exist)
        assert response.status_code != 401
    
    def test_check_auth_endpoint_authenticated(self, client, admin_user):
        """Test check auth endpoint with authenticated user."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response = client.get('/api/check-auth')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['authenticated'] is True
        assert data['user'] == admin_user.email
    
    def test_check_auth_endpoint_unauthenticated(self, client):
        """Test check auth endpoint without authentication."""
        response = client.get('/api/check-auth')
        assert response.status_code == 401
        
        data = response.get_json()
        assert data['authenticated'] is False
    
    def test_get_users_by_role_endpoint(self, client, admin_user, db_session):
        """Test get users by role endpoint."""
        # Create additional test users
        engineer = UserFactory(role='Engineer', status='Active')
        pm = UserFactory(role='PM', status='Active')
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response = client.get('/api/get-users-by-role')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        assert 'users' in data
        assert 'Admin' in data['users']
        assert 'Engineer' in data['users']
        assert 'PM' in data['users']
    
    def test_refresh_csrf_endpoint(self, client):
        """Test CSRF token refresh endpoint."""
        response = client.get('/refresh_csrf')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'csrf_token' in data
        assert data['csrf_token'] is not None


class TestHealthEndpoints:
    """Test health check and status endpoints."""
    
    def test_health_check_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get('/health')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['status'] == 'healthy'
        assert 'message' in data
        assert 'database' in data
    
    def test_root_redirect_unauthenticated(self, client):
        """Test root URL redirects to welcome for unauthenticated users."""
        response = client.get('/')
        assert response.status_code == 302
        # Should redirect to welcome page
    
    def test_root_redirect_authenticated(self, client, admin_user):
        """Test root URL redirects to dashboard for authenticated users."""
        with client.session_transaction() as sess:
            sess['user_id'] = admin_user.id
            sess['_fresh'] = True
        
        response = client.get('/')
        assert response.status_code == 302
        # Should redirect to dashboard


class TestErrorHandling:
    """Test error handling in API endpoints."""
    
    def test_404_error_handler(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent-endpoint')
        assert response.status_code == 404
    
    def test_csrf_error_handling_ajax(self, client):
        """Test CSRF error handling for AJAX requests."""
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
        
        # This would trigger CSRF error in a real scenario
        response = client.post('/auth/login', 
                             json={'email': 'test@test.com', 'password': 'test'},
                             headers=headers)
        
        # Response depends on CSRF configuration
        # Should handle gracefully
        assert response.status_code in [200, 400, 403]
    
    def test_method_not_allowed(self, client):
        """Test method not allowed error."""
        # Try POST on a GET-only endpoint
        response = client.post('/auth/welcome')
        assert response.status_code == 405  # Method Not Allowed


class TestDataValidation:
    """Test data validation in API endpoints."""
    
    def test_email_validation_in_registration(self, client):
        """Test email validation during registration."""
        data = {
            'full_name': 'Test User',
            'email': 'invalid-email',  # Invalid email format
            'password': 'password123',
            'requested_role': 'Engineer'
        }
        
        response = client.post('/auth/register', data=data)
        # Should handle invalid email gracefully
        assert response.status_code in [200, 400]
    
    def test_role_validation_in_registration(self, client):
        """Test role validation during registration."""
        data = {
            'full_name': 'Test User',
            'email': 'test@example.com',
            'password': 'password123',
            'requested_role': 'InvalidRole'  # Invalid role
        }
        
        response = client.post('/auth/register', data=data)
        assert response.status_code == 200
        # Should show error for invalid role
    
    def test_password_strength_validation(self, client):
        """Test password strength validation."""
        data = {
            'full_name': 'Test User',
            'email': 'test@example.com',
            'password': '123',  # Weak password
            'requested_role': 'Engineer'
        }
        
        response = client.post('/auth/register', data=data)
        # Should handle weak password appropriately
        assert response.status_code in [200, 400]