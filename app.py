import os
import sys
import signal
import logging
import traceback
import importlib.util
from flask import Flask, g, request, render_template, jsonify, make_response, redirect, url_for, session, flash
from flask_wtf.csrf import CSRFProtect, generate_csrf, CSRFError
from flask_login import current_user, login_required
from flask_session import Session
from typing import Optional, Any

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
from middleware import init_security_middleware
from middleware_optimized import init_optimized_middleware
from session_manager import session_manager
from services.storage_manager import StorageSettingsService, StorageSettingsError

# Initialize CSRF protection globally
csrf = CSRFProtect()

# Import only essential modules - lazy load others
try:
    from models import db, User, init_db
    from auth import init_auth
    from session_manager import session_manager
    # Lazy import blueprints to reduce startup time
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def create_app(config_name='default'):
    """Create and configure Flask application"""
    app = Flask(__name__)
    
    # Load configuration based on environment
    config_class = config.get(config_name, config['default'])
    app.config.from_object(config_class)
    
    # Initialize hierarchical configuration system
    try:
        config_manager = init_config_system(app)
        app.logger.info("Hierarchical configuration system initialized")
    except Exception as e:
        app.logger.error(f"Failed to initialize config system: {e}")
        # Continue with basic config if hierarchical config fails
    
    # Initialize secrets management system
    try:
        secrets_manager = init_secrets_management(app)
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
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = 'instance/flask_session'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_KEY_PREFIX'] = 'sat:'
    app.config['SESSION_COOKIE_NAME'] = 'sat_session'
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = app.config.get('USE_HTTPS', False)
    app.config['SESSION_REFRESH_EACH_REQUEST'] = False

    # Initialize Flask-Session for server-side session storage
    Session(app)

    # Initialize database and auth
    try:
        db_initialized = init_db(app)
        if not db_initialized:
            app.logger.warning("Database initialization returned False")


        init_auth(app)

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
            init_connection_pooling, init_backup_system
        )
        from database.cli import register_db_commands
        migration_manager = init_migrations(app)
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

    # Configure logging levels for cleaner output
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('database.pooling').setLevel(logging.INFO)
    logging.getLogger('database.performance').setLevel(logging.INFO)
    logging.getLogger('cache.redis_client').setLevel(logging.INFO)
    logging.getLogger('cache.cdn').setLevel(logging.INFO)
    # Suppress deprecation warnings from Flask and third-party libraries
    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning)
    warnings.filterwarnings('ignore', message="'FLASK_ENV' is deprecated")

    # Add CSRF token to g for access in templates and manage session
    @app.before_request
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

    @app.route('/refresh_csrf')
    def refresh_csrf():
        """Refresh CSRF token via AJAX"""
        return jsonify({'csrf_token': generate_csrf()})

    # API endpoint to check authentication status
    @app.route('/api/check-auth')
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
    
    # API endpoint for getting users by role
    @app.route('/api/get-users-by-role')
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

    # Custom CSRF error handler
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
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

    # Root route - redirect to welcome or dashboard
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.home'))
        return redirect(url_for('auth.welcome'))

    # Legacy redirects
    @app.route('/sat_form')
    def legacy_sat_form():
        return redirect(url_for('reports.new'))

    @app.route('/sat')
    @app.route('/sat/start')
    def legacy_sat():
        return redirect(url_for('reports.new_sat'))

    @app.route('/generate_sat')
    def legacy_generate_sat():
        return redirect(url_for('reports.new_sat'))

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
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('404.html'), 500

    @app.errorhandler(400)
    def csrf_error(error):
        """Handle CSRF token errors"""
        return render_template('csrf_error.html'), 400

    # 404 Error handler
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    # Minimal response logging for performance
    @app.after_request
    def log_response(response):
        return response

    if not db_initialized:
        app.logger.warning("Database initialization failed - running without database")

    return app

def sigint_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\nShutting down server...")
    sys.exit(0)

