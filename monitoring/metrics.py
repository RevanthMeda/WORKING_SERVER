"""
Prometheus metrics collection for SAT Report Generator.
"""
import time
import functools
from flask import request, g
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.core import CollectorRegistry
import psutil
import os


# Create custom registry for application metrics
REGISTRY = CollectorRegistry()

# HTTP Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=REGISTRY
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=REGISTRY
)

http_requests_in_progress = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    registry=REGISTRY
)

# Application-specific metrics
reports_created_total = Counter(
    'reports_created_total',
    'Total number of reports created',
    ['report_type', 'user_role'],
    registry=REGISTRY
)

reports_approved_total = Counter(
    'reports_approved_total',
    'Total number of reports approved',
    ['report_type', 'approval_stage'],
    registry=REGISTRY
)

reports_rejected_total = Counter(
    'reports_rejected_total',
    'Total number of reports rejected',
    ['report_type', 'approval_stage'],
    registry=REGISTRY
)

active_users_gauge = Gauge(
    'active_users',
    'Number of currently active users',
    registry=REGISTRY
)

pending_approvals_gauge = Gauge(
    'pending_approvals',
    'Number of reports pending approval',
    ['approval_stage'],
    registry=REGISTRY
)

# Database metrics
database_connections_active = Gauge(
    'database_connections_active',
    'Number of active database connections',
    registry=REGISTRY
)

database_query_duration_seconds = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    registry=REGISTRY
)

database_queries_total = Counter(
    'database_queries_total',
    'Total number of database queries',
    ['query_type', 'status'],
    registry=REGISTRY
)

# Email metrics
emails_sent_total = Counter(
    'emails_sent_total',
    'Total number of emails sent',
    ['email_type', 'status'],
    registry=REGISTRY
)

# File upload metrics
file_uploads_total = Counter(
    'file_uploads_total',
    'Total number of file uploads',
    ['file_type', 'status'],
    registry=REGISTRY
)

file_upload_size_bytes = Histogram(
    'file_upload_size_bytes',
    'Size of uploaded files in bytes',
    ['file_type'],
    registry=REGISTRY
)

# System metrics
system_cpu_usage_percent = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage',
    registry=REGISTRY
)

system_memory_usage_bytes = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes',
    ['type'],  # available, used, total
    registry=REGISTRY
)

system_disk_usage_bytes = Gauge(
    'system_disk_usage_bytes',
    'System disk usage in bytes',
    ['path', 'type'],  # type: free, used, total
    registry=REGISTRY
)

# Application info
app_info = Info(
    'app_info',
    'Application information',
    registry=REGISTRY
)

# Error metrics
application_errors_total = Counter(
    'application_errors_total',
    'Total number of application errors',
    ['error_type', 'severity'],
    registry=REGISTRY
)

# Session metrics
user_sessions_active = Gauge(
    'user_sessions_active',
    'Number of active user sessions',
    registry=REGISTRY
)

user_login_attempts_total = Counter(
    'user_login_attempts_total',
    'Total number of login attempts',
    ['status'],  # success, failure
    registry=REGISTRY
)


