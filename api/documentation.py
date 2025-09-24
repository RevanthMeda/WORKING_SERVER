"""
API documentation and OpenAPI specification generation.
"""
from flask import jsonify, request, current_app, url_for
from flask_restx import Namespace, Resource
from datetime import datetime
import json


# Create namespace for documentation
docs_ns = Namespace('docs', description='API Documentation and Specification')


@docs_ns.route('/openapi.json')
class OpenAPISpecResource(Resource):
    """OpenAPI 3.0 specification endpoint."""
    
    def get(self):
        """Get OpenAPI 3.0 specification in JSON format."""
        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": "SAT Report Generator API",
                "version": "1.0.0",
                "description": """
                Enterprise RESTful API for SAT Report Generator system.
                
                This API provides comprehensive access to report management,
                user authentication, file operations, and approval workflows.
                """,
                "termsOfService": "https://satreportgenerator.com/terms",
                "contact": {
                    "name": "API Support Team",
                    "email": "api-support@satreportgenerator.com",
                    "url": "https://satreportgenerator.com/support"
                },
                "license": {
                    "name": "Proprietary",
                    "url": "https://satreportgenerator.com/license"
                }
            },
            "servers": [
                {
                    "url": f"{request.scheme}://{request.host}/api/v1",
                    "description": "Production API Server"
                },
                {
                    "url": "https://staging.satreportgenerator.com/api/v1",
                    "description": "Staging API Server"
                },
                {
                    "url": "http://localhost:5000/api/v1",
                    "description": "Development API Server"
                }
            ],
            "security": [
                {"Bearer": []},
                {"ApiKey": []}
            ],
            "components": {
                "securitySchemes": {
                    "Bearer": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                        "description": "JWT Bearer token authentication"
                    },
                    "ApiKey": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key",
                        "description": "API Key for server-to-server authentication"
                    }
                },
                "schemas": {
                    "Error": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "object",
                                "properties": {
                                    "message": {
                                        "type": "string",
                                        "description": "Human readable error message"
                                    },
                                    "status_code": {
                                        "type": "integer",
                                        "description": "HTTP status code"
                                    },
                                    "code": {
                                        "type": "string",
                                        "description": "Machine readable error code"
                                    },
                                    "details": {
                                        "type": "object",
                                        "description": "Additional error details"
                                    },
                                    "timestamp": {
                                        "type": "string",
                                        "format": "date-time",
                                        "description": "Error timestamp"
                                    },
                                    "path": {
                                        "type": "string",
                                        "description": "Request path that caused the error"
                                    }
                                },
                                "required": ["message", "status_code", "timestamp"]
                            }
                        }
                    },
                    "ValidationError": {
                        "type": "object",
                        "properties": {
                            "error": {
                                "type": "object",
                                "properties": {
                                    "message": {
                                        "type": "string",
                                        "example": "Validation failed"
                                    },
                                    "status_code": {
                                        "type": "integer",
                                        "example": 400
                                    },
                                    "code": {
                                        "type": "string",
                                        "example": "VALIDATION_ERROR"
                                    },
                                    "details": {
                                        "type": "object",
                                        "description": "Field-specific validation errors",
                                        "example": {
                                            "email": ["Invalid email format"],
                                            "password": ["Password must be at least 12 characters"]
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "User ID",
                                "example": "user_123456"
                            },
                            "email": {
                                "type": "string",
                                "format": "email",
                                "description": "User email address",
                                "example": "john.doe@company.com"
                            },
                            "full_name": {
                                "type": "string",
                                "description": "User full name",
                                "example": "John Doe"
                            },
                            "role": {
                                "type": "string",
                                "enum": ["Engineer", "Admin", "PM", "Automation Manager"],
                                "description": "User role",
                                "example": "Engineer"
                            },
                            "is_active": {
                                "type": "boolean",
                                "description": "Whether user account is active",
                                "example": True
                            },
                            "is_approved": {
                                "type": "boolean",
                                "description": "Whether user account is approved",
                                "example": True
                            },
                            "created_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Account creation timestamp",
                                "example": "2023-01-01T00:00:00Z"
                            },
                            "last_login": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Last login timestamp",
                                "example": "2023-01-01T12:00:00Z"
                            }
                        }
                    },
                    "Report": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Report ID",
                                "example": "report_123456"
                            },
                            "document_title": {
                                "type": "string",
                                "description": "Document title",
                                "example": "SAT Report for Project Alpha"
                            },
                            "document_reference": {
                                "type": "string",
                                "description": "Document reference",
                                "example": "DOC-2023-001"
                            },
                            "project_reference": {
                                "type": "string",
                                "description": "Project reference",
                                "example": "PROJ-ALPHA-2023"
                            },
                            "client_name": {
                                "type": "string",
                                "description": "Client name",
                                "example": "Acme Corporation"
                            },
                            "revision": {
                                "type": "string",
                                "description": "Document revision",
                                "example": "R1"
                            },
                            "prepared_by": {
                                "type": "string",
                                "description": "Report preparer",
                                "example": "John Doe"
                            },
                            "date": {
                                "type": "string",
                                "format": "date",
                                "description": "Report date",
                                "example": "2023-01-01"
                            },
                            "purpose": {
                                "type": "string",
                                "description": "Report purpose",
                                "example": "Site Acceptance Testing for new automation system"
                            },
                            "scope": {
                                "type": "string",
                                "description": "Report scope",
                                "example": "Testing of PLC, SCADA, and HMI systems"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["Draft", "Pending Approval", "Approved", "Rejected", "Generated"],
                                "description": "Report status",
                                "example": "Draft"
                            },
                            "created_by": {
                                "type": "string",
                                "description": "Report creator ID",
                                "example": "user_123456"
                            },
                            "created_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Creation timestamp",
                                "example": "2023-01-01T00:00:00Z"
                            },
                            "updated_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "Last update timestamp",
                                "example": "2023-01-01T12:00:00Z"
                            }
                        }
                    },
                    "Pagination": {
                        "type": "object",
                        "properties": {
                            "page": {
                                "type": "integer",
                                "description": "Current page number",
                                "example": 1
                            },
                            "per_page": {
                                "type": "integer",
                                "description": "Items per page",
                                "example": 20
                            },
                            "total": {
                                "type": "integer",
                                "description": "Total number of items",
                                "example": 100
                            },
                            "pages": {
                                "type": "integer",
                                "description": "Total number of pages",
                                "example": 5
                            }
                        }
                    }
                },
                "responses": {
                    "ValidationError": {
                        "description": "Validation error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ValidationError"}
                            }
                        }
                    },
                    "Unauthorized": {
                        "description": "Authentication required",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"},
                                "example": {
                                    "error": {
                                        "message": "Authentication required",
                                        "status_code": 401,
                                        "code": "AUTHENTICATION_REQUIRED",
                                        "timestamp": "2023-01-01T00:00:00Z"
                                    }
                                }
                            }
                        }
                    },
                    "Forbidden": {
                        "description": "Access denied",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"},
                                "example": {
                                    "error": {
                                        "message": "Access denied",
                                        "status_code": 403,
                                        "code": "ACCESS_DENIED",
                                        "timestamp": "2023-01-01T00:00:00Z"
                                    }
                                }
                            }
                        }
                    },
                    "NotFound": {
                        "description": "Resource not found",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"},
                                "example": {
                                    "error": {
                                        "message": "Resource not found",
                                        "status_code": 404,
                                        "code": "NOT_FOUND",
                                        "timestamp": "2023-01-01T00:00:00Z"
                                    }
                                }
                            }
                        }
                    },
                    "Conflict": {
                        "description": "Resource conflict",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"},
                                "example": {
                                    "error": {
                                        "message": "Resource already exists",
                                        "status_code": 409,
                                        "code": "CONFLICT",
                                        "timestamp": "2023-01-01T00:00:00Z"
                                    }
                                }
                            }
                        }
                    },
                    "RateLimit": {
                        "description": "Rate limit exceeded",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"},
                                "example": {
                                    "error": {
                                        "message": "Rate limit exceeded",
                                        "status_code": 429,
                                        "code": "RATE_LIMIT_EXCEEDED",
                                        "timestamp": "2023-01-01T00:00:00Z"
                                    }
                                }
                            }
                        }
                    },
                    "InternalError": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Error"},
                                "example": {
                                    "error": {
                                        "message": "Internal server error",
                                        "status_code": 500,
                                        "code": "INTERNAL_ERROR",
                                        "timestamp": "2023-01-01T00:00:00Z"
                                    }
                                }
                            }
                        }
                    }
                },
                "parameters": {
                    "PageParam": {
                        "name": "page",
                        "in": "query",
                        "description": "Page number for pagination",
                        "schema": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 1
                        }
                    },
                    "PerPageParam": {
                        "name": "per_page",
                        "in": "query",
                        "description": "Number of items per page",
                        "schema": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 100,
                            "default": 20
                        }
                    },
                    "SearchParam": {
                        "name": "search",
                        "in": "query",
                        "description": "Search term for full-text search",
                        "schema": {
                            "type": "string"
                        }
                    },
                    "SortByParam": {
                        "name": "sort_by",
                        "in": "query",
                        "description": "Field to sort by",
                        "schema": {
                            "type": "string",
                            "default": "created_at"
                        }
                    },
                    "SortOrderParam": {
                        "name": "sort_order",
                        "in": "query",
                        "description": "Sort order",
                        "schema": {
                            "type": "string",
                            "enum": ["asc", "desc"],
                            "default": "desc"
                        }
                    }
                }
            },
            "tags": [
                {
                    "name": "Authentication",
                    "description": "User authentication and session management"
                },
                {
                    "name": "Users",
                    "description": "User management operations"
                },
                {
                    "name": "Reports",
                    "description": "SAT report management"
                },
                {
                    "name": "Files",
                    "description": "File upload and management"
                },
                {
                    "name": "Admin",
                    "description": "Administrative operations"
                },
                {
                    "name": "Documentation",
                    "description": "API documentation and specifications"
                }
            ],
            "externalDocs": {
                "description": "Find more info about SAT Report Generator",
                "url": "https://satreportgenerator.com/docs"
            }
        }
        
        return jsonify(spec)


