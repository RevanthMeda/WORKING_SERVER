import os
import sys
import logging
import traceback
import importlib.util
from logging.handlers import RotatingFileHandler
from flask import Flask, g, request, render_template, jsonify, redirect, url_for, session, flash
from flask_wtf.csrf import CSRFProtect, generate_csrf, CSRFError
from flask_login import current_user, login_required
from flask_session import Session
from typing import Any, cast
from sqlalchemy import text

# Import Config directly from config.py file
config_file_path = os.path.join(os.path.dirname(__file__), 'config.py')
spec = importlib.util.spec_from_file_location("config_module", config_file_path)
if spec and spec.loader:
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
else:
    raise ImportError("Could not load config module")

# Now we can access Config and config from the file
Config = config_module.Config
config = config_module.config

# Import from config/ directory
from config.manager import init_config_system
from config.secrets import init_secrets_management
from middleware_optimized import init_optimized_middleware
from services.storage_manager import StorageSettingsService, StorageSettingsError
from session_manager import session_manager
from database.fix_missing_columns import ensure_database_ready

# Initialize CSRF protection globally
csrf = CSRFProtect()

# Type helper so static typing knows about dynamically-attached attributes
class _ExtendedFlask(Flask):
    cache: Any
    session_manager: Any
    query_cache: Any
    cdn_extension: Any
    celery: Any


def _resolve_directory(app: Flask, candidate: str | None, *, fallback: str) -> str:
    """Return an absolute directory path and ensure it exists."""
    target = candidate or fallback
    if not os.path.isabs(target):
        target = os.path.abspath(os.path.join(app.root_path, target))
    os.makedirs(target, exist_ok=True)
    return target


def _configure_logging(app: Flask) -> None:
    """Attach sensible logging handlers for production usage."""
    log_level_name = str(app.config.get('LOG_LEVEL', 'INFO')).upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    log_format = app.config.get('LOG_FORMAT', '[%(asctime)s] %(levelname)s in %(module)s: %(message)s')

    if not app.logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(log_format))
        stream_handler.setLevel(log_level)
        app.logger.addHandler(stream_handler)

        log_file_path = app.config.get('LOG_FILE_PATH')
        if log_file_path:
            max_bytes = int(app.config.get('LOG_FILE_MAX_BYTES', 10 * 1024 * 1024))
            backup_count = int(app.config.get('LOG_FILE_BACKUP_COUNT', 5))
            file_handler = RotatingFileHandler(log_file_path, maxBytes=max_bytes, backupCount=backup_count)
            file_handler.setFormatter(logging.Formatter(log_format))
            file_handler.setLevel(log_level)
            app.logger.addHandler(file_handler)

    app.logger.setLevel(log_level)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


def _ensure_required_directories(app: Flask) -> None:
    """Create directories relied upon by the application at runtime."""
    os.makedirs(app.instance_path, exist_ok=True)

    session_dir = _resolve_directory(
        app,
        app.config.get('SESSION_FILE_DIR'),
        fallback=os.path.join(app.instance_path, 'flask_session'),
    )
    app.config['SESSION_FILE_DIR'] = session_dir

    static_root = app.static_folder or os.path.join(app.root_path, 'static')
    upload_root = _resolve_directory(
        app,
        app.config.get('UPLOAD_ROOT'),
        fallback=os.path.join(static_root, 'uploads'),
    )
    app.config['UPLOAD_ROOT'] = upload_root

    signatures_dir = _resolve_directory(
        app,
        app.config.get('SIGNATURES_FOLDER'),
        fallback=os.path.join(static_root, 'signatures'),
    )
    app.config['SIGNATURES_FOLDER'] = signatures_dir

    output_dir = _resolve_directory(
        app,
        app.config.get('OUTPUT_DIR'),
        fallback=os.path.join(app.instance_path, 'outputs'),
    )
    app.config['OUTPUT_DIR'] = output_dir

    logs_dir = _resolve_directory(
        app,
        app.config.get('LOG_DIR'),
        fallback=os.path.join(app.instance_path, 'logs'),
    )
    app.config['LOG_DIR'] = logs_dir
    app.config.setdefault('LOG_FILE_PATH', os.path.join(logs_dir, 'application.log'))

    submissions_file = app.config.get('SUBMISSIONS_FILE', os.path.join(app.instance_path, 'data', 'submissions.json'))
    if not os.path.isabs(submissions_file):
        submissions_file = os.path.abspath(os.path.join(app.root_path, submissions_file))
    os.makedirs(os.path.dirname(submissions_file), exist_ok=True)
    app.config['SUBMISSIONS_FILE'] = submissions_file

    # Maintain compatibility with legacy configuration keys
    if app.config.get('UPLOAD_FOLDER'):
        app.config['UPLOAD_FOLDER'] = _resolve_directory(
            app,
            app.config['UPLOAD_FOLDER'],
            fallback=os.path.join(upload_root, 'legacy'),
        )


