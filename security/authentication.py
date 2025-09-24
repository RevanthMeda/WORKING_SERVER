"""
Enhanced authentication and security utilities for SAT Report Generator API.
"""
import jwt
import pyotp
import qrcode
import io
import base64
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, current_app, session, g
from flask_login import current_user
from werkzeug.security import check_password_hash
from models import User, db


class SessionManager:
    """Enhanced session management."""
    
    @staticmethod
    def create_session(user_id, remember_me=False):
        """Create a new session."""
        session_id = secrets.token_urlsafe(32)
        session['session_id'] = session_id
        session['user_id'] = user_id
        session['created_at'] = time.time()
        session['last_activity'] = time.time()
        
        if remember_me:
            session.permanent = True
        
        return session_id
    
    @staticmethod
    def destroy_session():
        """Destroy current session."""
        session.clear()
    
    @staticmethod
    def is_session_valid():
        """Check if current session is valid."""
        if 'session_id' not in session:
            return False
        
        # Check session timeout (24 hours)
        last_activity = session.get('last_activity', 0)
        if time.time() - last_activity > 86400:  # 24 hours
            return False
        
        # Update last activity
        session['last_activity'] = time.time()
        return True


class JWTManager:
    """JWT token management."""
    
    @staticmethod
    def generate_token(user_id, expires_in=3600):
        """Generate JWT access token."""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        
        return jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
    
    @staticmethod
    def verify_token(token):
        """Verify JWT token."""
        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def get_user_from_token(token):
        """Get user from JWT token."""
        payload = JWTManager.verify_token(token)
        if not payload:
            return None
        
        user_id = payload.get('user_id')
        return User.query.get(user_id)


class MFAManager:
    """Multi-Factor Authentication management."""
    
    @staticmethod
    def generate_secret():
        """Generate TOTP secret."""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_qr_code_url(secret, email):
        """Generate QR code URL for authenticator app."""
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=email,
            issuer_name="SAT Report Generator"
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    @staticmethod
    def verify_totp(secret, token):
        """Verify TOTP token."""
        if not secret or not token:
            return False
        
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)
    
    @staticmethod
    def generate_backup_codes(count=10):
        """Generate backup codes."""
        codes = []
        for _ in range(count):
            code = secrets.token_hex(4).upper()
            codes.append(f"{code[:4]}-{code[4:]}")
        return codes
    
    @staticmethod
    def hash_backup_codes(codes):
        """Hash backup codes for storage."""
        hashed_codes = []
        for code in codes:
            hashed = hashlib.sha256(code.encode()).hexdigest()
            hashed_codes.append(hashed)
        return hashed_codes


class RateLimiter:
    """Rate limiting utilities."""
    
    def __init__(self):
        self.attempts = {}
    
    def is_rate_limited(self, identifier, max_attempts, window):
        """Check if identifier is rate limited."""
        now = time.time()
        
        if identifier not in self.attempts:
            return False
        
        # Clean old attempts
        self.attempts[identifier] = [
            attempt_time for attempt_time in self.attempts[identifier]
            if now - attempt_time < window
        ]
        
        return len(self.attempts[identifier]) >= max_attempts
    
    def record_attempt(self, identifier):
        """Record an attempt."""
        now = time.time()
        
        if identifier not in self.attempts:
            self.attempts[identifier] = []
        
        self.attempts[identifier].append(now)
    
    def reset_attempts(self, identifier):
        """Reset attempts for identifier."""
        if identifier in self.attempts:
            del self.attempts[identifier]


class PasswordPolicy:
    """Password policy enforcement."""
    
    MIN_LENGTH = 12
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL = True
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    @staticmethod
    def validate_password(password, username=None, email=None):
        """Validate password against policy."""
        errors = []
        
        if len(password) < PasswordPolicy.MIN_LENGTH:
            errors.append(f"Password must be at least {PasswordPolicy.MIN_LENGTH} characters long")
        
        if PasswordPolicy.REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if PasswordPolicy.REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if PasswordPolicy.REQUIRE_DIGITS and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if PasswordPolicy.REQUIRE_SPECIAL and not any(c in PasswordPolicy.SPECIAL_CHARS for c in password):
            errors.append("Password must contain at least one special character")
        
        # Check for common patterns
        if username and username.lower() in password.lower():
            errors.append("Password must not contain username")
        
        if email and email.split('@')[0].lower() in password.lower():
            errors.append("Password must not contain email prefix")
        
        # Check for common weak passwords
        weak_passwords = [
            'password', '123456', 'qwerty', 'admin', 'letmein',
            'welcome', 'monkey', '1234567890', 'password123'
        ]
        
        if password.lower() in weak_passwords:
            errors.append("Password is too common")
        
        return len(errors) == 0, errors


# Global instances
rate_limiter = RateLimiter()


def enhanced_login_required(f):
    """Enhanced login required decorator for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for JWT token in Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            user = JWTManager.get_user_from_token(token)
            
            if user and user.is_active:
                g.current_user = user
                return f(*args, **kwargs)
        
        # Fallback to session-based authentication
        if current_user.is_authenticated and current_user.is_active:
            if SessionManager.is_session_valid():
                g.current_user = current_user
                return f(*args, **kwargs)
        
        return jsonify({'message': 'Authentication required'}), 401
    
    return decorated_function


def api_key_required(f):
    """API key authentication decorator."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            return jsonify({'message': 'API key required'}), 401
        
        # Validate API key (implement your API key validation logic)
        # For now, just check if it's not empty
        if not api_key:
            return jsonify({'message': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


def role_required_api(allowed_roles):
    """Role-based access control for API endpoints."""
    def decorator(f):
        @wraps(f)
        @enhanced_login_required
        def decorated_function(*args, **kwargs):
            user = getattr(g, 'current_user', current_user)
            
            if user.role not in allowed_roles:
                return jsonify({'message': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator