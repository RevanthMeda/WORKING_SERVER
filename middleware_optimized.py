"""
Optimized middleware for SAT Report Generator with caching and compression
"""
import gzip
import io
from functools import wraps
from flask import request, make_response, current_app
from werkzeug.datastructures import Headers
import hashlib
import time

class OptimizedMiddleware:
    """Middleware for performance optimization"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Pre-request optimizations"""
        # Record request start time for performance monitoring
        request._start_time = time.time()
    
    def after_request(self, response):
        """Post-request optimizations"""
        # Add performance headers
        if hasattr(request, '_start_time'):
            elapsed = time.time() - request._start_time
            response.headers['X-Response-Time'] = f'{elapsed:.3f}s'
        
        # Apply caching headers for static files
        if request.path.startswith('/static/'):
            self.add_static_cache_headers(response)
        
        # Apply gzip compression for text-based responses
        if self.should_compress(response):
            response = self.compress_response(response)
        
        # Add security headers
        self.add_security_headers(response)
        
        return response
    
    def add_static_cache_headers(self, response):
        """Add aggressive caching headers for static files"""
        # Determine cache duration based on file type
        path = request.path
        
        if path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.ico', '.svg')):
            # Images - cache for 1 year
            max_age = 31536000
        elif path.endswith(('.css', '.js')):
            # CSS and JS - cache for 1 month with revalidation
            max_age = 2592000
            # Only add ETag if response has data and not in passthrough mode
            try:
                if not response.direct_passthrough:
                    response.headers['ETag'] = self.generate_etag(response.get_data())
            except:
                pass  # Skip ETag if there's any issue
        elif path.endswith(('.woff', '.woff2', '.ttf', '.eot')):
            # Fonts - cache for 1 year
            max_age = 31536000
        else:
            # Other static files - cache for 1 week
            max_age = 604800
        
        response.headers['Cache-Control'] = f'public, max-age={max_age}, immutable'
        response.headers['Vary'] = 'Accept-Encoding'
    
    def should_compress(self, response):
        """Check if response should be compressed"""
        # Don't compress if already compressed
        if 'Content-Encoding' in response.headers:
            return False
        
        # Don't compress small responses (less than 500 bytes)
        if response.content_length and response.content_length < 500:
            return False
        
        # Don't compress non-text content
        content_type = response.headers.get('Content-Type', '')
        compressible_types = [
            'text/', 'application/json', 'application/javascript',
            'application/xml', 'application/x-javascript'
        ]
        
        if not any(ct in content_type for ct in compressible_types):
            return False
        
        # Check if client accepts gzip
        accept_encoding = request.headers.get('Accept-Encoding', '')
        return 'gzip' in accept_encoding.lower()
    
    def compress_response(self, response):
        """Compress response using gzip"""
        try:
            # Skip compression for direct passthrough responses
            if response.direct_passthrough:
                return response
            
            # Get response data
            data = response.get_data()
            
            # Compress data
            gzip_buffer = io.BytesIO()
            with gzip.GzipFile(mode='wb', fileobj=gzip_buffer, compresslevel=6) as gzip_file:
                gzip_file.write(data)
            
            compressed_data = gzip_buffer.getvalue()
            
            # Only use compression if it actually reduces size
            if len(compressed_data) < len(data):
                response.set_data(compressed_data)
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = len(compressed_data)
                response.headers['Vary'] = 'Accept-Encoding'
        except Exception as e:
            current_app.logger.error(f"Compression error: {e}")
        
        return response
    
    def add_security_headers(self, response):
        """Add security headers for better performance and security"""
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Prevent MIME sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # DNS prefetching
        response.headers['X-DNS-Prefetch-Control'] = 'on'
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
    
    def generate_etag(self, data):
        """Generate ETag for response data"""
        if isinstance(data, bytes):
            return hashlib.md5(data).hexdigest()
        else:
            return hashlib.md5(str(data).encode()).hexdigest()


def cache_control(max_age=0, public=False, private=True, no_cache=False, no_store=False):
    """Decorator to set cache control headers"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            response = make_response(f(*args, **kwargs))
            
            cache_parts = []
            
            if no_store:
                cache_parts.append('no-store')
            elif no_cache:
                cache_parts.append('no-cache')
            else:
                if public:
                    cache_parts.append('public')
                elif private:
                    cache_parts.append('private')
                
                if max_age > 0:
                    cache_parts.append(f'max-age={max_age}')
            
            response.headers['Cache-Control'] = ', '.join(cache_parts)
            
            return response
        return decorated_function
    return decorator


def etag(f):
    """Decorator to add ETag support to responses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        
        # Generate ETag
        response_data = response.get_data()
        etag_value = hashlib.md5(response_data).hexdigest()
        response.headers['ETag'] = f'"{etag_value}"'
        
        # Check if client has matching ETag
        client_etag = request.headers.get('If-None-Match')
        if client_etag and client_etag.strip('"') == etag_value:
            # Return 304 Not Modified
            response = make_response('', 304)
            response.headers['ETag'] = f'"{etag_value}"'
        
        return response
    return decorated_function


def init_optimized_middleware(app):
    """Initialize optimized middleware for the application"""
    middleware = OptimizedMiddleware(app)
    
    # Add request ID for tracking
    @app.before_request
    def add_request_id():
        request.id = hashlib.md5(f"{time.time()}{request.remote_addr}".encode()).hexdigest()[:8]
    
    # Log slow requests
    @app.after_request
    def log_slow_requests(response):
        if hasattr(request, '_start_time'):
            elapsed = time.time() - request._start_time
            if elapsed > 1.0:  # Log requests taking more than 1 second
                current_app.logger.warning(
                    f"Slow request: {request.method} {request.path} took {elapsed:.3f}s"
                )
        return response
    
    return middleware