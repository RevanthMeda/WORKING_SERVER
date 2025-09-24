"""
Production security middleware for domain-only access
"""

from flask import request, abort, current_app
from functools import wraps
import ipaddress
import re

def domain_security_middleware():
    """
    Middleware to block direct IP access and enforce domain-only access
    """
    # Get configuration
    allowed_domains = current_app.config.get('ALLOWED_DOMAINS', [])
    server_ip = current_app.config.get('SERVER_IP', '')
    block_ip_access = current_app.config.get('BLOCK_IP_ACCESS', False)
    
    # Skip security for development environment (Replit domains)
    host = request.headers.get('Host', '').lower()
    if 'replit.dev' in host or 'repl.co' in host:
        return  # Allow Replit development domains
    
    if not block_ip_access:
        return  # Skip if not in production or blocking disabled
    
    # Remove port from host if present
    host_without_port = host.split(':')[0]
    
    # Check if accessing via IP address
    try:
        ipaddress.ip_address(host_without_port)
        # This is an IP address access - allow internal server IP, block others
        server_ip = current_app.config.get('SERVER_IP', '')
        if host_without_port == server_ip or host_without_port in ['127.0.0.1', 'localhost']:
            return  # Allow internal server IP and localhost
        else:
            current_app.logger.warning(f"Blocked external IP access attempt: {host} from {request.remote_addr}")
            abort(403)  # Forbidden
    except ValueError:
        # This is a domain name, check if it's allowed
        pass
    
    # Check if domain is in allowed list
    if allowed_domains and host_without_port not in allowed_domains:
        current_app.logger.warning(f"Blocked unauthorized domain access: {host} from {request.remote_addr}")
        abort(403)  # Forbidden
    
    # Additional security: Check for common attack patterns
    user_agent = request.headers.get('User-Agent', '').lower()
    suspicious_patterns = [
        'scanner', 'bot', 'crawler', 'spider', 
        'masscan', 'nmap', 'zmap', 'sqlmap'
    ]
    
    for pattern in suspicious_patterns:
        if pattern in user_agent:
            current_app.logger.warning(f"Blocked suspicious user agent: {user_agent} from {request.remote_addr}")
            abort(403)

def require_domain_access(f):
    """
    Decorator to enforce domain-only access for specific routes
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        domain_security_middleware()
        return f(*args, **kwargs)
    return decorated_function

def init_security_middleware(app):
    """
    Initialize security middleware for the Flask app
    """
    @app.before_request
    def before_request():
        # Skip security checks for health endpoint and static files
        if request.endpoint in ['health_check', 'static']:
            return
            
        # Skip security for development environment
        host = request.headers.get('Host', '').lower()
        if 'replit.dev' in host or 'repl.co' in host:
            return  # Allow Replit development domains
            
        # Apply domain security based on configuration
        if current_app.config.get('BLOCK_IP_ACCESS', False):
            domain_security_middleware()
        
        # Additional production security headers
        @app.after_request
        def security_headers(response):
            # Security headers for production
            response.headers['X-Content-Type-Options'] = 'nosniff'
            
            # Conditional X-Frame-Options for iframe support
            if current_app.config.get('BLOCK_IP_ACCESS', True):
                response.headers['X-Frame-Options'] = 'DENY'  # Block iframes for secure mode
            else:
                response.headers['X-Frame-Options'] = 'SAMEORIGIN'  # Allow same-origin iframes
            
            response.headers['X-XSS-Protection'] = '1; mode=block'
            
            # Only set HSTS if using HTTPS
            if request.is_secure:
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            # Flexible CSP for iframe embedding
            if current_app.config.get('BLOCK_IP_ACCESS', True):
                # Strict CSP for secure mode
                response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' fonts.googleapis.com cdnjs.cloudflare.com; font-src 'self' fonts.gstatic.com; img-src 'self' data:;"
            else:
                # Permissive CSP for iframe embedding
                response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' fonts.googleapis.com cdnjs.cloudflare.com; font-src 'self' fonts.gstatic.com; img-src 'self' data:; frame-ancestors *;"
            
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            
            return response