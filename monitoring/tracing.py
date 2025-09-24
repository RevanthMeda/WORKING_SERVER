"""
Distributed tracing configuration using OpenTelemetry.
"""
import os
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.jaeger import JaegerPropagator
from opentelemetry.propagators.composite import CompositeHTTPPropagator
import functools
from flask import g, request
import time


class TracingConfig:
    """Configuration for distributed tracing."""
    
    def __init__(self, app=None):
        self.app = app
        self.tracer = None
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize tracing with Flask app."""
        self.app = app
        
        # Check if tracing is enabled
        if not app.config.get('TRACING_ENABLED', True):
            return
        
        # Configure resource
        resource = Resource.create({
            "service.name": app.config.get('SERVICE_NAME', 'sat-report-generator'),
            "service.version": app.config.get('VERSION', '1.0.0'),
            "service.environment": app.config.get('FLASK_ENV', 'production'),
            "service.instance.id": os.environ.get('HOSTNAME', 'unknown'),
        })
        
        # Set up tracer provider
        trace.set_tracer_provider(TracerProvider(resource=resource))
        
        # Configure Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=app.config.get('JAEGER_AGENT_HOST', 'localhost'),
            agent_port=app.config.get('JAEGER_AGENT_PORT', 6831),
            collector_endpoint=app.config.get('JAEGER_COLLECTOR_ENDPOINT'),
        )
        
        # Add span processor
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Set up propagators
        set_global_textmap(
            CompositeHTTPPropagator([
                JaegerPropagator(),
                B3MultiFormat(),
            ])
        )
        
        # Get tracer
        self.tracer = trace.get_tracer(__name__)
        
        # Instrument Flask app
        FlaskInstrumentor().instrument_app(app)
        
        # Instrument SQLAlchemy
        try:
            from models import db
            SQLAlchemyInstrumentor().instrument(engine=db.engine)
        except ImportError:
            pass
        
        # Instrument requests library
        RequestsInstrumentor().instrument()
        
        # Instrument Redis (if available)
        try:
            RedisInstrumentor().instrument()
        except ImportError:
            pass
        
        # Add custom span attributes
        @app.before_request
        def add_trace_context():
            span = trace.get_current_span()
            if span:
                # Add request attributes
                span.set_attribute("http.method", request.method)
                span.set_attribute("http.url", request.url)
                span.set_attribute("http.route", request.endpoint or "unknown")
                span.set_attribute("http.user_agent", request.headers.get('User-Agent', ''))
                
                # Add user context if available
                try:
                    from flask_login import current_user
                    if current_user.is_authenticated:
                        span.set_attribute("user.id", str(current_user.id))
                        span.set_attribute("user.email", current_user.email)
                        span.set_attribute("user.role", current_user.role)
                except:
                    pass
                
                # Store span in g for access in other functions
                g.current_span = span
        
        @app.after_request
        def finalize_trace(response):
            span = getattr(g, 'current_span', None)
            if span:
                span.set_attribute("http.status_code", response.status_code)
                
                # Add response size if available
                if response.content_length:
                    span.set_attribute("http.response_size", response.content_length)
                
                # Set span status based on response code
                if response.status_code >= 400:
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
            
            return response


def trace_function(operation_name=None, attributes=None):
    """Decorator to trace function execution."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)
                
                # Add function metadata
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)
                
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    
                    # Add execution time
                    execution_time = time.time() - start_time
                    span.set_attribute("function.execution_time", execution_time)
                    
                    return result
                    
                except Exception as e:
                    # Record exception in span
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


def trace_database_operation(operation_type, table_name=None):
    """Decorator to trace database operations."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = f"db.{operation_type}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Add database attributes
                span.set_attribute("db.operation", operation_type)
                if table_name:
                    span.set_attribute("db.table", table_name)
                
                span.set_attribute("db.system", "postgresql")
                
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    
                    # Add query execution time
                    execution_time = time.time() - start_time
                    span.set_attribute("db.execution_time", execution_time)
                    
                    # Add result metadata if applicable
                    if hasattr(result, 'rowcount'):
                        span.set_attribute("db.rows_affected", result.rowcount)
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


def trace_external_call(service_name, operation=None):
    """Decorator to trace external service calls."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = f"external.{service_name}"
            if operation:
                span_name += f".{operation}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Add external service attributes
                span.set_attribute("external.service", service_name)
                if operation:
                    span.set_attribute("external.operation", operation)
                
                try:
                    start_time = time.time()
                    result = func(*args, **kwargs)
                    
                    # Add call duration
                    duration = time.time() - start_time
                    span.set_attribute("external.duration", duration)
                    
                    return result
                    
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


def trace_business_operation(operation_name, attributes=None):
    """Decorator to trace business operations."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = f"business.{operation_name}"
            
            with tracer.start_as_current_span(span_name) as span:
                # Add business operation attributes
                span.set_attribute("business.operation", operation_name)
                
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(f"business.{key}", value)
                
                # Add user context if available
                try:
                    from flask_login import current_user
                    if current_user.is_authenticated:
                        span.set_attribute("business.user_id", str(current_user.id))
                        span.set_attribute("business.user_role", current_user.role)
                except:
                    pass
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Add success indicator
                    span.set_attribute("business.success", True)
                    
                    return result
                    
                except Exception as e:
                    span.set_attribute("business.success", False)
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise
        
        return wrapper
    return decorator


class CustomSpanProcessor:
    """Custom span processor for additional processing."""
    
    def on_start(self, span, parent_context):
        """Called when a span starts."""
        # Add custom attributes or processing
        pass
    
    def on_end(self, span):
        """Called when a span ends."""
        # Add custom processing when span ends
        # Could send metrics, log events, etc.
        pass
    
    def shutdown(self):
        """Called when the processor is shut down."""
        pass
    
    def force_flush(self, timeout_millis=30000):
        """Force flush any pending spans."""
        return True


# Utility functions for manual tracing
def get_current_trace_id():
    """Get the current trace ID."""
    span = trace.get_current_span()
    if span:
        return format(span.get_span_context().trace_id, '032x')
    return None


def get_current_span_id():
    """Get the current span ID."""
    span = trace.get_current_span()
    if span:
        return format(span.get_span_context().span_id, '016x')
    return None


def add_span_attribute(key, value):
    """Add attribute to current span."""
    span = trace.get_current_span()
    if span:
        span.set_attribute(key, value)


def add_span_event(name, attributes=None):
    """Add event to current span."""
    span = trace.get_current_span()
    if span:
        span.add_event(name, attributes or {})


def record_exception_in_span(exception):
    """Record exception in current span."""
    span = trace.get_current_span()
    if span:
        span.record_exception(exception)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exception)))


# Initialize tracing
tracing_config = TracingConfig()