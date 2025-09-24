"""
Audit logging and compliance for SAT Report Generator.
"""
import json
import hashlib
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from flask import request, session, current_app, g
from flask_login import current_user
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Index, JSON
from sqlalchemy.dialects.postgresql import UUID
from models import db
import uuid


class AuditEventType(Enum):
    """Audit event types for categorization."""
    
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    
    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGE = "permission_change"
    ROLE_CHANGE = "role_change"
    
    # Data events
    DATA_CREATE = "data_create"
    DATA_READ = "data_read"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    
    # Report events
    REPORT_CREATE = "report_create"
    REPORT_UPDATE = "report_update"
    REPORT_DELETE = "report_delete"
    REPORT_APPROVE = "report_approve"
    REPORT_REJECT = "report_reject"
    REPORT_GENERATE = "report_generate"
    REPORT_DOWNLOAD = "report_download"
    
    # File events
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    FILE_DELETE = "file_delete"
    
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGE = "config_change"
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"
    
    # Security events
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_BREACH_ATTEMPT = "data_breach_attempt"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Audit event data structure."""
    
    event_type: AuditEventType
    severity: AuditSeverity
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class AuditLog(db.Model):
    """Audit log database model."""
    
    __tablename__ = 'audit_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    user_id = Column(String(50), nullable=True)
    session_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    action = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    checksum = Column(String(64), nullable=False)  # SHA-256 hash for integrity
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_user_id', 'user_id'),
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_severity', 'severity'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self):
        """Calculate SHA-256 checksum for integrity verification."""
        data = {
            'event_type': self.event_type,
            'severity': self.severity,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'action': self.action,
            'details': self.details,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
        
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def verify_integrity(self):
        """Verify the integrity of the audit log entry."""
        return self.checksum == self._calculate_checksum()
    
    def to_dict(self):
        """Convert audit log to dictionary."""
        return {
            'id': str(self.id),
            'event_type': self.event_type,
            'severity': self.severity,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'resource_type': self.resource_type,
            'resource_id': self.resource_id,
            'action': self.action,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'checksum': self.checksum
        }


class AuditLogger:
    """Centralized audit logging service."""
    
    def __init__(self):
        self.enabled = True
        self.retention_days = 2555  # 7 years for compliance
    
    def log_event(self, event: AuditEvent):
        """Log an audit event."""
        if not self.enabled:
            return
        
        try:
            # Create audit log entry
            audit_log = AuditLog(
                event_type=event.event_type.value,
                severity=event.severity.value,
                user_id=event.user_id,
                session_id=event.session_id,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                action=event.action,
                details=event.details,
                timestamp=event.timestamp
            )
            
            db.session.add(audit_log)
            db.session.commit()
            
            # Log to application logger as well
            from monitoring.logging_config import audit_logger as app_logger
            app_logger.info(
                "Audit event logged",
                extra={
                    'audit_id': str(audit_log.id),
                    'event_type': event.event_type.value,
                    'severity': event.severity.value,
                    'user_id': event.user_id,
                    'resource_type': event.resource_type,
                    'resource_id': event.resource_id
                }
            )
            
        except Exception as e:
            # Critical: audit logging failure
            current_app.logger.critical(f"Audit logging failed: {str(e)}")
            # In production, this might trigger alerts
    
    def log_authentication_event(self, event_type: AuditEventType, user_id: str = None, 
                                success: bool = True, details: Dict = None):
        """Log authentication-related events."""
        severity = AuditSeverity.LOW if success else AuditSeverity.MEDIUM
        
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            user_id=user_id or (current_user.id if current_user.is_authenticated else None),
            session_id=session.get('session_id'),
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None,
            details=details
        )
        
        self.log_event(event)
    
    def log_data_access(self, action: str, resource_type: str, resource_id: str = None,
                       details: Dict = None):
        """Log data access events."""
        event_type_map = {
            'create': AuditEventType.DATA_CREATE,
            'read': AuditEventType.DATA_READ,
            'update': AuditEventType.DATA_UPDATE,
            'delete': AuditEventType.DATA_DELETE,
            'export': AuditEventType.DATA_EXPORT
        }
        
        event_type = event_type_map.get(action.lower(), AuditEventType.DATA_READ)
        severity = AuditSeverity.HIGH if action.lower() == 'delete' else AuditSeverity.LOW
        
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session.get('session_id'),
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=details
        )
        
        self.log_event(event)
    
    def log_report_event(self, action: str, report_id: str, details: Dict = None):
        """Log report-related events."""
        event_type_map = {
            'create': AuditEventType.REPORT_CREATE,
            'update': AuditEventType.REPORT_UPDATE,
            'delete': AuditEventType.REPORT_DELETE,
            'approve': AuditEventType.REPORT_APPROVE,
            'reject': AuditEventType.REPORT_REJECT,
            'generate': AuditEventType.REPORT_GENERATE,
            'download': AuditEventType.REPORT_DOWNLOAD
        }
        
        event_type = event_type_map.get(action.lower(), AuditEventType.DATA_READ)
        severity = AuditSeverity.MEDIUM if action.lower() in ['delete', 'approve'] else AuditSeverity.LOW
        
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            user_id=current_user.id if current_user.is_authenticated else None,
            session_id=session.get('session_id'),
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None,
            resource_type='report',
            resource_id=report_id,
            action=action,
            details=details
        )
        
        self.log_event(event)
    
    def log_security_event(self, event_type: str, severity: str = 'medium', 
                          user_id: str = None, details: Dict = None):
        """Log security-related events."""
        event_type_enum = getattr(AuditEventType, event_type.upper(), AuditEventType.SECURITY_VIOLATION)
        severity_enum = getattr(AuditSeverity, severity.upper(), AuditSeverity.MEDIUM)
        
        event = AuditEvent(
            event_type=event_type_enum,
            severity=severity_enum,
            user_id=user_id or (current_user.id if current_user.is_authenticated else None),
            session_id=session.get('session_id'),
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None,
            details=details
        )
        
        self.log_event(event)
    
    def get_audit_logs(self, start_date: datetime = None, end_date: datetime = None,
                      user_id: str = None, event_type: str = None, 
                      severity: str = None, limit: int = 100):
        """Retrieve audit logs with filtering."""
        query = AuditLog.query
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        if event_type:
            query = query.filter(AuditLog.event_type == event_type)
        
        if severity:
            query = query.filter(AuditLog.severity == severity)
        
        return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    def cleanup_old_logs(self):
        """Clean up old audit logs based on retention policy."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        deleted_count = AuditLog.query.filter(
            AuditLog.timestamp < cutoff_date
        ).delete()
        
        db.session.commit()
        
        self.log_event(AuditEvent(
            event_type=AuditEventType.SYSTEM_START,
            severity=AuditSeverity.LOW,
            details={'action': 'audit_log_cleanup', 'deleted_count': deleted_count}
        ))
        
        return deleted_count
    
    def generate_compliance_report(self, start_date: datetime, end_date: datetime):
        """Generate compliance report for audit logs."""
        logs = self.get_audit_logs(start_date=start_date, end_date=end_date, limit=10000)
        
        # Group by event type
        event_summary = {}
        user_activity = {}
        security_events = []
        
        for log in logs:
            # Event type summary
            if log.event_type not in event_summary:
                event_summary[log.event_type] = 0
            event_summary[log.event_type] += 1
            
            # User activity summary
            if log.user_id:
                if log.user_id not in user_activity:
                    user_activity[log.user_id] = 0
                user_activity[log.user_id] += 1
            
            # Security events
            if log.severity in ['high', 'critical']:
                security_events.append(log.to_dict())
        
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'total_events': len(logs),
            'event_summary': event_summary,
            'user_activity': user_activity,
            'security_events': security_events,
            'generated_at': datetime.utcnow().isoformat()
        }


