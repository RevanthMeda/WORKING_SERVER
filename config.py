import os
import logging
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Application configuration class"""

    # Application settings
    APP_NAME = 'SAT Report Generator'
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = False  # Force disable debug mode for production performance
    
    # Domain security settings
    ALLOWED_DOMAINS = os.environ.get('ALLOWED_DOMAINS', '').split(',') if os.environ.get('ALLOWED_DOMAINS') else []
    SERVER_IP = os.environ.get('SERVER_IP', '')
    BLOCK_IP_ACCESS = os.environ.get('BLOCK_IP_ACCESS', 'False').lower() == 'true'

    # Security - Bulletproof CSRF settings with HTTPS
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here-change-in-production-sat-2025'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 86400  # 24 hours - very long timeout
    WTF_CSRF_SSL_STRICT = False  # More lenient for login compatibility
    WTF_CSRF_CHECK_DEFAULT = False  # More lenient CSRF checking
    
    # Session configuration - Force server-side sessions
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'sat_session:'
    SESSION_COOKIE_NAME = 'sat_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # Set to True when using HTTPS
    SEND_FILE_MAX_AGE_DEFAULT = 0  # Disable caching for static files

    # Dashboard stats caching
    ENABLE_DASHBOARD_STATS_CACHE = os.environ.get('ENABLE_DASHBOARD_STATS_CACHE', 'True').lower() == 'true'
    DASHBOARD_STATS_REFRESH_SECONDS = int(os.environ.get('DASHBOARD_STATS_REFRESH_SECONDS', 300))
    DASHBOARD_STATS_MAX_AGE_SECONDS = int(os.environ.get('DASHBOARD_STATS_MAX_AGE_SECONDS', 600))

    # AI assistance configuration
    AI_PROVIDER = os.environ.get('AI_PROVIDER', 'gemini')
    AI_ENABLED = os.environ.get('AI_ENABLED', '').lower() == 'true' or bool(os.environ.get('GEMINI_API_KEY'))
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-pro')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')


    
    # SSL/HTTPS Configuration
    SSL_CERT_PATH = r'E:\report generator\SERVER\ssl\mobilehmi.org2025.pfx'
    SSL_KEY_PATH = None  # Not needed for .pfx files
    SSL_CERT_PASSWORD = os.environ.get('SSL_CERT_PASSWORD', '')  # Password for .pfx file
    USE_HTTPS = True

    # Database - Use absolute path for SQLite
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(BASE_DIR, "instance", "sat_reports.db")}'

    # Optimized database settings for performance
    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': False,  # Disable for faster startup  
        'pool_recycle': 3600,   # Longer pool recycle
        'pool_size': 10,        # Connection pool size
        'max_overflow': 20,     # Max overflow connections
        'pool_timeout': 30,     # Connection timeout
    }

    # File upload settings
    UPLOAD_ROOT = os.path.join(BASE_DIR, 'static', 'uploads')
    SIGNATURES_FOLDER = os.path.join(BASE_DIR, 'static', 'signatures')

    # Output directory for generated reports
    OUTPUT_DIR = os.path.join(BASE_DIR, 'outputs')

    # Ensure directories exist
    os.makedirs(UPLOAD_ROOT, exist_ok=True)
    os.makedirs(SIGNATURES_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Email configuration - Dynamic loading (no caching)
    # Static config for server/port/username (these rarely change)
    SMTP_SERVER = os.environ.get('SMTP_SERVER') or 'smtp.gmail.com'
    SMTP_PORT = int(os.environ.get('SMTP_PORT') or 587)
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME') or ''
    DEFAULT_SENDER = os.environ.get('DEFAULT_SENDER') or ''
    
    # Dynamic password loading - always fresh from environment
    @staticmethod
    def get_smtp_credentials():
        """
        Always fetch fresh SMTP credentials from environment variables.
        This prevents password caching issues when credentials change.
        """
        import os
        from dotenv import load_dotenv
        
        # Force refresh environment variables
        smtp_password = os.environ.get('SMTP_PASSWORD', '')
        
        # If not found in environment, try .env file (for local development)
        if not smtp_password:
            load_dotenv(override=True)
            smtp_password = os.environ.get('SMTP_PASSWORD', '')
        
        print(f"🔄 Fresh SMTP credentials loaded - Password length: {len(smtp_password)}")
        if smtp_password:
            print(f"🔐 Password: {smtp_password[:4]}...{smtp_password[-4:]}")
        
        return {
            'server': Config.SMTP_SERVER,
            'port': Config.SMTP_PORT,
            'username': Config.SMTP_USERNAME,
            'password': smtp_password,
            'sender': Config.DEFAULT_SENDER
        }

    # PDF export
    ENABLE_PDF_EXPORT = os.environ.get('ENABLE_PDF_EXPORT', 'False').lower() == 'true'

    # Default approvers configuration
    DEFAULT_APPROVERS = [
        {
            "stage": 1,
            "title": "Automation Manager",
            "approver_email": "tm@cullyautomation.com"
        },
        {
            "stage": 2,
            "title": "Project Manager",
            "approver_email": "pm@cullyautomation.com"
        }
    ]

    # Max content length (16MB default)
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', '16777216'))

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'}

    # Template file for SAT reports
    TEMPLATE_FILE = os.getenv('TEMPLATE_FILE', 'templates/SAT_Template.docx')
    OUTPUT_FILE = os.getenv('OUTPUT_FILE', 'outputs/SAT_Report_Final.docx')

    # Feature Flags
    ENABLE_EMAIL_NOTIFICATIONS = os.getenv('ENABLE_EMAIL_NOTIFICATIONS', 'True').lower() == 'true'
    
    # Redis caching configuration
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
    REDIS_DB = int(os.environ.get('REDIS_DB', '0'))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_SSL = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
    REDIS_SSL_CERT_REQS = os.environ.get('REDIS_SSL_CERT_REQS', 'required')
    REDIS_SSL_CA_CERTS = os.environ.get('REDIS_SSL_CA_CERTS')
    REDIS_SSL_CERTFILE = os.environ.get('REDIS_SSL_CERTFILE')
    REDIS_SSL_KEYFILE = os.environ.get('REDIS_SSL_KEYFILE')
    REDIS_SOCKET_TIMEOUT = int(os.environ.get('REDIS_SOCKET_TIMEOUT', '5'))
    REDIS_SOCKET_CONNECT_TIMEOUT = int(os.environ.get('REDIS_SOCKET_CONNECT_TIMEOUT', '5'))
    REDIS_SOCKET_KEEPALIVE = os.environ.get('REDIS_SOCKET_KEEPALIVE', 'true').lower() == 'true'
    REDIS_MAX_CONNECTIONS = int(os.environ.get('REDIS_MAX_CONNECTIONS', '50'))
    REDIS_REQUIRED = os.environ.get('REDIS_REQUIRED', 'false').lower() == 'true'
    
    # Cache timeout settings (in seconds)
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', '3600'))  # 1 hour
    SESSION_CACHE_TIMEOUT = int(os.environ.get('SESSION_CACHE_TIMEOUT', '86400'))  # 24 hours
    API_CACHE_TIMEOUT = int(os.environ.get('API_CACHE_TIMEOUT', '300'))  # 5 minutes
    QUERY_CACHE_TIMEOUT = int(os.environ.get('QUERY_CACHE_TIMEOUT', '600'))  # 10 minutes

    # Security Settings - Updated for HTTPS
    SESSION_COOKIE_SECURE = True  # Require HTTPS for session cookies
    SESSION_COOKIE_HTTPONLY = True  # Standard security
    SESSION_COOKIE_SAMESITE = 'Lax'  # Allow cross-site cookies for external domain access
    SESSION_COOKIE_DOMAIN = None  # Let Flask handle domain automatically
    
    # Session Management - Auto-logout after 30 minutes of inactivity
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)  # Auto-logout after 30 min inactivity
    REMEMBER_COOKIE_DURATION = timedelta(minutes=30)  # "Remember me" expiry
    SESSION_REFRESH_EACH_REQUEST = True  # Refresh expiry on every request

    @staticmethod
    def init_app(app):
        """Initialize app-specific configuration"""
        pass

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///sat_reports_dev.db')

class ProductionConfig(Config):
    """Production configuration for domain-only access"""
    DEBUG = False
    # PORT is inherited from Config class (uses environment variable)
    SESSION_COOKIE_SECURE = True
    
    # Production domain security
    ALLOWED_DOMAINS = ['automation-reports.mobilehmi.org']
    SERVER_IP = '172.16.18.21'
    BLOCK_IP_ACCESS = True
    
    # Enhanced security for production
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)  # Auto-logout after 30 min inactivity
    REMEMBER_COOKIE_DURATION = timedelta(minutes=30)  # "Remember me" expiry
    
    # Production database (use PostgreSQL)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{os.path.join(Config.BASE_DIR, "instance", "sat_reports_prod.db")}'
    
    @staticmethod
    def init_app(app):
        Config.init_app(app)

        # Enhanced logging for production
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler('logs/sat_reports.log', maxBytes=10240000, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('SAT Report Generator startup - Production Mode')

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
