"""
RESTful API package for SAT Report Generator.
"""
from flask import Blueprint
from flask_restx import Api

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Initialize Flask-RESTX API with comprehensive documentation
api = Api(
    api_bp,
    version='1.0.0',
    title='SAT Report Generator API',
    description='''
    ## Enterprise RESTful API for SAT Report Generator
    
    This API provides comprehensive access to the SAT Report Generator system, enabling:
    
    ### Features
    - **Report Management**: Create, read, update, and delete SAT reports
    - **User Management**: User registration, authentication, and role-based access control
    - **File Operations**: Upload and manage report attachments and images
    - **Approval Workflows**: Multi-stage report approval processes
    - **Audit Logging**: Comprehensive audit trails for compliance
    - **Real-time Notifications**: WebSocket-based notifications for report updates
    
    ### Authentication
    This API supports multiple authentication methods:
    - **JWT Bearer Tokens**: For web applications and mobile clients
    - **API Keys**: For server-to-server integrations
    - **Session-based**: For web browser sessions
    
    ### Rate Limiting
    API endpoints are rate-limited to ensure fair usage:
    - **Authenticated users**: 1000 requests per hour
    - **API keys**: Configurable per key
    - **Anonymous**: 100 requests per hour
    
    ### Versioning
    This API uses URL-based versioning. Current version is v1.
    Future versions will be available at `/api/v2/`, etc.
    
    ### Error Handling
    All errors follow RFC 7807 Problem Details format with consistent structure:
    ```json
    {
      "error": {
        "message": "Human readable error message",
        "status_code": 400,
        "code": "ERROR_CODE",
        "details": {},
        "timestamp": "2023-01-01T00:00:00Z",
        "path": "/api/v1/reports"
      }
    }
    ```
    
    ### Pagination
    List endpoints support cursor-based pagination:
    - `page`: Page number (default: 1)
    - `per_page`: Items per page (default: 20, max: 100)
    - `sort_by`: Sort field (default: created_at)
    - `sort_order`: Sort direction (asc/desc, default: desc)
    
    ### Filtering and Search
    Most list endpoints support filtering and full-text search:
    - `search`: Full-text search across relevant fields
    - `status`: Filter by status
    - `created_by`: Filter by creator (admin only)
    - Date range filters where applicable
    
    ### Compliance
    This API is designed to meet enterprise compliance requirements:
    - **SOC 2 Type II**: Security and availability controls
    - **GDPR**: Data protection and privacy rights
    - **HIPAA**: Healthcare data protection (where applicable)
    - **ISO 27001**: Information security management
    
    ### Support
    For API support, please contact: api-support@satreportgenerator.com
    
    ### Changelog
    - **v1.0.0**: Initial release with core functionality
    ''',
    doc='/docs/',
    contact='API Support Team',
    contact_email='api-support@satreportgenerator.com',
    license='Proprietary',
    license_url='https://satreportgenerator.com/license',
    terms_url='https://satreportgenerator.com/terms',
    authorizations={
        'Bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization',
            'description': '''
            JWT Bearer token authentication.
            
            **Format**: `Bearer <jwt_token>`
            
            **Example**: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
            
            **Obtaining a token**: Use the `/auth/login` endpoint
            
            **Token expiration**: Tokens expire after 1 hour
            
            **Refresh**: Use `/auth/token/refresh` to get a new token
            '''
        },
        'ApiKey': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-Key',
            'description': '''
            API Key authentication for server-to-server integrations.
            
            **Format**: `X-API-Key: <api_key>`
            
            **Example**: `X-API-Key: sk_live_1234567890abcdef`
            
            **Obtaining an API key**: Contact your system administrator
            
            **Rate limits**: Configurable per key
            
            **Permissions**: Scoped to specific operations
            '''
        }
    },
    security=['Bearer'],
    validate=True,
    ordered=True
)

# Register error handlers
from api.errors import register_error_handlers, create_error_models
register_error_handlers(api)
error_models = create_error_models(api)

# Set up versioning
from api.versioning import add_version_headers

@api_bp.after_request
def add_api_version_headers(response):
    """Add version headers to all API responses."""
    return add_version_headers(response)

# Import and register namespaces
from api.auth import auth_ns
from api.users import users_ns
from api.reports import reports_ns
from api.files import files_ns
from api.admin import admin_ns
from api.documentation import docs_ns
from api.keys import keys_ns
from api.database import db_ns
from api.config import config_ns

api.add_namespace(auth_ns, path='/auth')
api.add_namespace(users_ns, path='/users')
api.add_namespace(reports_ns, path='/reports')
api.add_namespace(files_ns, path='/files')
api.add_namespace(admin_ns, path='/admin')
api.add_namespace(docs_ns, path='/docs')
api.add_namespace(keys_ns, path='/keys')
api.add_namespace(db_ns, path='/database')
api.add_namespace(config_ns, path='/config')
