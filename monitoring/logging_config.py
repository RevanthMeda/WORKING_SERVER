"""
Structured logging configuration for SAT Report Generator.
"""
import logging
import logging.config
import json
import uuid
import time
from datetime import datetime
from flask import request, g, has_request_context
from flask_login import current_user
import structlog


class CorrelationIDProcessor:
    """Add correlation ID to log records."""
    
    def __call__(self, logger, method_name, event_dict):
        # Get correlation ID from Flask g object or generate new one
        if has_request_context():
            correlation_id = getattr(g, 'correlation_id', None)
            if not correlation_id:
                correlation_id = str(uuid.uuid4())
                g.correlation_id = correlation_id
            event_dict['correlation_id'] = correlation_id
        
        return event_dict


class UserContextProcessor:
    """Add user context to log records."""
    
    def __call__(self, logger, method_name, event_dict):
        if has_request_context():
            try:
                if current_user.is_authenticated:
                    event_dict['user_id'] = current_user.id
                    event_dict['user_email'] = current_user.email
                    event_dict['user_role'] = current_user.role
                else:
                    event_dict['user_id'] = 'anonymous'
            except:
                event_dict['user_id'] = 'unknown'
        
        return event_dict


class RequestContextProcessor:
    """Add request context to log records."""
    
    def __call__(self, logger, method_name, event_dict):
        if has_request_context():
            event_dict['request_method'] = request.method
            event_dict['request_path'] = request.path
            event_dict['request_endpoint'] = request.endpoint
            event_dict['remote_addr'] = request.remote_addr
            event_dict['user_agent'] = request.headers.get('User-Agent', '')
            
            # Add request ID if available
            request_id = request.headers.get('X-Request-ID')
            if request_id:
                event_dict['request_id'] = request_id
        
        return event_dict