# Import only essential modules - lazy load others
try:
    from models import db, User, init_db
    from auth import init_auth
    # Lazy import blueprints to reduce startup time
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def create_app(config_name='default'):
    """Create and configure Flask application"""
    app: _ExtendedFlask = cast(_ExtendedFlask, Flask(__name__))
    
    # Load configuration based on environment
    config_class = config.get(config_name, config['default'])
    app.config.from_object(config_class)
    _ensure_required_directories(app)
    _configure_logging(app)
    
    # Initialize hierarchical configuration system
    try:
        _config_manager = init_config_system(app)
        app.logger.info("Hierarchical configuration system initialized")
    except Exception as e:
        app.logger.error(f"Failed to initialize config system: {e}")
        # Continue with basic config if hierarchical config fails
    
    # Initialize secrets management system
    try:
        _secrets_manager = init_secrets_management(app)
        app.logger.info("Secrets management system initialized")
    except Exception as e:
        app.logger.error(f"Failed to initialize secrets management: {e}")
        # Continue without secrets management if it fails
    
    # Initialize production security middleware
    # Temporarily disabled for remote access testing
    # if config_name == 'production':
    #     init_security_middleware(app)
    
    # Initialize extensions
    csrf.init_app(app)
    # Initialize optimized middleware
    init_optimized_middleware(app)
    
    # Configure server-side sessions
    app.config.setdefault('SESSION_TYPE', 'filesystem')
    app.config['SESSION_FILE_DIR'] = app.config['SESSION_FILE_DIR']
    app.config.setdefault('SESSION_PERMANENT', False)
    app.config.setdefault('SESSION_USE_SIGNER', True)
    app.config.setdefault('SESSION_KEY_PREFIX', 'sat:')
    app.config.setdefault('SESSION_COOKIE_NAME', 'sat_session')
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config.setdefault('SESSION_COOKIE_SECURE', app.config.get('USE_HTTPS', False))
    app.config.setdefault('SESSION_REFRESH_EACH_REQUEST', False)

    # Initialize Flask-Session for server-side session storage
    Session(app)

    # Initialize database and auth
    try:
        db_initialized = init_db(app)
        if not db_initialized:
            app.logger.warning("Database initialization returned False")


        init_auth(app)
        try:
            ensure_database_ready(app, db)
        except Exception as migration_error:
            app.logger.warning("Database consistency check encountered issues: %s", migration_error, exc_info=True)

        try:
            settings = StorageSettingsService.sync_app_config(app)
            app.logger.info(
                "Storage settings loaded for org=%s environment=%s (version=%s)",
                settings.org_id,
                settings.environment,
                settings.version,
            )
        except StorageSettingsError as storage_error:
            app.logger.error(f"Failed to load storage settings: {storage_error}")
        except Exception as unexpected_storage_error:
            app.logger.error(f"Unexpected error while loading storage settings: {unexpected_storage_error}")

        # Initialize migration system
        from database import (
            init_migrations, init_database_performance,
            init_connection_pooling
        )
        from database.cli import register_db_commands
        _migration_manager = init_migrations(app)
        register_db_commands(app)
        
        # Register task management CLI commands (optional)
        try:
            from tasks.cli import tasks
            if hasattr(app, 'cli'):
                app.cli.add_command(tasks)
                app.logger.debug("Task management CLI commands registered")
            else:
                app.logger.debug("Flask CLI not available, skipping task CLI registration")
        except ImportError:
            # Celery not installed - this is optional
            pass
        except Exception:
            # Task CLI is optional, silently skip if not available
            pass
        
        # Initialize performance optimizations only if needed
        # Skip for development to improve startup time
        if config_name == 'production':
            init_connection_pooling(app)
            init_database_performance(app)
            # Skip backup system on startup for performance
            # init_backup_system(app)  # Run manually when needed
        else:
            app.logger.debug("Skipping performance initialization in non-production")
        
        # Initialize Redis caching system
        try:
            from cache.redis_client import init_cache
            from cache.session_store import RedisSessionInterface, SessionManager
            
            # Initialize cache system
            init_cache(app)
            
            # Replace Flask-Session with Redis session interface if Redis is available
            if hasattr(app, 'cache') and app.cache.redis_client.is_available():
                app.session_interface = RedisSessionInterface(
                    redis_client=app.cache.redis_client,
                    key_prefix='session:',
                    use_signer=True,
                    permanent=True
                )
                app.session_manager = SessionManager(
                    app.cache.redis_client,
                    key_prefix='session:'
                )
                app.logger.debug("Redis session storage initialized")  # Reduced log level
            else:
                app.logger.debug("Using filesystem sessions (Redis not available)")  # Reduced log level
            
            # Initialize cache monitoring
            from cache.monitoring import init_cache_monitoring
            init_cache_monitoring(app)
            
            app.logger.debug("Cache system initialized successfully")  # Reduced log level
        except Exception as e:
            app.logger.error(f"Failed to initialize cache system: {e}")
            # Continue without caching if it fails
        
        # Initialize query caching system
        try:
            from database.query_cache import init_query_cache
            
            # Initialize query cache with Redis client
            if hasattr(app, 'cache') and app.cache.redis_client.is_available():
                query_cache_manager = init_query_cache(app.cache.redis_client, db)
                app.query_cache = query_cache_manager
                app.logger.debug("Query caching system initialized")  # Reduced log level
            else:
                app.logger.debug("Query caching disabled (Redis not available)")
        except Exception as e:
            app.logger.error(f"Failed to initialize query caching: {e}")
        
        # Initialize CDN integration
        try:
            from cache.flask_cdn import create_cdn_extension
            
            # Create and initialize CDN extension
            cdn_extension = create_cdn_extension(app)
            app.cdn_extension = cdn_extension
            
            app.logger.debug("CDN integration initialized")  # Reduced log level
        except ImportError:
            # CDN dependencies not installed - this is optional
            app.logger.debug("CDN integration not available (missing dependencies)")
            app.cdn_extension = None
        except AttributeError:
            # Handle Flask CLI issues with AppGroup
            app.logger.debug("CDN integration skipped (Flask CLI issue)")
            app.cdn_extension = None
        except Exception:
            # CDN is optional
            app.logger.debug("CDN integration disabled (optional feature)")
            app.cdn_extension = None
        
        # Initialize background task processing with Celery
        try:
            # Check if Redis is available first
            redis_available = False
            if hasattr(app, 'cache') and hasattr(app.cache, 'redis_client'):
                redis_available = app.cache.redis_client.is_available()
            
            if redis_available:
                from tasks.celery_app import init_celery
                
                # Initialize Celery for background tasks
                celery_app = init_celery(app)
                app.celery = celery_app
                
                app.logger.info("Background task processing (Celery) initialized")
            else:
                app.logger.debug("Background task processing disabled (Redis not available)")
                app.celery = None
        except ImportError:
            # Celery not installed - this is optional
            app.logger.debug("Background task processing not available (Celery not installed)")
            app.celery = None
        except AttributeError:
            # Celery initialization issue - optional feature
            app.logger.debug("Background task processing disabled (Celery initialization issue)")
            app.celery = None
        except Exception:
            # Background tasks are optional
            app.logger.debug("Background task processing disabled (optional feature)")
            app.celery = None
        
        app.logger.info("Database, auth, migrations, performance, backup, and cache systems initialized")
    except Exception as e:
        app.logger.error(f"Failed to initialize database or auth: {e}")
        traceback.print_exc()
        db_initialized = False

    app.config['DB_INITIALIZED'] = db_initialized

    # Suppress deprecation warnings from Flask and third-party libraries
    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    warnings.filterwarnings('ignore', message="'FLASK_ENV' is deprecated")

    # Add CSRF token to g for access in templates and manage session
    def add_csrf_token():
        import time

        g.request_time = time.time()

        public_endpoints = ['auth.login', 'auth.register', 'auth.welcome', 'auth.logout',
                            'auth.forgot_password', 'auth.reset_password', 'static',
                            'index', 'refresh_csrf', 'health', 'check_auth']

        endpoint = request.endpoint or ''
        is_public = not endpoint or endpoint in public_endpoints
        user_authenticated = current_user.is_authenticated

        session_valid = None
        if (not is_public) or user_authenticated:
            session_valid = session_manager.is_session_valid()

        if not is_public:
            if session_valid is False:
                from flask_login import logout_user
                logout_user()
                session.clear()
                session.permanent = False

                if request.is_json or 'application/json' in request.headers.get('Accept', ''):
                    return jsonify({'error': 'Session expired', 'authenticated': False}), 401

                flash('Your session has expired. Please log in again.', 'info')
                return redirect(url_for('auth.welcome'))

            if not user_authenticated:
                session.clear()
                session.permanent = False

                if request.is_json or 'application/json' in request.headers.get('Accept', ''):
                    return jsonify({'error': 'Not authenticated', 'authenticated': False}), 401

                return redirect(url_for('auth.welcome'))

            if 'user_id' not in session or session.get('user_id') != current_user.id:
                from flask_login import logout_user
                session_manager.revoke_session()
                logout_user()
                session.clear()
                return redirect(url_for('auth.welcome'))

        elif user_authenticated and session_valid is False:
            from flask_login import logout_user
            logout_user()
            session.clear()
            session.permanent = False

        session.permanent = False

        token = generate_csrf()
        g.csrf_token = token

        try:
            db.session.close()
        except Exception:
            pass

    app.before_request(add_csrf_token)

    def refresh_csrf():
        """Refresh CSRF token via AJAX"""
        return jsonify({'csrf_token': generate_csrf()})

    app.add_url_rule('/refresh_csrf', 'refresh_csrf', refresh_csrf, methods=['GET'])

    # API endpoint to check authentication status
    def check_auth():
        """Check if user is authenticated and session is valid"""
        # First check if session is valid
        if not session_manager.is_session_valid():
            return jsonify({'authenticated': False, 'reason': 'Session invalid or expired'}), 401
        
        # Then check Flask-Login authentication
        if current_user.is_authenticated:
            return jsonify({'authenticated': True, 'user': current_user.email}), 200
        else:
            return jsonify({'authenticated': False, 'reason': 'Not logged in'}), 401
    
    app.add_url_rule('/api/check-auth', 'check_auth', check_auth, methods=['GET'])

    # API endpoint for getting users by role
    @login_required
    def get_users_by_role():
        """API endpoint to get users by role for dropdowns"""
        try:
            # Only get active users
            users = User.query.filter_by(status='Active').all()
            users_by_role = {
                'Admin': [],
                'Engineer': [],
                'Automation Manager': [],
                'PM': []
            }

            for user in users:
                user_data = {
                    'name': user.full_name,
                    'email': user.email
                }

                # Map database roles to frontend role categories
                if user.role == 'Admin':
                    users_by_role['Admin'].append(user_data)
                elif user.role == 'Engineer':
                    users_by_role['Engineer'].append(user_data)
                elif user.role in ['Automation Manager']:
                    users_by_role['Automation Manager'].append(user_data)
                elif user.role in ['PM', 'Project Manager', 'Project_Manager']:
                    users_by_role['PM'].append(user_data)

            app.logger.info(f"Found {len(users)} total users")
            app.logger.info(f"Users by role: Automation Manager={len(users_by_role['Automation Manager'])}, PM={len(users_by_role['PM'])}, Admin={len(users_by_role['Admin'])}, Engineer={len(users_by_role['Engineer'])}")

            return jsonify({'success': True, 'users': users_by_role})
        except Exception as e:
            app.logger.error(f"Error in get_users_by_role endpoint: {e}")
            return jsonify({'success': False, 'error': 'Unable to fetch users at this time'}), 500
    app.add_url_rule('/api/get-users-by-role', 'get_users_by_role', get_users_by_role, methods=['GET'])

    def health_check():
        """Lightweight readiness probe."""
        status = 'ok'
        db_status = 'disabled'

        if app.config.get('DB_INITIALIZED'):
            try:
                db.session.execute(text('SELECT 1'))
                db_status = 'connected'
            except Exception as exc:
                app.logger.error("Database health check failed: %s", exc)
                db_status = 'error'
                status = 'degraded'

        return jsonify(
            {
                'status': status,
                'application': app.config.get('APP_NAME', 'SAT Report Generator'),
                'database': db_status,
            }
        ), 200 if status == 'ok' else 503

    app.add_url_rule('/health', 'health_check', health_check, methods=['GET'])

    # Custom CSRF error handler
    def handle_csrf_error(e: CSRFError):
        app.logger.error(f"CSRF Error occurred: {str(e)}")
        app.logger.error(f"Request Method: {request.method}")
        app.logger.error(f"Request Form Keys: {list(request.form.keys()) if request.form else []}")
        app.logger.error(f"CSRF Token Submitted: {request.form.get('csrf_token') if request.form else 'No form data'}")

        # For AJAX requests, return JSON error
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'error': 'CSRF token expired',
                'message': 'Please refresh the page and try again',
                'csrf_token': generate_csrf()
            }), 400

        # Ensure we have a CSRF token for the error page
        if not hasattr(g, 'csrf_token'):
            g.csrf_token = generate_csrf()

        return render_template('csrf_error.html', reason=str(e)), 400

    app.register_error_handler(CSRFError, handle_csrf_error)

    # Root route - redirect to welcome or dashboard
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.home'))
        return redirect(url_for('auth.welcome'))

    app.add_url_rule('/', 'index', index, methods=['GET'])

    # Legacy redirects
    def legacy_sat_form():
        return redirect(url_for('reports.new'))

    def legacy_sat():
        return redirect(url_for('reports.new_sat'))

    def legacy_generate_sat():
        return redirect(url_for('reports.new_sat'))

    app.add_url_rule('/sat_form', 'legacy_sat_form', legacy_sat_form, methods=['GET'])
    app.add_url_rule('/sat', 'legacy_sat', legacy_sat, methods=['GET'])
    app.add_url_rule('/sat/start', 'legacy_sat_start', legacy_sat, methods=['GET'])
    app.add_url_rule('/generate_sat', 'legacy_generate_sat', legacy_generate_sat, methods=['GET'])

    # Lazy import and register blueprints for faster startup
    def register_blueprints():
        from routes.auth import auth_bp
        from routes.dashboard import dashboard_bp
        from routes.reports import reports_bp
        from routes.notifications import notifications_bp
        from routes.io_builder import io_builder_bp
        from routes.main import main_bp
        from routes.approval import approval_bp
        from routes.status import status_bp
        from routes.templates import templates_bp
        from routes.compare import compare_bp
        from routes.webhooks import webhooks_bp
        from routes.collaboration import collaboration_bp
        from routes.search import search_bp
        from routes.bulk import bulk_bp
        from routes.audit import audit_bp
        from routes.analytics import analytics_bp
        from routes.bot import bot_bp
        from routes.ai import ai_bp
        from routes.edit import edit_bp
        from routes.mcp import mcp_bp
        from routes.test_download import test_download_bp
        from routes.intelligent_search import search_bp as intelligent_search_bp
        
        # Import new RESTful API
        from api import api_bp as restful_api_bp
        
        # Import legacy API (will be deprecated)
        from routes.api import api_bp as legacy_api_bp

        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
        app.register_blueprint(reports_bp, url_prefix='/reports')
        app.register_blueprint(notifications_bp, url_prefix='/notifications')
        app.register_blueprint(io_builder_bp, url_prefix='/io-builder')
        app.register_blueprint(main_bp)
        app.register_blueprint(approval_bp, url_prefix='/approve')
        app.register_blueprint(status_bp, url_prefix='/status')
        app.register_blueprint(templates_bp, url_prefix='/templates')
        app.register_blueprint(compare_bp, url_prefix='/compare')
        app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
        app.register_blueprint(collaboration_bp, url_prefix='/collaboration')
        app.register_blueprint(search_bp, url_prefix='/search')
        app.register_blueprint(bulk_bp, url_prefix='/bulk')
        app.register_blueprint(audit_bp, url_prefix='/audit')
        app.register_blueprint(analytics_bp, url_prefix='/analytics')
        app.register_blueprint(bot_bp, url_prefix='/bot')
        app.register_blueprint(edit_bp, url_prefix='/edit')
        app.register_blueprint(ai_bp)
        app.register_blueprint(mcp_bp)
        app.register_blueprint(test_download_bp)
        app.register_blueprint(intelligent_search_bp)
        
        # Register new RESTful API at /api/v1
        app.register_blueprint(restful_api_bp)
        
        # Register legacy API at /api/legacy (for backward compatibility)
        app.register_blueprint(legacy_api_bp, url_prefix='/api/legacy')
        
        # Register CDN management blueprint if CDN extension is available
        if hasattr(app, 'cdn_extension') and app.cdn_extension:
            try:
                from cache.flask_cdn import CDNBlueprint
                cdn_blueprint_manager = CDNBlueprint(app.cdn_extension)
                cdn_bp = cdn_blueprint_manager.create_blueprint()
                app.register_blueprint(cdn_bp)
                app.logger.info("CDN management blueprint registered")
            except Exception as e:
                app.logger.error(f"Failed to register CDN blueprint: {e}")

    register_blueprints()

    if db_initialized and app.config.get('ENABLE_DASHBOARD_STATS_CACHE', True):
        try:
            from services.dashboard_stats import start_dashboard_stats_refresher
            start_dashboard_stats_refresher(app)
        except Exception as e:
            app.logger.error(f"Failed to start dashboard stats refresher: {e}")
    else:
        app.logger.debug('Dashboard stats cache disabled or database not initialized; skipping refresher thread')

    # Error handlers
    def not_found_error(error):
        return render_template('404.html'), 404

    def internal_error(error):
        db.session.rollback()
        return render_template('404.html'), 500

    def csrf_error(error):
        """Handle CSRF token errors"""
        return render_template('csrf_error.html'), 400

    app.register_error_handler(404, not_found_error)
    app.register_error_handler(500, internal_error)
    app.register_error_handler(400, csrf_error)

    # Minimal response logging for performance
    def log_response(response):
        return response

    app.after_request(log_response)

    if not db_initialized:
        app.logger.warning("Database initialization failed - running without database")

    return app