class DataEncryption:
    """Data encryption utilities for sensitive information."""
    
    def __init__(self):
        from cryptography.fernet import Fernet
        self.cipher_suite = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize encryption with key from configuration."""
        try:
            from cryptography.fernet import Fernet
            
            # Get encryption key from environment or generate one
            encryption_key = current_app.config.get('ENCRYPTION_KEY')
            
            if not encryption_key:
                # Generate a new key (in production, this should be stored securely)
                encryption_key = Fernet.generate_key()
                current_app.logger.warning("Generated new encryption key. Store this securely!")
            
            if isinstance(encryption_key, str):
                encryption_key = encryption_key.encode()
            
            self.cipher_suite = Fernet(encryption_key)
            
        except Exception as e:
            # Handle case where we're outside application context
            try:
                current_app.logger.error(f"Failed to initialize encryption: {str(e)}")
            except RuntimeError:
                # Outside application context, use basic logging
                import logging
                logging.getLogger(__name__).error(f"Failed to initialize encryption: {str(e)}")
            self.cipher_suite = None
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data."""
        if not self.cipher_suite or not data:
            return data
        
        try:
            encrypted_data = self.cipher_suite.encrypt(data.encode())
            return encrypted_data.decode()
        except Exception as e:
            current_app.logger.error(f"Encryption failed: {str(e)}")
            return data
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        if not self.cipher_suite or not encrypted_data:
            return encrypted_data
        
        try:
            decrypted_data = self.cipher_suite.decrypt(encrypted_data.encode())
            return decrypted_data.decode()
        except Exception as e:
            current_app.logger.error(f"Decryption failed: {str(e)}")
            return encrypted_data


