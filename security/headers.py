"""
Security headers and CSRF protection enhancements for SAT Report Generator.
"""
from flask import Flask, request, make_response, jsonify
from functools import wraps


class SecurityHeaders:
    """Security headers configuration and management."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize security headers for Flask app."""
        self.app = app
        
        # Register after_request handler
        app.after_request(self.add_security_headers)
        
        # Configure CSP policy
        self.csp_policy = self._build_csp_policy()
    
    def _build_csp_policy(self):
        """Build Content Security Policy."""
        policy_parts = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com",
            "img-src 'self' data: https:",
            "connect-src 'self'",
            "frame-src 'none'",
            "object-src 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "upgrade-insecure-requests"
        ]
        
        return "; ".join(policy_parts)
    
    def add_security_headers(self, response):
        """Add security headers to response."""
        # Content Security Policy
        response.headers['Content-Security-Policy'] = self.csp_policy
        
        # X-Content-Type-Options
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # X-Frame-Options
        response.headers['X-Frame-Options'] = 'DENY'
        
        # X-XSS-Protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Strict-Transport-Security (HSTS)
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        
        # Referrer Policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy (formerly Feature Policy)
        permissions_policy = [
            "geolocation=()",
            "microphone=()",
            "camera=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "speaker=()",
            "vibrate=()",
            "fullscreen=(self)",
            "sync-xhr=()"
        ]
        response.headers['Permissions-Policy'] = ", ".join(permissions_policy)
        
        # Cache Control for sensitive pages
        if request.endpoint and any(sensitive in request.endpoint for sensitive in ['auth', 'admin', 'report']):
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        # Remove server information
        response.headers.pop('Server', None)
        
        return response


class EnhancedCSRFProtection:
    """Enhanced CSRF protection with additional security measures."""
    
    def __init__(self, app: Flask = None):
        self.app = app
        self.token_lifetime = 3600  # 1 hour
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize CSRF protection for Flask app."""
        self.app = app
        
        # Add CSRF token to template context
        app.context_processor(self.inject_csrf_token)
    
    def inject_csrf_token(self):
        """Inject CSRF token into template context."""
        from security.validation import CSRFProtection
        return {'csrf_token': CSRFProtection.generate_csrf_token}
    
    def validate_csrf_token(self, token: str = None) -> bool:
        """Enhanced CSRF token validation."""
        from flask import session
        import time
        
        if not token:
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        
        if not token:
            return False
        
        stored_token = session.get('csrf_token')
        token_timestamp = session.get('csrf_token_timestamp', 0)
        
        if not stored_token:
            return False
        
        # Check token expiration
        if time.time() - token_timestamp > self.token_lifetime:
            session.pop('csrf_token', None)
            session.pop('csrf_token_timestamp', None)
            return False
        
        # Constant-time comparison
        return self._constant_time_compare(token, stored_token)
    
    def _constant_time_compare(self, a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        if len(a) != len(b):
            return False
        
        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)
        
        return result == 0


class RequestSizeLimit:
    """Request size limiting middleware."""
    
    def __init__(self, app: Flask = None, max_content_length: int = 16 * 1024 * 1024):
        self.max_content_length = max_content_length  # 16MB default
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize request size limiting."""
        app.config['MAX_CONTENT_LENGTH'] = self.max_content_length
        app.before_request(self.check_content_length)
    
    def check_content_length(self):
        """Check request content length."""
        if request.content_length and request.content_length > self.max_content_length:
            from monitoring.logging_config import audit_logger
            audit_logger.log_security_event(
                'request_too_large',
                severity='medium',
                details={
                    'content_length': request.content_length,
                    'max_allowed': self.max_content_length,
                    'endpoint': request.endpoint
                }
            )
            return jsonify({'error': 'Request entity too large'}), 413


