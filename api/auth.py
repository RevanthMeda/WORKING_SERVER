"""
Authentication API endpoints.
"""
from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash
from marshmallow import ValidationError

from models import User, db
from security.authentication import (
    SessionManager, JWTManager, MFAManager, 
    rate_limiter, PasswordPolicy
)
from security.validation import (
    UserRegistrationSchema, validate_request_data,
    rate_limit_check, csrf_protect
)
from security.audit import get_audit_logger, AuditEventType, AuditSeverity
from monitoring.logging_config import audit_logger as app_logger

# Create namespace
auth_ns = Namespace('auth', description='Authentication operations')

# Request/Response models
login_model = auth_ns.model('Login', {
    'email': fields.String(required=True, description='User email address'),
    'password': fields.String(required=True, description='User password'),
    'remember_me': fields.Boolean(default=False, description='Remember login session'),
    'mfa_token': fields.String(description='MFA token (if MFA is enabled)')
})

register_model = auth_ns.model('Register', {
    'full_name': fields.String(required=True, description='Full name'),
    'email': fields.String(required=True, description='Email address'),
    'password': fields.String(required=True, description='Password'),
    'requested_role': fields.String(required=True, description='Requested role', 
                                   enum=['Engineer', 'Admin', 'PM', 'Automation Manager'])
})

token_response_model = auth_ns.model('TokenResponse', {
    'access_token': fields.String(description='JWT access token'),
    'token_type': fields.String(description='Token type (Bearer)'),
    'expires_in': fields.Integer(description='Token expiration time in seconds'),
    'user': fields.Raw(description='User information')
})

mfa_setup_model = auth_ns.model('MFASetup', {
    'secret': fields.String(description='TOTP secret'),
    'qr_code_url': fields.String(description='QR code URL for authenticator app'),
    'backup_codes': fields.List(fields.String, description='Backup codes')
})

mfa_verify_model = auth_ns.model('MFAVerify', {
    'token': fields.String(required=True, description='TOTP token from authenticator app')
})

password_change_model = auth_ns.model('PasswordChange', {
    'current_password': fields.String(required=True, description='Current password'),
    'new_password': fields.String(required=True, description='New password')
})


@auth_ns.route('/login')
class LoginResource(Resource):
    """User login endpoint."""
    
    @auth_ns.expect(login_model)
    @auth_ns.marshal_with(token_response_model)
    @rate_limit_check(max_requests=5, window=300)  # 5 attempts per 5 minutes
    def post(self):
        """Authenticate user and return access token."""
        data = request.get_json()
        
        # Rate limiting check
        identifier = request.remote_addr
        if rate_limiter.is_rate_limited(identifier, 5, 300):
            get_audit_logger().log_authentication_event(
                AuditEventType.LOGIN_FAILURE,
                details={'reason': 'rate_limited', 'ip': request.remote_addr}
            )
            return {'message': 'Too many login attempts. Please try again later.'}, 429
        
        # Validate input
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        remember_me = data.get('remember_me', False)
        mfa_token = data.get('mfa_token')
        
        if not email or not password:
            rate_limiter.record_attempt(identifier)
            return {'message': 'Email and password are required'}, 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            rate_limiter.record_attempt(identifier)
            get_audit_logger().log_authentication_event(
                AuditEventType.LOGIN_FAILURE,
                user_id=user.id if user else None,
                success=False,
                details={'reason': 'invalid_credentials', 'email': email}
            )
            return {'message': 'Invalid email or password'}, 401
        
        # Check if user is active
        if not user.is_active:
            rate_limiter.record_attempt(identifier)
            get_audit_logger().log_authentication_event(
                AuditEventType.LOGIN_FAILURE,
                user_id=user.id,
                success=False,
                details={'reason': 'account_disabled'}
            )
            return {'message': 'Account is disabled'}, 401
        
        # Check MFA if enabled
        if user.mfa_enabled:
            if not mfa_token:
                return {'message': 'MFA token required', 'mfa_required': True}, 200
            
            if not MFAManager.verify_totp(user.mfa_secret, mfa_token):
                rate_limiter.record_attempt(identifier)
                get_audit_logger().log_authentication_event(
                    AuditEventType.LOGIN_FAILURE,
                    user_id=user.id,
                    success=False,
                    details={'reason': 'invalid_mfa_token'}
                )
                return {'message': 'Invalid MFA token'}, 401
        
        # Successful login
        rate_limiter.reset_attempts(identifier)
        
        # Create session
        session_id = SessionManager.create_session(user.id, remember_me)
        
        # Generate JWT token
        access_token = JWTManager.generate_token(user.id)
        
        # Log successful login
        get_audit_logger().log_authentication_event(
            AuditEventType.LOGIN_SUCCESS,
            user_id=user.id,
            success=True,
            details={'session_id': session_id}
        )
        
        # Update last login
        user.last_login = db.func.now()
        db.session.commit()
        
        return {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': 3600,
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'mfa_enabled': user.mfa_enabled
            }
        }, 200