class TimestampProcessor:
    """Add ISO timestamp to log records."""
    
    def __call__(self, logger, method_name, event_dict):
        event_dict['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        return event_dict


class PerformanceProcessor:
    """Add performance metrics to log records."""
    
    def __call__(self, logger, method_name, event_dict):
        if has_request_context() and hasattr(g, 'start_time'):
            event_dict['request_duration_ms'] = round((time.time() - g.start_time) * 1000, 2)
        
        return event_dict


def configure_structlog():
    """Configure structured logging with structlog."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            TimestampProcessor(),
            CorrelationIDProcessor(),
            UserContextProcessor(),
            RequestContextProcessor(),
            PerformanceProcessor(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def setup_logging(app):
    """Set up logging configuration for the Flask app."""
    
    log_level = app.config.get('LOG_LEVEL', 'INFO').upper()
    log_format = app.config.get('LOG_FORMAT', 'json')
    
    # Configure structlog
    configure_structlog()
    
    # Logging configuration
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                'format': '%(message)s'
            },
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': log_format,
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': log_level,
                'formatter': log_format,
                'filename': 'logs/app.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': log_format,
                'filename': 'logs/error.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5
            }
        },
        'loggers': {
            '': {  # Root logger
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': False
            },
            'sat_report_generator': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': False
            },
            'werkzeug': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False
            },
            'sqlalchemy.engine': {
                'handlers': ['file'],
                'level': 'WARNING',
                'propagate': False
            },
            'error': {
                'handlers': ['console', 'error_file'],
                'level': 'ERROR',
                'propagate': False
            }
        }
    }
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    
    # Create structured logger
    logger = structlog.get_logger('sat_report_generator')
    
    # Add request logging middleware
    @app.before_request
    def log_request_start():
        g.start_time = time.time()
        g.correlation_id = str(uuid.uuid4())
        
        logger.info(
            "Request started",
            method=request.method,
            path=request.path,
            endpoint=request.endpoint,
            remote_addr=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            content_length=request.content_length
        )
    
    @app.after_request
    def log_request_end(response):
        duration_ms = round((time.time() - g.start_time) * 1000, 2)
        
        logger.info(
            "Request completed",
            status_code=response.status_code,
            content_length=response.content_length,
            duration_ms=duration_ms
        )
        
        return response
    
    # Error logging
    @app.errorhandler(Exception)
    def log_exception(error):
        logger.error(
            "Unhandled exception occurred",
            error_type=type(error).__name__,
            error_message=str(error),
            exc_info=True
        )
        
        # Re-raise the exception to let Flask handle it
        raise error
    
    return logger


class AuditLogger:
    """Audit logger for security and compliance events."""
    
    def __init__(self):
        self.logger = structlog.get_logger('audit')
    
    def log_user_action(self, action, user_id=None, user_email=None, resource_type=None, 
                       resource_id=None, details=None, success=True):
        """Log user actions for audit trail."""
        
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
            user_email = current_user.email
        
        self.logger.info(
            "User action",
            action=action,
            user_id=user_id,
            user_email=user_email,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            success=success,
            event_type='user_action'
        )
    
    def log_security_event(self, event_type, severity='medium', details=None, 
                          user_id=None, ip_address=None):
        """Log security-related events."""
        
        if not ip_address and has_request_context():
            ip_address = request.remote_addr
        
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        self.logger.warning(
            "Security event",
            event_type=event_type,
            severity=severity,
            details=details,
            user_id=user_id,
            ip_address=ip_address,
            event_category='security'
        )
    
    def log_data_access(self, resource_type, resource_id, action='read', 
                       user_id=None, success=True):
        """Log data access events for compliance."""
        
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
        
        self.logger.info(
            "Data access",
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            user_id=user_id,
            success=success,
            event_type='data_access'
        )
    
    def log_system_event(self, event_type, severity='info', details=None):
        """Log system events."""
        
        log_method = getattr(self.logger, severity.lower(), self.logger.info)
        log_method(
            "System event",
            event_type=event_type,
            details=details,
            event_category='system'
        )


class BusinessLogger:
    """Logger for business events and metrics."""
    
    def __init__(self):
        self.logger = structlog.get_logger('business')
    
    def log_report_created(self, report_id, report_type, user_id=None, user_role=None):
        """Log report creation events."""
        
        if not user_id and current_user.is_authenticated:
            user_id = current_user.id
            user_role = current_user.role
        
        self.logger.info(
            "Report created",
            report_id=report_id,
            report_type=report_type,
            user_id=user_id,
            user_role=user_role,
            event_type='report_created'
        )
    
    def log_approval_action(self, report_id, action, stage, approver_id=None, 
                           approver_email=None, comments=None):
        """Log approval actions."""
        
        if not approver_id and current_user.is_authenticated:
            approver_id = current_user.id
            approver_email = current_user.email
        
        self.logger.info(
            "Approval action",
            report_id=report_id,
            action=action,
            stage=stage,
            approver_id=approver_id,
            approver_email=approver_email,
            comments=comments,
            event_type='approval_action'
        )
    
    def log_document_generated(self, report_id, document_type, file_path=None, 
                              generation_time_ms=None):
        """Log document generation events."""
        
        self.logger.info(
            "Document generated",
            report_id=report_id,
            document_type=document_type,
            file_path=file_path,
            generation_time_ms=generation_time_ms,
            event_type='document_generated'
        )
    
    def log_email_sent(self, email_type, recipient, subject=None, success=True, 
                      error_message=None):
        """Log email sending events."""
        
        log_method = self.logger.info if success else self.logger.error
        log_method(
            "Email sent",
            email_type=email_type,
            recipient=recipient,
            subject=subject,
            success=success,
            error_message=error_message,
            event_type='email_sent'
        )


# Global logger instances
audit_logger = AuditLogger()
business_logger = BusinessLogger()


# Decorator for logging function calls
def log_function_call(logger_name='sat_report_generator', log_args=False, log_result=False):
    """Decorator to log function calls."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = structlog.get_logger(logger_name)
            
            log_data = {
                'function': func.__name__,
                'module': func.__module__
            }
            
            if log_args:
                log_data['args'] = str(args)
                log_data['kwargs'] = str(kwargs)
            
            logger.debug("Function called", **log_data)
            
            try:
                result = func(*args, **kwargs)
                
                if log_result:
                    log_data['result'] = str(result)
                
                logger.debug("Function completed", **log_data)
                return result
                
            except Exception as e:
                log_data['error'] = str(e)
                log_data['error_type'] = type(e).__name__
                logger.error("Function failed", **log_data, exc_info=True)
                raise
        
        return wrapper
    return decorator