class ComplianceManager:
    """Compliance management utilities."""
    
    def __init__(self):
        self.audit_logger = AuditLogger()
        self.data_encryption = DataEncryption()
    
    def ensure_gdpr_compliance(self, user_id: str):
        """Ensure GDPR compliance for user data."""
        # Log data access
        self.audit_logger.log_data_access(
            action='read',
            resource_type='user_data',
            resource_id=user_id,
            details={'compliance': 'GDPR', 'purpose': 'data_access_audit'}
        )
    
    def handle_data_deletion_request(self, user_id: str):
        """Handle GDPR right to be forgotten request."""
        try:
            # This would implement actual data deletion logic
            # For now, just log the request
            
            self.audit_logger.log_data_access(
                action='delete',
                resource_type='user_data',
                resource_id=user_id,
                details={
                    'compliance': 'GDPR',
                    'request_type': 'right_to_be_forgotten',
                    'status': 'initiated'
                }
            )
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Data deletion request failed: {str(e)}")
            return False
    
    def generate_data_export(self, user_id: str):
        """Generate data export for GDPR compliance."""
        try:
            # This would implement actual data export logic
            # For now, just log the request
            
            self.audit_logger.log_data_access(
                action='export',
                resource_type='user_data',
                resource_id=user_id,
                details={
                    'compliance': 'GDPR',
                    'request_type': 'data_portability',
                    'status': 'initiated'
                }
            )
            
            return {'status': 'success', 'message': 'Data export initiated'}
            
        except Exception as e:
            current_app.logger.error(f"Data export request failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}


# Global instances - lazy loaded
audit_logger = None
compliance_manager = None
data_encryption = None

def get_audit_logger():
    """Get or create audit logger instance."""
    global audit_logger
    if audit_logger is None:
        audit_logger = AuditLogger()
    return audit_logger

def get_compliance_manager():
    """Get or create compliance manager instance."""
    global compliance_manager
    if compliance_manager is None:
        compliance_manager = ComplianceManager()
    return compliance_manager

def get_data_encryption():
    """Get or create data encryption instance."""
    global data_encryption
    if data_encryption is None:
        data_encryption = DataEncryption()
    return data_encryption


# Decorators for automatic audit logging
def audit_data_access(resource_type: str, action: str = 'read'):
    """Decorator to automatically audit data access."""
    def decorator(f):
        from functools import wraps
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract resource ID from kwargs or args
            resource_id = kwargs.get('id') or (args[0] if args else None)
            
            # Log the access
            audit_logger.log_data_access(
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None
            )
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def audit_report_action(action: str):
    """Decorator to automatically audit report actions."""
    def decorator(f):
        from functools import wraps
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract report ID from kwargs or args
            report_id = kwargs.get('report_id') or kwargs.get('id') or (args[0] if args else None)
            
            # Execute the function
            result = f(*args, **kwargs)
            
            # Log the action
            audit_logger.log_report_event(
                action=action,
                report_id=str(report_id) if report_id else None,
                details={'status': 'success'}
            )
            
            return result
        
        return decorated_function
    return decorator