if __name__ == '__main__':
    # Set up signal handling
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGTERM, sigint_handler)

    try:
        print("Initializing SAT Report Generator...")
        
        # Determine environment
        flask_env = os.environ.get('FLASK_ENV', 'development')
        config_name = 'production' if flask_env == 'production' else 'development'
        
        # Create the app with appropriate configuration
        app = create_app(config_name)
        
        # Log security status for production
        if config_name == 'production':
            print("Production mode: Domain security enabled")
            print(f"Allowed domain: {app.config.get('ALLOWED_DOMAINS', [])}")
            print(f"IP access blocking: {app.config.get('BLOCK_IP_ACCESS', False)}")

        # Print startup information
        print(f"Starting {app.config.get('APP_NAME', 'SAT Report Generator')}...")
        print(f"Debug Mode: {app.config.get('DEBUG', False)}")
        protocol = "http"  # Temporarily using HTTP for testing
        print(f"Running on {protocol}://0.0.0.0:{app.config.get('PORT', 5000)}")
        print("Testing with HTTP - SSL disabled temporarily")

        # Create required directories if they don't exist
        try:
            upload_root = app.config.get('UPLOAD_ROOT', 'static/uploads')
            signatures_folder = app.config.get('SIGNATURES_FOLDER', 'static/signatures')
            submissions_file = app.config.get('SUBMISSIONS_FILE', 'data/submissions.json')

            os.makedirs(upload_root, exist_ok=True)
            os.makedirs(signatures_folder, exist_ok=True)
            os.makedirs(os.path.dirname(submissions_file), exist_ok=True)
            os.makedirs('instance', exist_ok=True)
            os.makedirs('logs', exist_ok=True)
            # Ensure upload directory exists
            upload_dir = app.config.get('UPLOAD_FOLDER')
            if upload_dir and not os.path.exists(upload_dir):
                os.makedirs(upload_dir, exist_ok=True)

            # Ensure output directory exists
            output_dir = app.config.get('OUTPUT_DIR')
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            print("Required directories created successfully")
        except Exception as dir_error:
            print(f"Warning: Could not create some directories: {dir_error}")

        # Test a simple route to ensure app is working
        @app.route('/health')
        def health_check():
            try:
                # Test database connection
                from models import db
                with db.engine.connect() as connection:
                    connection.execute(db.text('SELECT 1'))
                db_status = 'connected'
            except Exception as e:
                app.logger.error(f"Database health check failed: {e}")
                db_status = 'disconnected'
            
            return jsonify({
                'status': 'healthy', 
                'message': 'SAT Report Generator is running',
                'database': db_status
            })

        print("Health check endpoint available at /health")

        # Run the server
        try:
            # Production server configuration
            host = '0.0.0.0'  # Bind to all interfaces
            port = app.config['PORT']
            debug = False  # Force debug off for performance
            
            if config_name == 'production':
                print(f"Starting production server on port {port}")
                print("Production mode: Use a WSGI server like Gunicorn for deployment")
            
            # Enable SSL/HTTPS for secure connections
            if app.config.get('USE_HTTPS', False):
                ssl_cert_path = app.config.get('SSL_CERT_PATH', '')
                
                # Check if it's a .pfx file (contains both cert and key)
                if ssl_cert_path.endswith('.pfx') and os.path.exists(ssl_cert_path):
                    try:
                        import ssl
                        from cryptography.hazmat.primitives import serialization
                        from cryptography.hazmat.primitives.serialization import pkcs12
                        import tempfile
                        
                        # Get password from config
                        cert_password = app.config.get('SSL_CERT_PASSWORD', '').encode() if app.config.get('SSL_CERT_PASSWORD') else None
                        
                        # Load the .pfx file
                        with open(ssl_cert_path, 'rb') as f:
                            pfx_data = f.read()
                        
                        # Parse the PKCS#12 file
                        private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                            pfx_data, cert_password
                        )
                        
                        # Create temporary files for cert and key
                        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem') as cert_file:
                            cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))
                            cert_temp_path = cert_file.name
                        
                        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.key') as key_file:
                            key_file.write(private_key.private_bytes(
                                encoding=serialization.Encoding.PEM,
                                format=serialization.PrivateFormat.PKCS8,
                                encryption_algorithm=serialization.NoEncryption()
                            ))
                            key_temp_path = key_file.name
                        
                        # Create optimized SSL context with extracted cert and key
                        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                        ssl_context.load_cert_chain(cert_temp_path, key_temp_path)
                        
                        # Performance optimizations for SSL (compatible with Flask dev server)
                        ssl_context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
                        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2  # Use modern method instead of deprecated options
                        ssl_context.options |= ssl.OP_SINGLE_DH_USE | ssl.OP_SINGLE_ECDH_USE
                        
                        print("HTTPS enabled with password-protected .pfx SSL certificate")
                        
                        # Clean up temporary files after loading
                        import atexit
                        def cleanup_temp_files():
                            try:
                                os.unlink(cert_temp_path)
                                os.unlink(key_temp_path)
                            except:
                                pass
                        atexit.register(cleanup_temp_files)
                        
                    except Exception as e:
                        print(f"Error loading .pfx certificate: {e}")
                        print("Make sure SSL_CERT_PASSWORD is set in your .env file")
                        ssl_context = None
                        print("Falling back to HTTP mode")
                # Check for separate cert and key files  
                elif (ssl_cert_path and os.path.exists(ssl_cert_path) and 
                      app.config.get('SSL_KEY_PATH') and os.path.exists(app.config.get('SSL_KEY_PATH', ''))):
                    ssl_context = (ssl_cert_path, app.config['SSL_KEY_PATH'])
                    print("HTTPS enabled with separate SSL certificate and key files")
                else:
                    ssl_context = None
                    print("SSL certificate not found - running in HTTP mode")
            else:
                ssl_context = None
                print("HTTPS disabled - running in HTTP mode")

            app.run(
                host=host,
                port=port,
                debug=False,  # Always disable debug for performance
                threaded=True,
                ssl_context=ssl_context,
                use_reloader=False,  # Disable reloader for performance
                processes=1,  # Single process for stability
                request_handler=None,  # Use default handler
                passthrough_errors=False  # Prevent hanging on errors
            )
        except OSError as e:
            if "Address already in use" in str(e):
                print("Port 5000 is already in use. Trying to kill existing processes...")
                import os
                os.system('pkill -f "python app.py"')
                import time
                time.sleep(2)
                print("Retrying on port 5000...")
                app.run(
                    host='0.0.0.0',
                    port=app.config['PORT'],
                    debug=app.config['DEBUG']
                )
            else:
                raise

    except Exception as e:
        print(f"Server startup failed: {e}")
        traceback.print_exc()
        sys.exit(1)

