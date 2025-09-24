"""
Unit tests for authentication and authorization functions.
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import session, g
from flask_login import current_user, login_user, logout_user
from auth import login_required, admin_required, role_required
from models import User


class TestAuthDecorators:
    """Test cases for authentication decorators."""
    
    def test_login_required_authenticated_user(self, app, client, admin_user):
        """Test login_required decorator with authenticated user."""
        @app.route('/test-login-required')
        @login_required
        def test_view():
            return 'success'
        
        # Mock session manager to return valid session
        with patch('auth.session_manager') as mock_session_manager:
            mock_session_manager.is_session_valid.return_value = True
            
            with client.session_transaction() as sess:
                sess['user_id'] = admin_user.id
                sess['_fresh'] = True
            
            # Mock current_user
            with patch('auth.current_user', admin_user):
                response = client.get('/test-login-required')
                assert response.status_code == 200
                assert response.data == b'success'
    
    def test_login_required_unauthenticated_user(self, app, client):
        """Test login_required decorator with unauthenticated user."""
        @app.route('/test-login-required')
        @login_required
        def test_view():
            return 'success'
        
        # Mock session manager to return invalid session
        with patch('auth.session_manager') as mock_session_manager:
            mock_session_manager.is_session_valid.return_value = False
            
            response = client.get('/test-login-required')
            assert response.status_code == 302  # Redirect to login
    
    def test_login_required_invalid_session(self, app, client, admin_user):
        """Test login_required decorator with invalid session."""
        @app.route('/test-login-required')
        @login_required
        def test_view():
            return 'success'
        
        # Mock session manager to return invalid session
        with patch('auth.session_manager') as mock_session_manager:
            mock_session_manager.is_session_valid.return_value = False
            
            with client.session_transaction() as sess:
                sess['user_id'] = admin_user.id
            
            response = client.get('/test-login-required')
            assert response.status_code == 302  # Redirect to login
    
    def test_admin_required_admin_user(self, app, client, admin_user):
        """Test admin_required decorator with admin user."""
        @app.route('/test-admin-required')
        @admin_required
        def test_view():
            return 'admin success'
        
        with patch('auth.session_manager') as mock_session_manager:
            mock_session_manager.is_session_valid.return_value = True
            
            with client.session_transaction() as sess:
                sess['user_id'] = admin_user.id
                sess['_fresh'] = True
            
            with patch('auth.current_user', admin_user):
                response = client.get('/test-admin-required')
                assert response.status_code == 200
                assert response.data == b'admin success'
    
    def test_admin_required_non_admin_user(self, app, client, engineer_user):
        """Test admin_required decorator with non-admin user."""
        @app.route('/test-admin-required')
        @admin_required
        def test_view():
            return 'admin success'
        
        with patch('auth.session_manager') as mock_session_manager:
            mock_session_manager.is_session_valid.return_value = True
            
            with client.session_transaction() as sess:
                sess['user_id'] = engineer_user.id
                sess['_fresh'] = True
            
            with patch('auth.current_user', engineer_user):
                response = client.get('/test-admin-required')
                assert response.status_code == 302  # Redirect due to insufficient privileges
    
    def test_role_required_authorized_role(self, app, client, engineer_user):
        """Test role_required decorator with authorized role."""
        @app.route('/test-role-required')
        @role_required(['Engineer', 'Admin'])
        def test_view():
            return 'role success'
        
        with patch('auth.session_manager') as mock_session_manager:
            mock_session_manager.is_session_valid.return_value = True
            
            with client.session_transaction() as sess:
                sess['user_id'] = engineer_user.id
                sess['_fresh'] = True
            
            with patch('auth.current_user', engineer_user):
                response = client.get('/test-role-required')
                assert response.status_code == 200
                assert response.data == b'role success'
    
    def test_role_required_unauthorized_role(self, app, client, pm_user):
        """Test role_required decorator with unauthorized role."""
        @app.route('/test-role-required')
        @role_required(['Engineer', 'Admin'])
        def test_view():
            return 'role success'
        
        with patch('auth.session_manager') as mock_session_manager:
            mock_session_manager.is_session_valid.return_value = True
            
            with client.session_transaction() as sess:
                sess['user_id'] = pm_user.id
                sess['_fresh'] = True
            
            with patch('auth.current_user', pm_user):
                response = client.get('/test-role-required')
                assert response.status_code == 302  # Redirect due to insufficient role
    
    def test_role_required_inactive_user(self, app, client, db_session):
        """Test role_required decorator with inactive user."""
        # Create inactive user
        inactive_user = User(
            email='inactive@test.com',
            full_name='Inactive User',
            role='Engineer',
            status='Disabled'
        )
        inactive_user.set_password('password123')
        db_session.add(inactive_user)
        db_session.commit()
        
        @app.route('/test-role-required')
        @role_required(['Engineer'])
        def test_view():
            return 'role success'
        
        with patch('auth.session_manager') as mock_session_manager:
            mock_session_manager.is_session_valid.return_value = True
            
            with client.session_transaction() as sess:
                sess['user_id'] = inactive_user.id
                sess['_fresh'] = True
            
            with patch('auth.current_user', inactive_user):
                response = client.get('/test-role-required')
                assert response.status_code == 302  # Redirect due to inactive status


class TestUserLoader:
    """Test cases for the user loader function."""
    
    def test_load_user_valid_session(self, app, db_session, admin_user):
        """Test loading user with valid session."""
        from auth import load_user
        
        with app.test_request_context():
            with patch('auth.session_manager') as mock_session_manager:
                mock_session_manager.is_session_valid.return_value = True
                mock_session_manager.is_session_revoked.return_value = False
                
                with patch('auth.session', {'session_id': 'valid-session', 'user_id': admin_user.id}):
                    user = load_user(str(admin_user.id))
                    assert user is not None
                    assert user.id == admin_user.id
                    assert user.email == admin_user.email
    
    def test_load_user_invalid_session(self, app, db_session, admin_user):
        """Test loading user with invalid session."""
        from auth import load_user
        
        with app.test_request_context():
            with patch('auth.session_manager') as mock_session_manager:
                mock_session_manager.is_session_valid.return_value = False
                
                user = load_user(str(admin_user.id))
                assert user is None
    
    def test_load_user_revoked_session(self, app, db_session, admin_user):
        """Test loading user with revoked session."""
        from auth import load_user
        
        with app.test_request_context():
            with patch('auth.session_manager') as mock_session_manager:
                mock_session_manager.is_session_valid.return_value = True
                mock_session_manager.is_session_revoked.return_value = True
                
                with patch('auth.session', {'session_id': 'revoked-session', 'user_id': admin_user.id}):
                    user = load_user(str(admin_user.id))
                    assert user is None
    
    def test_load_user_no_session_id(self, app, db_session, admin_user):
        """Test loading user without session ID."""
        from auth import load_user
        
        with app.test_request_context():
            with patch('auth.session_manager') as mock_session_manager:
                mock_session_manager.is_session_valid.return_value = True
                
                with patch('auth.session', {'user_id': admin_user.id}):  # No session_id
                    user = load_user(str(admin_user.id))
                    assert user is None
    
    def test_load_user_mismatched_user_id(self, app, db_session, admin_user):
        """Test loading user with mismatched user ID in session."""
        from auth import load_user
        
        with app.test_request_context():
            with patch('auth.session_manager') as mock_session_manager:
                mock_session_manager.is_session_valid.return_value = True
                mock_session_manager.is_session_revoked.return_value = False
                
                with patch('auth.session', {'session_id': 'valid-session', 'user_id': 999}):  # Different user_id
                    user = load_user(str(admin_user.id))
                    assert user is None
    
    def test_load_user_nonexistent_user(self, app, db_session):
        """Test loading non-existent user."""
        from auth import load_user
        
        with app.test_request_context():
            with patch('auth.session_manager') as mock_session_manager:
                mock_session_manager.is_session_valid.return_value = True
                mock_session_manager.is_session_revoked.return_value = False
                
                with patch('auth.session', {'session_id': 'valid-session', 'user_id': 999}):
                    user = load_user('999')
                    assert user is None


class TestAuthInitialization:
    """Test cases for auth initialization."""
    
    def test_init_auth(self, app):
        """Test auth initialization with app."""
        from auth import init_auth, login_manager
        
        # Initialize auth
        init_auth(app)
        
        # Verify login manager is configured
        assert login_manager.login_view == 'auth.login'
        assert login_manager.login_message == 'Please log in to access this page.'
        assert login_manager.login_message_category == 'info'