class IPWhitelist:
    """IP address whitelisting for admin endpoints."""
    
    def __init__(self, app: Flask = None):
        self.whitelist = set()
        self.enabled = False
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize IP whitelisting."""
        self.whitelist = set(app.config.get('ADMIN_IP_WHITELIST', []))
        self.enabled = app.config.get('ENABLE_IP_WHITELIST', False)
    
    def add_ip(self, ip_address: str):
        """Add IP address to whitelist."""
        self.whitelist.add(ip_address)
    
    def remove_ip(self, ip_address: str):
        """Remove IP address from whitelist."""
        self.whitelist.discard(ip_address)
    
    def is_allowed(self, ip_address: str) -> bool:
        """Check if IP address is allowed."""
        if not self.enabled:
            return True
        
        return ip_address in self.whitelist
    
    def require_whitelisted_ip(self, f):
        """Decorator to require whitelisted IP."""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_allowed(request.remote_addr):
                from monitoring.logging_config import audit_logger
                audit_logger.log_security_event(
                    'ip_not_whitelisted',
                    severity='high',
                    details={
                        'ip_address': request.remote_addr,
                        'endpoint': request.endpoint
                    }
                )
                return jsonify({'error': 'Access denied'}), 403
            
            return f(*args, **kwargs)
        
        return decorated_function


class SecurityMiddleware:
    """Comprehensive security middleware."""
    
    def __init__(self, app: Flask = None):
        self.security_headers = SecurityHeaders()
        self.csrf_protection = EnhancedCSRFProtection()
        self.request_size_limit = RequestSizeLimit()
        self.ip_whitelist = IPWhitelist()
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app: Flask):
        """Initialize all security middleware."""
        self.security_headers.init_app(app)
        self.csrf_protection.init_app(app)
        self.request_size_limit.init_app(app)
        self.ip_whitelist.init_app(app)
        
        # Add security checks before request
        app.before_request(self.security_checks)
    
    def security_checks(self):
        """Perform security checks before processing request."""
        # Check for suspicious patterns in request
        self._check_suspicious_patterns()
        
        # Check for common attack vectors
        self._check_attack_vectors()
    
    def _check_suspicious_patterns(self):
        """Check for suspicious patterns in request."""
        suspicious_patterns = [
            r'<script[^>]*>.*?</script>',  # XSS attempts
            r'union\s+select',  # SQL injection
            r'drop\s+table',  # SQL injection
            r'exec\s*\(',  # Code injection
            r'eval\s*\(',  # Code injection
            r'\.\./',  # Path traversal
            r'%2e%2e%2f',  # Encoded path traversal
        ]
        
        # Check URL, headers, and form data
        check_data = [
            request.url,
            str(request.headers),
            str(request.form),
            str(request.args)
        ]
        
        import re
        for data in check_data:
            for pattern in suspicious_patterns:
                if re.search(pattern, data, re.IGNORECASE):
                    from monitoring.logging_config import audit_logger
                    audit_logger.log_security_event(
                        'suspicious_pattern_detected',
                        severity='high',
                        details={
                            'pattern': pattern,
                            'data': data[:200],  # Limit logged data
                            'endpoint': request.endpoint
                        }
                    )
                    return jsonify({'error': 'Suspicious request detected'}), 400
    
    def _check_attack_vectors(self):
        """Check for common attack vectors."""
        # Check for excessive header count
        if len(request.headers) > 50:
            from monitoring.logging_config import audit_logger
            audit_logger.log_security_event(
                'excessive_headers',
                severity='medium',
                details={
                    'header_count': len(request.headers),
                    'endpoint': request.endpoint
                }
            )
        
        # Check for suspicious user agents
        user_agent = request.headers.get('User-Agent', '').lower()
        suspicious_agents = [
            'sqlmap', 'nikto', 'nmap', 'masscan', 'zap', 'burp',
            'wget', 'curl', 'python-requests'  # May need to whitelist legitimate usage
        ]
        
        if any(agent in user_agent for agent in suspicious_agents):
            from monitoring.logging_config import audit_logger
            audit_logger.log_security_event(
                'suspicious_user_agent',
                severity='medium',
                details={
                    'user_agent': user_agent,
                    'endpoint': request.endpoint
                }
            )


# Decorators for enhanced security
def require_https(f):
    """Decorator to require HTTPS."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_secure and not current_app.debug:
            return jsonify({'error': 'HTTPS required'}), 400
        return f(*args, **kwargs)
    
    return decorated_function


def require_json(f):
    """Decorator to require JSON content type."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'error': 'JSON content type required'}), 400
        return f(*args, **kwargs)
    
    return decorated_function


def security_headers_only(f):
    """Decorator to add security headers to specific endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        
        # Add additional security headers for sensitive endpoints
        response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'
        response.headers['X-Download-Options'] = 'noopen'
        response.headers['X-DNS-Prefetch-Control'] = 'off'
        
        return response
    
    return decorated_function


# Global security middleware instance
security_middleware = SecurityMiddleware()