class MetricsCollector:
    """Collect and update application metrics."""
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize metrics collection with Flask app."""
        self.app = app
        
        # Set application info
        app_info.info({
            'version': app.config.get('VERSION', '1.0.0'),
            'environment': app.config.get('FLASK_ENV', 'production'),
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
        })
        
        # Register request handlers
        app.before_request(self._before_request)
        app.after_request(self._after_request)
        
        # Register metrics endpoint
        app.add_url_rule('/metrics', 'metrics', self._metrics_endpoint)
        
        # Start background metrics collection
        self._start_system_metrics_collection()
    
    def _before_request(self):
        """Called before each request."""
        g.start_time = time.time()
        http_requests_in_progress.inc()
    
    def _after_request(self, response):
        """Called after each request."""
        # Decrement in-progress counter
        http_requests_in_progress.dec()
        
        # Record request metrics
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            
            method = request.method
            endpoint = request.endpoint or 'unknown'
            status_code = str(response.status_code)
            
            # Update counters and histograms
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
        
        return response
    
    def _metrics_endpoint(self):
        """Endpoint to expose Prometheus metrics."""
        from flask import Response
        
        # Update dynamic metrics before serving
        self._update_dynamic_metrics()
        
        return Response(
            generate_latest(REGISTRY),
            mimetype=CONTENT_TYPE_LATEST
        )
    
    def _update_dynamic_metrics(self):
        """Update metrics that need to be calculated dynamically."""
        try:
            # Update active users count
            from models import User
            from flask_login import current_user
            from flask import session
            
            # This is a simplified example - in production, you'd track active sessions
            active_users_gauge.set(self._get_active_users_count())
            
            # Update pending approvals
            self._update_pending_approvals()
            
            # Update database connection metrics
            self._update_database_metrics()
            
        except Exception as e:
            application_errors_total.labels(
                error_type='metrics_update',
                severity='warning'
            ).inc()
    
    def _get_active_users_count(self):
        """Get count of active users (simplified implementation)."""
        try:
            from models import User
            # In a real implementation, you'd track active sessions
            return User.query.filter_by(status='Active').count()
        except:
            return 0
    
    def _update_pending_approvals(self):
        """Update pending approvals metrics."""
        try:
            from models import Report
            import json
            
            # Get reports with pending approvals
            reports = Report.query.filter_by(status='PENDING').all()
            
            # Count by approval stage
            stage_counts = {}
            for report in reports:
                if report.approvals_json:
                    approvals = json.loads(report.approvals_json)
                    for approval in approvals:
                        if approval.get('status') == 'pending':
                            stage = str(approval.get('stage', 'unknown'))
                            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            
            # Update gauges
            for stage, count in stage_counts.items():
                pending_approvals_gauge.labels(approval_stage=stage).set(count)
                
        except Exception as e:
            application_errors_total.labels(
                error_type='pending_approvals_update',
                severity='warning'
            ).inc()
    
    def _update_database_metrics(self):
        """Update database-related metrics."""
        try:
            from models import db
            
            # Get database connection pool info
            engine = db.engine
            pool = engine.pool
            
            # Update connection metrics
            database_connections_active.set(pool.checkedout())
            
        except Exception as e:
            application_errors_total.labels(
                error_type='database_metrics_update',
                severity='warning'
            ).inc()
    
    def _start_system_metrics_collection(self):
        """Start collecting system metrics in background."""
        import threading
        
        def collect_system_metrics():
            while True:
                try:
                    # CPU usage
                    cpu_percent = psutil.cpu_percent(interval=1)
                    system_cpu_usage_percent.set(cpu_percent)
                    
                    # Memory usage
                    memory = psutil.virtual_memory()
                    system_memory_usage_bytes.labels(type='total').set(memory.total)
                    system_memory_usage_bytes.labels(type='used').set(memory.used)
                    system_memory_usage_bytes.labels(type='available').set(memory.available)
                    
                    # Disk usage
                    disk_usage = psutil.disk_usage('/')
                    system_disk_usage_bytes.labels(path='/', type='total').set(disk_usage.total)
                    system_disk_usage_bytes.labels(path='/', type='used').set(disk_usage.used)
                    system_disk_usage_bytes.labels(path='/', type='free').set(disk_usage.free)
                    
                    time.sleep(30)  # Update every 30 seconds
                    
                except Exception as e:
                    application_errors_total.labels(
                        error_type='system_metrics_collection',
                        severity='error'
                    ).inc()
                    time.sleep(60)  # Wait longer on error
        
        # Start background thread
        thread = threading.Thread(target=collect_system_metrics, daemon=True)
        thread.start()


# Decorator for timing database queries
def time_database_query(query_type):
    """Decorator to time database queries."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'success'
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                status = 'error'
                application_errors_total.labels(
                    error_type='database_query',
                    severity='error'
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                database_query_duration_seconds.labels(query_type=query_type).observe(duration)
                database_queries_total.labels(query_type=query_type, status=status).inc()
        
        return wrapper
    return decorator


# Decorator for timing email operations
def time_email_operation(email_type):
    """Decorator to time email operations."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            status = 'success'
            
            try:
                result = func(*args, **kwargs)
                if not result:
                    status = 'failure'
                return result
            except Exception as e:
                status = 'error'
                application_errors_total.labels(
                    error_type='email_operation',
                    severity='error'
                ).inc()
                raise
            finally:
                emails_sent_total.labels(email_type=email_type, status=status).inc()
        
        return wrapper
    return decorator


# Business metrics functions
def record_report_created(report_type, user_role):
    """Record a report creation event."""
    reports_created_total.labels(report_type=report_type, user_role=user_role).inc()


def record_report_approved(report_type, approval_stage):
    """Record a report approval event."""
    reports_approved_total.labels(report_type=report_type, approval_stage=str(approval_stage)).inc()


def record_report_rejected(report_type, approval_stage):
    """Record a report rejection event."""
    reports_rejected_total.labels(report_type=report_type, approval_stage=str(approval_stage)).inc()


def record_file_upload(file_type, file_size, success=True):
    """Record a file upload event."""
    status = 'success' if success else 'failure'
    file_uploads_total.labels(file_type=file_type, status=status).inc()
    
    if success:
        file_upload_size_bytes.labels(file_type=file_type).observe(file_size)


def record_login_attempt(success=True):
    """Record a login attempt."""
    status = 'success' if success else 'failure'
    user_login_attempts_total.labels(status=status).inc()


def record_application_error(error_type, severity='error'):
    """Record an application error."""
    application_errors_total.labels(error_type=error_type, severity=severity).inc()


# Initialize metrics collector
metrics_collector = MetricsCollector()