"""
Input validation and sanitization for SAT Report Generator.
"""
import re
import html
import bleach
from urllib.parse import urlparse
from functools import wraps
from flask import request, abort, jsonify
from werkzeug.exceptions import BadRequest
from marshmallow import Schema, fields, ValidationError, validates, validates_schema
from monitoring.logging_config import audit_logger


class InputSanitizer:
    """Input sanitization utilities."""
    
    # Allowed HTML tags and attributes for rich text
    ALLOWED_TAGS = [
        'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote'
    ]
    
    ALLOWED_ATTRIBUTES = {
        '*': ['class'],
        'a': ['href', 'title'],
        'img': ['src', 'alt', 'width', 'height']
    }
    
    @staticmethod
    def sanitize_html(text):
        """Sanitize HTML content."""
        if not text:
            return text
        
        # Clean HTML with bleach
        cleaned = bleach.clean(
            text,
            tags=InputSanitizer.ALLOWED_TAGS,
            attributes=InputSanitizer.ALLOWED_ATTRIBUTES,
            strip=True
        )
        
        return cleaned
    
    @staticmethod
    def sanitize_text(text):
        """Sanitize plain text input."""
        if not text:
            return text
        
        # HTML escape
        sanitized = html.escape(text)
        
        # Remove null bytes
        sanitized = sanitized.replace('\x00', '')
        
        # Normalize whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        return sanitized
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename for safe storage."""
        if not filename:
            return filename
        
        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
        
        # Remove leading/trailing dots and spaces
        sanitized = sanitized.strip('. ')
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            sanitized = name[:255-len(ext)-1] + ('.' + ext if ext else '')
        
        return sanitized
    
    @staticmethod
    def sanitize_email(email):
        """Sanitize email address."""
        if not email:
            return email
        
        # Basic email sanitization
        email = email.strip().lower()
        
        # Remove dangerous characters
        email = re.sub(r'[<>"\\]', '', email)
        
        return email
    
    @staticmethod
    def sanitize_url(url):
        """Sanitize URL input."""
        if not url:
            return url
        
        # Parse URL
        parsed = urlparse(url)
        
        # Only allow http/https schemes
        if parsed.scheme not in ['http', 'https']:
            return None
        
        # Reconstruct clean URL
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        if parsed.query:
            clean_url += f"?{parsed.query}"
        
        return clean_url


class InputValidator:
    """Input validation utilities."""
    
    # Common regex patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^[+]?[1-9]?[0-9]{7,15}$')
    ALPHANUMERIC_PATTERN = re.compile(r'^[a-zA-Z0-9]+$')
    SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.]+$')
    
    @staticmethod
    def validate_email(email):
        """Validate email format."""
        if not email:
            return False, "Email is required"
        
        if len(email) > 254:
            return False, "Email is too long"
        
        if not InputValidator.EMAIL_PATTERN.match(email):
            return False, "Invalid email format"
        
        return True, None
    
    @staticmethod
    def validate_password_strength(password):
        """Validate password strength."""
        from security.authentication import PasswordPolicy
        return PasswordPolicy.validate_password(password)
    
    @staticmethod
    def validate_filename(filename):
        """Validate filename."""
        if not filename:
            return False, "Filename is required"
        
        if len(filename) > 255:
            return False, "Filename is too long"
        
        # Check for dangerous patterns
        dangerous_patterns = [
            r'\.\.', r'^\.',  # Path traversal
            r'[<>:"/\\|?*]',  # Invalid characters
            r'\x00',  # Null bytes
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, filename):
                return False, "Filename contains invalid characters"
        
        return True, None
    
    @staticmethod
    def validate_file_type(filename, allowed_extensions):
        """Validate file type by extension."""
        if not filename:
            return False, "Filename is required"
        
        if '.' not in filename:
            return False, "File must have an extension"
        
        extension = filename.rsplit('.', 1)[1].lower()
        
        if extension not in allowed_extensions:
            return False, f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        
        return True, None
    
    @staticmethod
    def validate_file_size(file_size, max_size_mb=16):
        """Validate file size."""
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            return False, f"File size exceeds maximum allowed size of {max_size_mb}MB"
        
        return True, None
    
    @staticmethod
    def validate_text_length(text, min_length=0, max_length=1000):
        """Validate text length."""
        if not text and min_length > 0:
            return False, f"Text must be at least {min_length} characters"
        
        if text and len(text) > max_length:
            return False, f"Text must not exceed {max_length} characters"
        
        return True, None
    
    @staticmethod
    def validate_safe_string(text):
        """Validate string contains only safe characters."""
        if not text:
            return True, None
        
        if not InputValidator.SAFE_STRING_PATTERN.match(text):
            return False, "Text contains invalid characters"
        
        return True, None


# Marshmallow schemas for request validation
class UserRegistrationSchema(Schema):
    """Schema for user registration validation."""
    
    full_name = fields.Str(required=True, validate=lambda x: len(x.strip()) >= 2)
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=lambda x: len(x) >= 12)
    requested_role = fields.Str(required=True, validate=lambda x: x in ['Engineer', 'Admin', 'PM', 'Automation Manager'])
    
    @validates('full_name')
    def validate_full_name(self, value):
        sanitized = InputSanitizer.sanitize_text(value)
        if len(sanitized.strip()) < 2:
            raise ValidationError('Full name must be at least 2 characters')
        
        if not re.match(r'^[a-zA-Z\s\-\.]+$', sanitized):
            raise ValidationError('Full name contains invalid characters')
    
    @validates('password')
    def validate_password(self, value):
        from security.authentication import PasswordPolicy
        is_valid, errors = PasswordPolicy.validate_password(value)
        if not is_valid:
            raise ValidationError(errors)


class ReportCreationSchema(Schema):
    """Schema for report creation validation."""
    
    document_title = fields.Str(required=True, validate=lambda x: 5 <= len(x.strip()) <= 200)
    document_reference = fields.Str(required=True, validate=lambda x: 3 <= len(x.strip()) <= 50)
    project_reference = fields.Str(required=True, validate=lambda x: 3 <= len(x.strip()) <= 50)
    client_name = fields.Str(required=True, validate=lambda x: 2 <= len(x.strip()) <= 100)
    revision = fields.Str(required=True, validate=lambda x: len(x.strip()) <= 10)
    prepared_by = fields.Str(required=True, validate=lambda x: 2 <= len(x.strip()) <= 100)
    date = fields.Date(required=True)
    purpose = fields.Str(required=True, validate=lambda x: 10 <= len(x.strip()) <= 1000)
    scope = fields.Str(required=True, validate=lambda x: 10 <= len(x.strip()) <= 2000)
    
    @validates('document_reference')
    def validate_document_reference(self, value):
        sanitized = InputSanitizer.sanitize_text(value)
        if not re.match(r'^[A-Z0-9\-_]+$', sanitized.upper()):
            raise ValidationError('Document reference must contain only letters, numbers, hyphens, and underscores')
    
    @validates('project_reference')
    def validate_project_reference(self, value):
        sanitized = InputSanitizer.sanitize_text(value)
        if not re.match(r'^[A-Z0-9\-_]+$', sanitized.upper()):
            raise ValidationError('Project reference must contain only letters, numbers, hyphens, and underscores')


class FileUploadSchema(Schema):
    """Schema for file upload validation."""
    
    filename = fields.Str(required=True)
    file_size = fields.Int(required=True)
    file_type = fields.Str(required=True)
    
    @validates('filename')
    def validate_filename(self, value):
        is_valid, error = InputValidator.validate_filename(value)
        if not is_valid:
            raise ValidationError(error)
    
    @validates('file_size')
    def validate_file_size(self, value):
        is_valid, error = InputValidator.validate_file_size(value)
        if not is_valid:
            raise ValidationError(error)
    
    @validates('file_type')
    def validate_file_type(self, value):
        allowed_types = ['image/png', 'image/jpeg', 'image/gif', 'application/pdf', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        if value not in allowed_types:
            raise ValidationError(f'File type not allowed. Allowed types: {", ".join(allowed_types)}')


class CSRFProtection:
    """CSRF protection utilities."""
    
    @staticmethod
    def generate_csrf_token():
        """Generate CSRF token."""
        import secrets
        token = secrets.token_urlsafe(32)
        from flask import session
        session['csrf_token'] = token
        return token
    
    @staticmethod
    def validate_csrf_token(token):
        """Validate CSRF token."""
        from flask import session
        return token and session.get('csrf_token') == token


def validate_request_data(schema_class):
    """Decorator to validate request data using Marshmallow schema."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            schema = schema_class()
            
            try:
                # Get data based on content type
                if request.is_json:
                    data = request.get_json()
                else:
                    data = request.form.to_dict()
                
                # Validate data
                validated_data = schema.load(data)
                
                # Add validated data to request context
                request.validated_data = validated_data
                
                return f(*args, **kwargs)
                
            except ValidationError as e:
                audit_logger.log_security_event(
                    'validation_error',
                    severity='medium',
                    ip_address=request.remote_addr,
                    details=f"Validation errors: {e.messages}"
                )
                
                if request.is_json:
                    return jsonify({'error': 'Validation failed', 'details': e.messages}), 400
                else:
                    abort(400)
        
        return decorated_function
    return decorator