APP_CONFIG_NAME = os.getenv('FLASK_CONFIG_NAME', os.getenv('FLASK_ENV', 'production') or 'production')
app = create_app(APP_CONFIG_NAME)


def _build_ssl_context(app: Flask) -> Any:
    if not app.config.get('USE_HTTPS', False):
        return None

    cert_path = app.config.get('SSL_CERT_PATH')
    key_path = app.config.get('SSL_KEY_PATH')

    if cert_path and key_path and os.path.exists(cert_path) and os.path.exists(key_path):
        return cert_path, key_path

    if cert_path and cert_path.endswith('.pfx') and os.path.exists(cert_path):
        try:
            import ssl
            import tempfile
            import atexit
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.serialization import pkcs12

            password = app.config.get('SSL_CERT_PASSWORD')
            with open(cert_path, 'rb') as cert_file:
                private_key, certificate, _ca = pkcs12.load_key_and_certificates(
                    cert_file.read(),
                    password.encode() if password else None,
                )

            if not private_key or not certificate:
                app.logger.error("PFX certificate is missing key or certificate entries.")
                return None

            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as cert_tmp:
                cert_tmp.write(certificate.public_bytes(serialization.Encoding.PEM))
                cert_tmp_path = cert_tmp.name

            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.key') as key_tmp:
                key_tmp.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )
                key_tmp_path = key_tmp.name

            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.load_cert_chain(cert_tmp_path, key_tmp_path)

            ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
            ssl_context.options |= ssl.OP_SINGLE_DH_USE | ssl.OP_SINGLE_ECDH_USE

            def _cleanup() -> None:
                for path in (cert_tmp_path, key_tmp_path):
                    try:
                        os.unlink(path)
                    except FileNotFoundError:
                        pass

            atexit.register(_cleanup)
            return ssl_context
        except Exception as exc:
            app.logger.error("Failed to load PFX certificate: %s", exc, exc_info=True)
            return None

    app.logger.warning("USE_HTTPS enabled but certificate files not found or invalid.")
    return None


if __name__ == '__main__':
    host = os.getenv('FLASK_RUN_HOST', app.config.get('HOST', '0.0.0.0'))
    port = int(os.getenv('FLASK_RUN_PORT', app.config.get('PORT', 5000)))
    debug = bool(app.config.get('DEBUG', False) or os.getenv('FLASK_ENV') == 'development')

    ssl_context = _build_ssl_context(app)
    scheme = 'https' if ssl_context else 'http'

    app.logger.info("Starting Flask development server on %s://%s:%s", scheme, host, port)
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=debug,
        ssl_context=ssl_context,
        threaded=True,
    )
