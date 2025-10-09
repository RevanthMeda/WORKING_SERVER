"""
API security, rate limiting, and usage analytics.
"""
import time
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict, deque
from flask import request, jsonify, current_app, g
from flask_login import current_user
from models import db, User
from security.audit import get_audit_logger, AuditEventType, AuditSeverity


class APIKey(db.Model):
    """API Key model for external integrations."""
    
    __tablename__ = 'api_keys'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(secrets.token_urlsafe(16)))
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    key_hash = db.Column(db.String(64), nullable=False, unique=True)  # SHA-256 hash
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    permissions = db.Column(db.JSON, default=list)  # List of permissions
    rate_limit = db.Column(db.Integer, default=1000)  # Requests per hour
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship(
        'User',
        backref=db.backref('api_keys', cascade='all, delete-orphan', passive_deletes=True)
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = str(secrets.token_urlsafe(16))
    
    @staticmethod
    def generate_key():
        """Generate a new API key."""
        return f"sk_{'live' if current_app.config.get('ENV') == 'production' else 'test'}_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def hash_key(key):
        """Hash an API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def verify_key(self, key):
        """Verify an API key against the stored hash."""
        return self.key_hash == self.hash_key(key)
    
    def has_permission(self, permission):
        """Check if API key has a specific permission."""
        return permission in (self.permissions or [])
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'permissions': self.permissions,
            'rate_limit': self.rate_limit,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }


class APIUsage(db.Model):
    """API usage tracking for analytics and rate limiting."""
    
    __tablename__ = 'api_usage'
    
    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.String(36), db.ForeignKey('api_keys.id', ondelete='SET NULL'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    endpoint = db.Column(db.String(200), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer)
    response_time = db.Column(db.Float)  # Response time in seconds
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    api_key = db.relationship('APIKey', backref='usage_records')
    user = db.relationship('User', backref='api_usage_records')


class RateLimiter:
    """Advanced rate limiting with multiple strategies."""
    
    def __init__(self):
        # In-memory storage for rate limiting (use Redis in production)
        self.requests = defaultdict(deque)
        self.blocked_ips = {}
        
        # Rate limiting configurations
        self.limits = {
            'anonymous': {'requests': 100, 'window': 3600},  # 100 per hour
            'authenticated': {'requests': 1000, 'window': 3600},  # 1000 per hour
            'api_key': {'requests': 5000, 'window': 3600},  # 5000 per hour (default)
            'admin': {'requests': 10000, 'window': 3600},  # 10000 per hour
        }
    
    def get_identifier(self):
        """Get unique identifier for rate limiting."""
        # Priority: API Key > User ID > IP Address
        api_key = request.headers.get('X-API-Key')
        if api_key:
            return f"api_key:{api_key}"
        
        if current_user.is_authenticated:
            return f"user:{current_user.id}"
        
        return f"ip:{request.remote_addr}"
    
    def get_rate_limit_config(self, identifier):
        """Get rate limit configuration for identifier."""
        if identifier.startswith('api_key:'):
            # Check if API key has custom rate limit
            api_key_value = identifier.split(':', 1)[1]
            api_key = APIKey.query.filter_by(key_hash=APIKey.hash_key(api_key_value)).first()
            if api_key:
                return {'requests': api_key.rate_limit, 'window': 3600}
            return self.limits['api_key']
        
        elif identifier.startswith('user:'):
            if current_user.is_authenticated and current_user.role == 'Admin':
                return self.limits['admin']
            return self.limits['authenticated']
        
        else:  # IP-based
            return self.limits['anonymous']
    
    def is_rate_limited(self, identifier=None):
        """Check if request should be rate limited."""
        if identifier is None:
            identifier = self.get_identifier()
        
        # Check if IP is blocked
        ip = request.remote_addr
        if ip in self.blocked_ips:
            if time.time() < self.blocked_ips[ip]:
                return True
            else:
                del self.blocked_ips[ip]
        
        config = self.get_rate_limit_config(identifier)
        window = config['window']
        limit = config['requests']
        
        now = time.time()
        
        # Clean old requests
        while self.requests[identifier] and self.requests[identifier][0] < now - window:
            self.requests[identifier].popleft()
        
        # Check if limit exceeded
        if len(self.requests[identifier]) >= limit:
            # Block IP for repeated violations
            if len(self.requests[identifier]) > limit * 2:
                self.blocked_ips[ip] = now + 3600  # Block for 1 hour
            
            return True
        
        return False
    
    def record_request(self, identifier=None):
        """Record a request for rate limiting."""
        if identifier is None:
            identifier = self.get_identifier()
        
        self.requests[identifier].append(time.time())
    
    def get_rate_limit_status(self, identifier=None):
        """Get current rate limit status."""
        if identifier is None:
            identifier = self.get_identifier()
        
        config = self.get_rate_limit_config(identifier)
        window = config['window']
        limit = config['requests']
        
        now = time.time()
        
        # Clean old requests
        while self.requests[identifier] and self.requests[identifier][0] < now - window:
            self.requests[identifier].popleft()
        
        current_requests = len(self.requests[identifier])
        remaining = max(0, limit - current_requests)
        
        # Calculate reset time
        if self.requests[identifier]:
            reset_time = int(self.requests[identifier][0] + window)
        else:
            reset_time = int(now + window)
        
        return {
            'limit': limit,
            'remaining': remaining,
            'reset': reset_time,
            'window': window
        }


class JWTManager:
    """Enhanced JWT token management."""
    
    @staticmethod
    def generate_token(user_id, expires_in=3600, token_type='access'):
        """Generate JWT token with enhanced claims."""
        now = datetime.utcnow()
        payload = {
            'user_id': user_id,
            'type': token_type,
            'iat': now,
            'exp': now + timedelta(seconds=expires_in),
            'jti': secrets.token_urlsafe(16),  # JWT ID for revocation
            'iss': 'sat-report-generator',  # Issuer
            'aud': 'sat-report-generator-api',  # Audience
        }
        
        # Add user role and permissions
        user = User.query.get(user_id)
        if user:
            payload['role'] = user.role
            payload['permissions'] = user.get_permissions()  # Implement this method
        
        return jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
    
    @staticmethod
    def verify_token(token):
        """Verify JWT token with enhanced validation."""
        try:
            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256'],
                audience='sat-report-generator-api',
                issuer='sat-report-generator'
            )
            
            # Check if token is revoked (implement token blacklist)
            jti = payload.get('jti')
            if JWTManager.is_token_revoked(jti):
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            get_audit_logger().log_security_event(
                'token_expired',
                severity='low',
                details={'token_type': 'jwt'}
            )
            return None
        except jwt.InvalidTokenError as e:
            get_audit_logger().log_security_event(
                'invalid_token',
                severity='medium',
                details={'error': str(e), 'token_type': 'jwt'}
            )
            return None
    
    @staticmethod
    def is_token_revoked(jti):
        """Check if token is revoked (implement with Redis/database)."""
        # TODO: Implement token blacklist
        return False
    
    @staticmethod
    def revoke_token(jti):
        """Revoke a token by adding to blacklist."""
        # TODO: Implement token revocation
        pass


class APISecurityManager:
    """Comprehensive API security management."""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.jwt_manager = JWTManager()
    
    def authenticate_request(self):
        """Authenticate API request using multiple methods."""
        # Try JWT Bearer token first
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            payload = self.jwt_manager.verify_token(token)
            
            if payload:
                user = User.query.get(payload['user_id'])
                if user and user.is_active:
                    g.current_user = user
                    g.auth_method = 'jwt'
                    return user
        
        # Try API Key authentication
        api_key = request.headers.get('X-API-Key')
        if api_key:
            api_key_record = APIKey.query.filter_by(
                key_hash=APIKey.hash_key(api_key),
                is_active=True
            ).first()
            
            if api_key_record:
                # Check expiration
                if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
                    get_audit_logger().log_security_event(
                        'expired_api_key',
                        severity='medium',
                        details={'api_key_id': api_key_record.id}
                    )
                    return None
                
                # Update last used
                api_key_record.last_used = datetime.utcnow()
                db.session.commit()
                
                g.current_user = api_key_record.user
                g.api_key = api_key_record
                g.auth_method = 'api_key'
                return api_key_record.user
        
        # Try session-based authentication (fallback)
        if current_user.is_authenticated:
            g.current_user = current_user
            g.auth_method = 'session'
            return current_user
        
        return None
    
    def check_permissions(self, required_permissions):
        """Check if current user/API key has required permissions."""
        if not hasattr(g, 'current_user') or not g.current_user:
            return False
        
        if g.auth_method == 'api_key':
            api_key = g.api_key
            return all(api_key.has_permission(perm) for perm in required_permissions)
        
        # For JWT and session auth, check user role permissions
        user = g.current_user
        user_permissions = user.get_permissions()  # Implement this method
        return all(perm in user_permissions for perm in required_permissions)
    
    def log_api_usage(self, start_time, status_code):
        """Log API usage for analytics."""
        response_time = time.time() - start_time
        
        usage = APIUsage(
            api_key_id=getattr(g, 'api_key', None) and g.api_key.id,
            user_id=getattr(g, 'current_user', None) and g.current_user.id,
            endpoint=request.endpoint or request.path,
            method=request.method,
            status_code=status_code,
            response_time=response_time,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            timestamp=datetime.utcnow()
        )
        
        db.session.add(usage)
        db.session.commit()


# Global security manager instance
security_manager = APISecurityManager()


def require_auth(permissions=None):
    """Decorator to require authentication and optional permissions."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            
            # Check rate limiting first
            if security_manager.rate_limiter.is_rate_limited():
                get_audit_logger().log_security_event(
                    'rate_limit_exceeded',
                    severity='medium',
                    details={
                        'endpoint': request.endpoint,
                        'ip': request.remote_addr,
                        'identifier': security_manager.rate_limiter.get_identifier()
                    }
                )
                
                rate_status = security_manager.rate_limiter.get_rate_limit_status()
                response = jsonify({
                    'error': {
                        'message': 'Rate limit exceeded',
                        'code': 'RATE_LIMIT_EXCEEDED',
                        'retry_after': rate_status['reset'] - int(time.time())
                    }
                })
                response.status_code = 429
                response.headers['Retry-After'] = str(rate_status['reset'] - int(time.time()))
                response.headers['X-RateLimit-Limit'] = str(rate_status['limit'])
                response.headers['X-RateLimit-Remaining'] = str(rate_status['remaining'])
                response.headers['X-RateLimit-Reset'] = str(rate_status['reset'])
                return response
            
            # Record request for rate limiting
            security_manager.rate_limiter.record_request()
            
            # Authenticate request
            user = security_manager.authenticate_request()
            if not user:
                get_audit_logger().log_security_event(
                    'unauthorized_access',
                    severity='medium',
                    details={
                        'endpoint': request.endpoint,
                        'ip': request.remote_addr,
                        'user_agent': request.headers.get('User-Agent')
                    }
                )
                
                return jsonify({
                    'error': {
                        'message': 'Authentication required',
                        'code': 'AUTHENTICATION_REQUIRED'
                    }
                }), 401
            
            # Check permissions if specified
            if permissions and not security_manager.check_permissions(permissions):
                get_audit_logger().log_security_event(
                    'insufficient_permissions',
                    severity='medium',
                    user_id=user.id,
                    details={
                        'endpoint': request.endpoint,
                        'required_permissions': permissions,
                        'auth_method': g.auth_method
                    }
                )
                
                return jsonify({
                    'error': {
                        'message': 'Insufficient permissions',
                        'code': 'INSUFFICIENT_PERMISSIONS',
                        'required_permissions': permissions
                    }
                }), 403
            
            # Execute the function
            try:
                result = f(*args, **kwargs)
                
                # Log successful API usage
                status_code = 200
                if isinstance(result, tuple) and len(result) > 1:
                    status_code = result[1]
                
                security_manager.log_api_usage(start_time, status_code)
                
                # Add rate limit headers to response
                rate_status = security_manager.rate_limiter.get_rate_limit_status()
                if isinstance(result, tuple):
                    response_data, status_code = result[0], result[1]
                    response = jsonify(response_data)
                    response.status_code = status_code
                else:
                    response = jsonify(result)
                
                response.headers['X-RateLimit-Limit'] = str(rate_status['limit'])
                response.headers['X-RateLimit-Remaining'] = str(rate_status['remaining'])
                response.headers['X-RateLimit-Reset'] = str(rate_status['reset'])
                
                return response
                
            except Exception as e:
                # Log failed API usage
                security_manager.log_api_usage(start_time, 500)
                raise
        
        return decorated_function
    return decorator


def require_api_key(permissions=None):
    """Decorator to specifically require API key authentication."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = request.headers.get('X-API-Key')
            if not api_key:
                return jsonify({
                    'error': {
                        'message': 'API key required',
                        'code': 'API_KEY_REQUIRED'
                    }
                }), 401
            
            api_key_record = APIKey.query.filter_by(
                key_hash=APIKey.hash_key(api_key),
                is_active=True
            ).first()
            
            if not api_key_record:
                get_audit_logger().log_security_event(
                    'invalid_api_key',
                    severity='high',
                    details={
                        'endpoint': request.endpoint,
                        'ip': request.remote_addr
                    }
                )
                
                return jsonify({
                    'error': {
                        'message': 'Invalid API key',
                        'code': 'INVALID_API_KEY'
                    }
                }), 401
            
            # Check permissions
            if permissions and not all(api_key_record.has_permission(perm) for perm in permissions):
                return jsonify({
                    'error': {
                        'message': 'API key lacks required permissions',
                        'code': 'INSUFFICIENT_API_PERMISSIONS',
                        'required_permissions': permissions
                    }
                }), 403
            
            g.api_key = api_key_record
            g.current_user = api_key_record.user
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def security_headers(f):
    """Add security headers to API responses."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        result = f(*args, **kwargs)
        
        if isinstance(result, tuple):
            response_data, status_code = result[0], result[1]
            response = jsonify(response_data)
            response.status_code = status_code
        else:
            response = jsonify(result)
        
        # Add security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Content-Security-Policy'] = "default-src 'none'"
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
    
    return decorated_function