def sanitize_request_data(f):
    """Decorator to sanitize request data."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.is_json:
            data = request.get_json()
            if data:
                sanitized_data = {}
                for key, value in data.items():
                    if isinstance(value, str):
                        sanitized_data[key] = InputSanitizer.sanitize_text(value)
                    else:
                        sanitized_data[key] = value
                request._cached_json = sanitized_data
        
        return f(*args, **kwargs)
    
    return decorated_function


def rate_limit_check(max_requests=100, window=3600):
    """Decorator for rate limiting."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from security.authentication import rate_limiter
            
            # Use IP address as identifier
            identifier = request.remote_addr
            
            if rate_limiter.is_rate_limited(identifier, max_requests, window):
                audit_logger.log_security_event(
                    'rate_limit_exceeded',
                    severity='medium',
                    ip_address=request.remote_addr,
                    details=f"Rate limit exceeded: {max_requests} requests per {window} seconds"
                )
                
                if request.is_json:
                    return jsonify({'error': 'Rate limit exceeded'}), 429
                else:
                    abort(429)
            
            # Record the attempt
            rate_limiter.record_attempt(identifier)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def csrf_protect(f):
    """CSRF protection decorator."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
            
            if not CSRFProtection.validate_csrf_token(token):
                audit_logger.log_security_event(
                    'csrf_token_invalid',
                    severity='high',
                    ip_address=request.remote_addr,
                    details="Invalid or missing CSRF token"
                )
                
                if request.is_json:
                    return jsonify({'error': 'CSRF token validation failed'}), 403
                else:
                    abort(403)
        
        return f(*args, **kwargs)
    
    return decorated_function