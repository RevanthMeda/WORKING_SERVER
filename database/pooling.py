"""
Database connection pooling optimization for SAT Report Generator.
"""
import logging
import time
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import QueuePool, StaticPool, NullPool
from sqlalchemy.engine import Engine
from flask import current_app
from threading import Lock
import psutil
import os

logger = logging.getLogger(__name__)


class ConnectionPoolManager:
    """Manage database connection pooling with dynamic optimization."""
    
    def __init__(self):
        self.pool_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'idle_connections': 0,
            'pool_overflows': 0,
            'connection_errors': 0,
            'avg_checkout_time': 0,
            'max_checkout_time': 0
        }
        self.checkout_times = []
        self.lock = Lock()
    
    def get_optimal_pool_config(self, database_uri, environment='development'):
        """Get optimal connection pool configuration based on environment and system resources."""
        
        # Get system resources
        cpu_count = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        
        # Base configuration
        config = {
            'poolclass': QueuePool,
            'pool_pre_ping': True,
            'pool_recycle': 3600,  # 1 hour
            'max_overflow': 0,
            'echo': False
        }
        
        if 'sqlite' in database_uri:
            # SQLite configuration
            config.update({
                'poolclass': StaticPool,
                'pool_size': 1,
                'max_overflow': 0,
                'pool_timeout': 20,
                'connect_args': {
                    'check_same_thread': False,
                    'timeout': 30,
                    'isolation_level': None  # Autocommit mode
                }
            })
            
        elif 'postgresql' in database_uri:
            # PostgreSQL configuration
            if environment == 'production':
                # Production settings - optimized for performance
                pool_size = min(10, cpu_count + 4)  # Reduced from 20
                max_overflow = min(5, cpu_count)    # Reduced from 10
                
                config.update({
                    'pool_size': pool_size,
                    'max_overflow': max_overflow,
                    'pool_timeout': 20,  # Reduced from 30
                    'pool_recycle': 1800,  # Reduced from 3600 (30 mins instead of 1 hour)
                    'connect_args': {
                        'connect_timeout': 30,
                        'application_name': 'sat_report_generator',
                        'options': '-c timezone=UTC -c statement_timeout=30000'
                    }
                })
                
            elif environment == 'staging':
                # Staging settings - optimized
                config.update({
                    'pool_size': 5,  # Reduced from 10
                    'max_overflow': 2,  # Reduced from 5
                    'pool_timeout': 15,  # Reduced from 20
                    'pool_recycle': 1800,  # Reduced from 3600
                    'connect_args': {
                        'connect_timeout': 20,
                        'application_name': 'sat_report_generator_staging',
                        'options': '-c timezone=UTC'
                    }
                })
                
            else:
                # Development settings - optimized
                config.update({
                    'pool_size': 2,  # Reduced from 5
                    'max_overflow': 1,  # Reduced from 2
                    'pool_timeout': 10,
                    'pool_recycle': 900,  # Reduced from 1800 (15 mins)
                    'echo': False,  # Disable query logging by default for performance
                    'connect_args': {
                        'connect_timeout': 10,
                        'application_name': 'sat_report_generator_dev'
                    }
                })
        
        elif 'mysql' in database_uri:
            # MySQL configuration - optimized
            if environment == 'production':
                config.update({
                    'pool_size': 8,  # Reduced from 15
                    'max_overflow': 4,  # Reduced from 8
                    'pool_timeout': 20,  # Reduced from 30
                    'pool_recycle': 1800,  # Reduced from 3600
                    'connect_args': {
                        'connect_timeout': 30,
                        'charset': 'utf8mb4'
                    }
                })
            else:
                config.update({
                    'pool_size': 3,  # Reduced from 5
                    'max_overflow': 1,  # Reduced from 2
                    'pool_timeout': 10,
                    'pool_recycle': 900,  # Reduced from 1800
                    'connect_args': {
                        'connect_timeout': 10,
                        'charset': 'utf8mb4'
                    }
                })
        
        # Adjust based on available memory
        if memory_gb < 2:
            # Low memory system
            config['pool_size'] = max(1, config.get('pool_size', 5) // 2)
            config['max_overflow'] = max(0, config.get('max_overflow', 2) // 2)
        elif memory_gb > 8:
            # High memory system
            config['pool_size'] = min(50, config.get('pool_size', 10) * 2)
            config['max_overflow'] = min(20, config.get('max_overflow', 5) * 2)
        
        return config
    
    def create_optimized_engine(self, database_uri, environment='development'):
        """Create database engine with optimized connection pooling."""
        
        pool_config = self.get_optimal_pool_config(database_uri, environment)
        
        # Create engine with optimized settings
        engine = create_engine(database_uri, **pool_config)
        
        # Set up event listeners for monitoring
        self._setup_pool_monitoring(engine)
        
        logger.info(f"Created optimized database engine for {environment}")
        logger.info(f"Pool configuration: {pool_config}")
        
        return engine
    
    def _setup_pool_monitoring(self, engine):
        """Set up connection pool monitoring."""
        
        @event.listens_for(engine, "connect")
        def connect(dbapi_conn, connection_record):
            """Monitor connection creation."""
            with self.lock:
                self.pool_stats['total_connections'] += 1
            logger.debug("Database connection created")
        
        @event.listens_for(engine, "checkout")
        def checkout(dbapi_conn, connection_record, connection_proxy):
            """Monitor connection checkout."""
            connection_record.checkout_time = time.time()
            with self.lock:
                self.pool_stats['active_connections'] += 1
            logger.debug("Database connection checked out")
        
        @event.listens_for(engine, "checkin")
        def checkin(dbapi_conn, connection_record):
            """Monitor connection checkin."""
            if hasattr(connection_record, 'checkout_time'):
                checkout_duration = time.time() - connection_record.checkout_time
                
                with self.lock:
                    self.pool_stats['active_connections'] -= 1
                    self.checkout_times.append(checkout_duration)
                    
                    # Keep only last 1000 checkout times
                    if len(self.checkout_times) > 1000:
                        self.checkout_times = self.checkout_times[-1000:]
                    
                    # Update statistics
                    if self.checkout_times:
                        self.pool_stats['avg_checkout_time'] = sum(self.checkout_times) / len(self.checkout_times)
                        self.pool_stats['max_checkout_time'] = max(self.checkout_times)
                
                logger.debug(f"Database connection checked in (duration: {checkout_duration:.3f}s)")
        
        @event.listens_for(engine, "close")
        def close(dbapi_conn, connection_record):
            """Monitor connection closure."""
            with self.lock:
                self.pool_stats['total_connections'] -= 1
            logger.debug("Database connection closed")
        
        @event.listens_for(engine, "close_detached")
        def close_detached(dbapi_conn):
            """Monitor detached connection closure."""
            logger.debug("Detached database connection closed")
    
    def get_pool_status(self, engine):
        """Get current connection pool status."""
        try:
            pool = engine.pool
            
            status = {
                'pool_size': pool.size(),
                'checked_in': pool.checkedin(),
                'checked_out': pool.checkedout(),
                'overflow': pool.overflow(),
                'stats': self.pool_stats.copy()
            }
            
            # Calculate pool utilization
            total_capacity = status['pool_size'] + status['overflow']
            if total_capacity > 0:
                status['utilization'] = (status['checked_out'] / total_capacity) * 100
            else:
                status['utilization'] = 0
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get pool status: {e}")
            return {}
    
    def optimize_pool_settings(self, engine, target_utilization=70):
        """Dynamically optimize pool settings based on usage patterns."""
        try:
            status = self.get_pool_status(engine)
            current_utilization = status.get('utilization', 0)
            
            recommendations = []
            
            # Get system resource information for optimization
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            memory_usage = memory_info.percent
            
            # Analyze utilization patterns with system resource consideration
            if current_utilization < 30 and memory_usage < 70:
                # Pool is under-utilized and system has memory headroom
                new_size = max(1, status['pool_size'] - 2)
                recommendations.append({
                    'setting': 'pool_size',
                    'current': status['pool_size'],
                    'recommended': new_size,
                    'reason': f'Pool utilization is low ({current_utilization:.1f}%) and memory usage is acceptable ({memory_usage:.1f}%)',
                    'impact': 'Reduce memory usage',
                    'priority': 'low'
                })
            
            elif current_utilization > 90 or (current_utilization > 70 and cpu_usage > 80):
                # Pool is over-utilized or system is under stress
                max_size = 30 if memory_usage > 80 else 50  # Reduce max if memory is constrained
                new_size = min(max_size, status['pool_size'] + 3)
                recommendations.append({
                    'setting': 'pool_size',
                    'current': status['pool_size'],
                    'recommended': new_size,
                    'reason': f'Pool utilization is high ({current_utilization:.1f}%) or system under stress (CPU: {cpu_usage:.1f}%)',
                    'impact': 'Reduce connection wait times',
                    'priority': 'high'
                })
            
            # Check average checkout time
            avg_checkout = self.pool_stats.get('avg_checkout_time', 0)
            if avg_checkout > 10:  # 10 seconds
                recommendations.append({
                    'setting': 'pool_timeout',
                    'current': 'unknown',
                    'recommended': max(30, int(avg_checkout * 1.5)),
                    'reason': f'High average checkout time: {avg_checkout:.2f}s',
                    'impact': 'Prevent timeout errors',
                    'priority': 'medium'
                })
            
            # Check for frequent overflows
            overflow_ratio = status.get('overflow', 0) / max(status.get('pool_size', 1), 1)
            if overflow_ratio > 0.5:
                new_overflow = min(20, status.get('overflow', 0) + 2)
                recommendations.append({
                    'setting': 'max_overflow',
                    'current': status.get('overflow', 0),
                    'recommended': new_overflow,
                    'reason': f'High overflow ratio: {overflow_ratio:.1f}',
                    'impact': 'Handle traffic spikes better',
                    'priority': 'medium'
                })
            
            # Check connection error rate
            error_rate = self.pool_stats.get('connection_errors', 0)
            if error_rate > 10:
                recommendations.append({
                    'setting': 'pool_pre_ping',
                    'current': 'unknown',
                    'recommended': True,
                    'reason': f'High connection error rate: {error_rate}',
                    'impact': 'Reduce connection failures',
                    'priority': 'high'
                })
            
            # Check pool recycle time based on connection age
            max_checkout = self.pool_stats.get('max_checkout_time', 0)
            if max_checkout > 300:  # 5 minutes
                recommendations.append({
                    'setting': 'pool_recycle',
                    'current': 3600,
                    'recommended': 1800,  # 30 minutes
                    'reason': f'Long-running connections detected: {max_checkout:.1f}s',
                    'impact': 'Prevent stale connections',
                    'priority': 'low'
                })
            
            # Performance-based recommendations
            if len(self.checkout_times) > 100:
                # Analyze checkout time distribution
                sorted_times = sorted(self.checkout_times)
                p95_time = sorted_times[int(len(sorted_times) * 0.95)]
                
                if p95_time > 5:  # 95th percentile > 5 seconds
                    recommendations.append({
                        'setting': 'pool_size',
                        'current': status['pool_size'],
                        'recommended': min(50, status['pool_size'] + 5),
                        'reason': f'95th percentile checkout time: {p95_time:.2f}s',
                        'impact': 'Improve response time consistency',
                        'priority': 'medium'
                    })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to optimize pool settings: {e}")
            return []
    
    def health_check(self, engine):
        """Perform connection pool health check."""
        try:
            # Test basic connectivity
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.close()
            
            # Get pool status
            status = self.get_pool_status(engine)
            
            # Check for issues
            issues = []
            
            if status.get('utilization', 0) > 95:
                issues.append("Pool utilization is very high (>95%)")
            
            if self.pool_stats.get('connection_errors', 0) > 10:
                issues.append(f"High number of connection errors: {self.pool_stats['connection_errors']}")
            
            avg_checkout = self.pool_stats.get('avg_checkout_time', 0)
            if avg_checkout > 5:
                issues.append(f"High average checkout time: {avg_checkout:.2f}s")
            
            health_status = 'healthy' if not issues else 'warning' if len(issues) < 3 else 'critical'
            
            return {
                'status': health_status,
                'issues': issues,
                'pool_status': status,
                'recommendations': self.optimize_pool_settings(engine) if issues else []
            }
            
        except Exception as e:
            logger.error(f"Pool health check failed: {e}")
            return {
                'status': 'critical',
                'issues': [f"Health check failed: {str(e)}"],
                'pool_status': {},
                'recommendations': []
            }


class ConnectionLeakDetector:
    """Detect and prevent database connection leaks."""
    
    def __init__(self):
        self.active_connections = {}
        self.leak_threshold = 300  # 5 minutes
        self.lock = Lock()
    
    def track_connection(self, connection_id, context=None):
        """Track an active connection."""
        with self.lock:
            self.active_connections[connection_id] = {
                'created_at': time.time(),
                'context': context or 'unknown',
                'stack_trace': self._get_stack_trace()
            }
    
    def release_connection(self, connection_id):
        """Release a tracked connection."""
        with self.lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
    
    def detect_leaks(self):
        """Detect potential connection leaks."""
        current_time = time.time()
        leaks = []
        
        with self.lock:
            for conn_id, info in self.active_connections.items():
                age = current_time - info['created_at']
                
                if age > self.leak_threshold:
                    leaks.append({
                        'connection_id': conn_id,
                        'age_seconds': age,
                        'context': info['context'],
                        'stack_trace': info['stack_trace']
                    })
        
        if leaks:
            logger.warning(f"Detected {len(leaks)} potential connection leaks")
            for leak in leaks:
                logger.warning(f"Leak: {leak['connection_id']} (age: {leak['age_seconds']:.1f}s)")
        
        return leaks
    
    def _get_stack_trace(self):
        """Get current stack trace for debugging."""
        import traceback
        return traceback.format_stack()[-5:]  # Last 5 frames


# Global instances
pool_manager = ConnectionPoolManager()
leak_detector = ConnectionLeakDetector()


def init_connection_pooling(app):
    """Initialize optimized connection pooling."""
    
    # Get environment
    environment = app.config.get('ENV', 'development')
    database_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    
    if not database_uri:
        logger.warning("No database URI configured")
        return
    
    # Create optimized engine
    try:
        optimized_engine = pool_manager.create_optimized_engine(database_uri, environment)
        
        # Store optimized engine for later use
        # Instead of trying to set db.engine directly (which is read-only),
        # we'll store it in the app context for use by the database
        from models import db
        
        # Store the optimized engine in the app's extensions
        app.extensions['optimized_engine'] = optimized_engine
        
        # Update the SQLAlchemy configuration with optimized settings
        # The engine will be created with these settings when db.init_app() is called
        pool_config = pool_manager.get_optimal_pool_config(database_uri, environment)
        
        # Apply pool configuration to SQLAlchemy config
        app.config.update({
            'SQLALCHEMY_ENGINE_OPTIONS': pool_config
        })
        
        logger.info("Database connection pooling optimized")
        
        # Set up periodic health checks
        if environment == 'production':
            import threading
            import time
            
            def periodic_health_check():
                while True:
                    time.sleep(300)  # Check every 5 minutes
                    try:
                        with app.app_context():
                            engine = db.get_engine()
                            if engine:
                                health = pool_manager.health_check(engine)
                                if health['status'] != 'healthy':
                                    logger.warning(f"Pool health check: {health['status']}")
                                    for issue in health['issues']:
                                        logger.warning(f"Pool issue: {issue}")
                    except Exception as e:
                        logger.error(f"Health check error: {e}")
            
            health_thread = threading.Thread(target=periodic_health_check, daemon=True)
            health_thread.start()
        
    except Exception as e:
        logger.error(f"Failed to initialize connection pooling: {e}")


def get_pool_metrics():
    """Get connection pool metrics for monitoring."""
    try:
        from models import db
        
        engine = db.get_engine()
        if engine:
            status = pool_manager.get_pool_status(engine)
            health = pool_manager.health_check(engine)
            leaks = leak_detector.detect_leaks()
            
            return {
                'pool_status': status,
                'health': health,
                'potential_leaks': len(leaks),
                'leak_details': leaks[:5]  # First 5 leaks
            }
        else:
            return {'error': 'Database engine not available'}
            
    except Exception as e:
        logger.error(f"Failed to get pool metrics: {e}")
        return {'error': str(e)}