@auth_ns.route('/logout')
class LogoutResource(Resource):
    """User logout endpoint."""
    
    def post(self):
        """Logout user and invalidate session."""
        user_id = current_user.id if current_user.is_authenticated else None
        
        # Destroy session
        SessionManager.destroy_session()
        
        # Log logout
        get_audit_logger().log_authentication_event(
            AuditEventType.LOGOUT,
            user_id=user_id,
            success=True
        )
        
        return {'message': 'Successfully logged out'}, 200


@auth_ns.route('/register')
class RegisterResource(Resource):
    """User registration endpoint."""
    
    @auth_ns.expect(register_model)
    @validate_request_data(UserRegistrationSchema)
    @rate_limit_check(max_requests=3, window=3600)  # 3 registrations per hour
    def post(self):
        """Register new user account."""
        data = request.validated_data
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email']).first()
        if existing_user:
            return {'message': 'User with this email already exists'}, 409
        
        # Create new user
        user = User(
            full_name=data['full_name'],
            email=data['email'],
            role=data['requested_role'],
            is_active=False,  # Require admin approval
            is_approved=False
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Log registration
        get_audit_logger().log_authentication_event(
            AuditEventType.LOGIN_SUCCESS,  # Using closest available event
            user_id=user.id,
            success=True,
            details={'action': 'user_registration', 'role_requested': data['requested_role']}
        )
        
        return {
            'message': 'Registration successful. Account pending approval.',
            'user_id': user.id
        }, 201


@auth_ns.route('/mfa/setup')
class MFASetupResource(Resource):
    """MFA setup endpoint."""
    
    @auth_ns.marshal_with(mfa_setup_model)
    def post(self):
        """Set up MFA for current user."""
        if not current_user.is_authenticated:
            return {'message': 'Authentication required'}, 401
        
        # Generate MFA secret
        secret = MFAManager.generate_secret()
        qr_code_url = MFAManager.generate_qr_code_url(secret, current_user.email)
        backup_codes = MFAManager.generate_backup_codes()
        
        # Store secret temporarily (user needs to verify before enabling)
        current_user.mfa_secret_temp = secret
        current_user.mfa_backup_codes = MFAManager.hash_backup_codes(backup_codes)
        db.session.commit()
        
        return {
            'secret': secret,
            'qr_code_url': qr_code_url,
            'backup_codes': backup_codes
        }, 200


@auth_ns.route('/mfa/verify')
class MFAVerifyResource(Resource):
    """MFA verification endpoint."""
    
    @auth_ns.expect(mfa_verify_model)
    def post(self):
        """Verify MFA token and enable MFA."""
        if not current_user.is_authenticated:
            return {'message': 'Authentication required'}, 401
        
        data = request.get_json()
        token = data.get('token')
        
        if not token:
            return {'message': 'MFA token is required'}, 400
        
        # Verify token with temporary secret
        if not current_user.mfa_secret_temp:
            return {'message': 'MFA setup not initiated'}, 400
        
        if not MFAManager.verify_totp(current_user.mfa_secret_temp, token):
            return {'message': 'Invalid MFA token'}, 400
        
        # Enable MFA
        current_user.mfa_enabled = True
        current_user.mfa_secret = current_user.mfa_secret_temp
        current_user.mfa_secret_temp = None
        db.session.commit()
        
        # Log MFA enabled
        get_audit_logger().log_authentication_event(
            AuditEventType.LOGIN_SUCCESS,  # Using closest available event
            user_id=current_user.id,
            success=True,
            details={'action': 'mfa_enabled'}
        )
        
        return {'message': 'MFA successfully enabled'}, 200


@auth_ns.route('/mfa/disable')
class MFADisableResource(Resource):
    """MFA disable endpoint."""
    
    @auth_ns.expect(mfa_verify_model)
    def post(self):
        """Disable MFA for current user."""
        if not current_user.is_authenticated:
            return {'message': 'Authentication required'}, 401
        
        data = request.get_json()
        token = data.get('token')
        
        if not current_user.mfa_enabled:
            return {'message': 'MFA is not enabled'}, 400
        
        if not token:
            return {'message': 'MFA token is required'}, 400
        
        # Verify current MFA token
        if not MFAManager.verify_totp(current_user.mfa_secret, token):
            return {'message': 'Invalid MFA token'}, 400
        
        # Disable MFA
        current_user.mfa_enabled = False
        current_user.mfa_secret = None
        current_user.mfa_backup_codes = None
        db.session.commit()
        
        # Log MFA disabled
        get_audit_logger().log_authentication_event(
            AuditEventType.LOGIN_SUCCESS,  # Using closest available event
            user_id=current_user.id,
            success=True,
            details={'action': 'mfa_disabled'}
        )
        
        return {'message': 'MFA successfully disabled'}, 200


@auth_ns.route('/password/change')
class PasswordChangeResource(Resource):
    """Password change endpoint."""
    
    @auth_ns.expect(password_change_model)
    def post(self):
        """Change user password."""
        if not current_user.is_authenticated:
            return {'message': 'Authentication required'}, 401
        
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return {'message': 'Current and new passwords are required'}, 400
        
        # Verify current password
        if not check_password_hash(current_user.password_hash, current_password):
            get_audit_logger().log_authentication_event(
                AuditEventType.PASSWORD_CHANGE,
                user_id=current_user.id,
                success=False,
                details={'reason': 'invalid_current_password'}
            )
            return {'message': 'Current password is incorrect'}, 400
        
        # Validate new password
        is_valid, errors = PasswordPolicy.validate_password(
            new_password, 
            username=current_user.email.split('@')[0],
            email=current_user.email
        )
        
        if not is_valid:
            return {'message': 'Password validation failed', 'errors': errors}, 400
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        # Log password change
        get_audit_logger().log_authentication_event(
            AuditEventType.PASSWORD_CHANGE,
            user_id=current_user.id,
            success=True
        )
        
        return {'message': 'Password successfully changed'}, 200


@auth_ns.route('/token/refresh')
class TokenRefreshResource(Resource):
    """Token refresh endpoint."""
    
    @auth_ns.marshal_with(token_response_model)
    def post(self):
        """Refresh JWT access token."""
        # Get current token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return {'message': 'Bearer token required'}, 401
        
        token = auth_header.split(' ')[1]
        
        # Verify current token
        payload = JWTManager.verify_token(token)
        if not payload:
            return {'message': 'Invalid or expired token'}, 401
        
        user_id = payload.get('user_id')
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            return {'message': 'User not found or inactive'}, 401
        
        # Generate new token
        new_token = JWTManager.generate_token(user_id)
        
        return {
            'access_token': new_token,
            'token_type': 'Bearer',
            'expires_in': 3600,
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'mfa_enabled': user.mfa_enabled
            }
        }, 200