@docs_ns.route('/redoc')
class RedocDocumentationResource(Resource):
    """ReDoc documentation interface."""
    
    def get(self):
        """Get ReDoc documentation HTML."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>SAT Report Generator API Documentation</title>
            <meta charset="utf-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
            <style>
                body {{ margin: 0; padding: 0; }}
            </style>
        </head>
        <body>
            <redoc spec-url="{url_for('api.docs_openapi_spec_resource', _external=True)}"></redoc>
            <script src="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js"></script>
        </body>
        </html>
        """
        return html, 200, {'Content-Type': 'text/html'}


@docs_ns.route('/swagger')
class SwaggerDocumentationResource(Resource):
    """Swagger UI documentation interface."""
    
    def get(self):
        """Get Swagger UI documentation HTML."""
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>SAT Report Generator API Documentation</title>
            <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui.css" />
            <style>
                html {{ box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }}
                *, *:before, *:after {{ box-sizing: inherit; }}
                body {{ margin:0; background: #fafafa; }}
            </style>
        </head>
        <body>
            <div id="swagger-ui"></div>
            <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-bundle.js"></script>
            <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-standalone-preset.js"></script>
            <script>
                window.onload = function() {{
                    const ui = SwaggerUIBundle({{
                        url: "{url_for('api.docs_openapi_spec_resource', _external=True)}",
                        dom_id: '#swagger-ui',
                        deepLinking: true,
                        presets: [
                            SwaggerUIBundle.presets.apis,
                            SwaggerUIStandalonePreset
                        ],
                        plugins: [
                            SwaggerUIBundle.plugins.DownloadUrl
                        ],
                        layout: "StandaloneLayout",
                        validatorUrl: null,
                        docExpansion: "list",
                        operationsSorter: "alpha",
                        tagsSorter: "alpha"
                    }});
                }};
            </script>
        </body>
        </html>
        """
        return html, 200, {'Content-Type': 'text/html'}


@docs_ns.route('/postman')
class PostmanCollectionResource(Resource):
    """Postman collection export."""
    
    def get(self):
        """Get Postman collection for API testing."""
        collection = {
            "info": {
                "name": "SAT Report Generator API",
                "description": "Postman collection for SAT Report Generator API",
                "version": "1.0.0",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{jwt_token}}",
                        "type": "string"
                    }
                ]
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": f"{request.scheme}://{request.host}/api/v1",
                    "type": "string"
                },
                {
                    "key": "jwt_token",
                    "value": "",
                    "type": "string"
                },
                {
                    "key": "api_key",
                    "value": "",
                    "type": "string"
                }
            ],
            "item": [
                {
                    "name": "Authentication",
                    "item": [
                        {
                            "name": "Login",
                            "request": {
                                "method": "POST",
                                "header": [
                                    {
                                        "key": "Content-Type",
                                        "value": "application/json"
                                    }
                                ],
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "email": "user@example.com",
                                        "password": "password123",
                                        "remember_me": False
                                    }, indent=2)
                                },
                                "url": {
                                    "raw": "{{base_url}}/auth/login",
                                    "host": ["{{base_url}}"],
                                    "path": ["auth", "login"]
                                }
                            }
                        },
                        {
                            "name": "Register",
                            "request": {
                                "method": "POST",
                                "header": [
                                    {
                                        "key": "Content-Type",
                                        "value": "application/json"
                                    }
                                ],
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "email": "newuser@example.com",
                                        "full_name": "New User",
                                        "password": "securepassword123",
                                        "requested_role": "Engineer"
                                    }, indent=2)
                                },
                                "url": {
                                    "raw": "{{base_url}}/auth/register",
                                    "host": ["{{base_url}}"],
                                    "path": ["auth", "register"]
                                }
                            }
                        }
                    ]
                },
                {
                    "name": "Reports",
                    "item": [
                        {
                            "name": "List Reports",
                            "request": {
                                "method": "GET",
                                "header": [],
                                "url": {
                                    "raw": "{{base_url}}/reports?page=1&per_page=20",
                                    "host": ["{{base_url}}"],
                                    "path": ["reports"],
                                    "query": [
                                        {"key": "page", "value": "1"},
                                        {"key": "per_page", "value": "20"}
                                    ]
                                }
                            }
                        },
                        {
                            "name": "Create Report",
                            "request": {
                                "method": "POST",
                                "header": [
                                    {
                                        "key": "Content-Type",
                                        "value": "application/json"
                                    }
                                ],
                                "body": {
                                    "mode": "raw",
                                    "raw": json.dumps({
                                        "document_title": "SAT Report for Project Alpha",
                                        "document_reference": "DOC-2023-001",
                                        "project_reference": "PROJ-ALPHA-2023",
                                        "client_name": "Acme Corporation",
                                        "revision": "R1",
                                        "prepared_by": "John Doe",
                                        "date": "2023-01-01",
                                        "purpose": "Site Acceptance Testing",
                                        "scope": "Testing of automation systems"
                                    }, indent=2)
                                },
                                "url": {
                                    "raw": "{{base_url}}/reports",
                                    "host": ["{{base_url}}"],
                                    "path": ["reports"]
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        return jsonify(collection)


@docs_ns.route('/health')
class HealthCheckResource(Resource):
    """API health check endpoint."""
    
    def get(self):
        """Get API health status."""
        try:
            # Test database connection
            from models import db
            with db.engine.connect() as connection:
                connection.execute(db.text('SELECT 1'))
            db_status = 'healthy'
        except Exception as e:
            db_status = f'unhealthy: {str(e)}'
        
        health_data = {
            'status': 'healthy' if db_status == 'healthy' else 'degraded',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0',
            'database': db_status,
            'services': {
                'authentication': 'healthy',
                'file_storage': 'healthy',
                'email_service': 'healthy',
                'audit_logging': 'healthy'
            }
        }
        
        status_code = 200 if health_data['status'] == 'healthy' else 503
        return jsonify(health_data), status_code


@docs_ns.route('/version')
class VersionResource(Resource):
    """API version information."""
    
    def get(self):
        """Get API version information."""
        version_info = {
            'api_version': '1.0.0',
            'build_date': '2023-01-01T00:00:00Z',
            'git_commit': 'abc123def456',
            'environment': current_app.config.get('ENV', 'development'),
            'features': [
                'authentication',
                'report_management',
                'file_upload',
                'approval_workflows',
                'audit_logging',
                'real_time_notifications'
            ],
            'deprecations': [],
            'breaking_changes': []
        }
        
        return jsonify(version_info)
