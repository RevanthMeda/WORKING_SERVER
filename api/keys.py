"""
API Key management endpoints.
"""
from flask import request, jsonify, g
from flask_restx import Namespace, Resource, fields
from datetime import datetime, timedelta
from marshmallow import Schema, fields as ma_fields, ValidationError

from models import db
from api.security import APIKey, security_manager, require_auth
from security.authentication import enhanced_login_required, role_required_api
from security.audit import get_audit_logger
from api.errors import APIError, ErrorResponse

# Create namespace
keys_ns = Namespace('keys', description='API Key management operations')

# Request/Response models
api_key_model = keys_ns.model('APIKey', {
    'id': fields.String(description='API Key ID'),
    'name': fields.String(description='API Key name'),
    'description': fields.String(description='API Key description'),
    'permissions': fields.List(fields.String, description='API Key permissions'),
    'rate_limit': fields.Integer(description='Rate limit (requests per hour)'),
    'is_active': fields.Boolean(description='Whether API key is active'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'last_used': fields.DateTime(description='Last used timestamp'),
    'expires_at': fields.DateTime(description='Expiration timestamp')
})

api_key_create_model = keys_ns.model('APIKeyCreate', {
    'name': fields.String(required=True, description='API Key name'),
    'description': fields.String(description='API Key description'),
    'permissions': fields.List(fields.String, description='API Key permissions'),
    'rate_limit': fields.Integer(description='Rate limit (requests per hour)', default=1000),
    'expires_in_days': fields.Integer(description='Expiration in days (optional)')
})

api_key_response_model = keys_ns.model('APIKeyResponse', {
    'api_key': fields.String(description='The actual API key (only shown once)'),
    'key_info': fields.Nested(api_key_model, description='API key information')
})

api_key_update_model = keys_ns.model('APIKeyUpdate', {
    'name': fields.String(description='API Key name'),
    'description': fields.String(description='API Key description'),
    'permissions': fields.List(fields.String, description='API Key permissions'),
    'rate_limit': fields.Integer(description='Rate limit (requests per hour)'),
    'is_active': fields.Boolean(description='Whether API key is active')
})

usage_stats_model = keys_ns.model('UsageStats', {
    'total_requests': fields.Integer(description='Total requests'),
    'requests_today': fields.Integer(description='Requests today'),
    'requests_this_hour': fields.Integer(description='Requests this hour'),
    'average_response_time': fields.Float(description='Average response time (seconds)'),
    'error_rate': fields.Float(description='Error rate percentage'),
    'top_endpoints': fields.List(fields.Raw, description='Most used endpoints'),
    'rate_limit_status': fields.Raw(description='Current rate limit status')
})

# Validation schemas
class APIKeyCreateSchema(Schema):
    """Schema for API key creation."""
    name = ma_fields.Str(required=True, validate=lambda x: 3 <= len(x.strip()) <= 100)
    description = ma_fields.Str(validate=lambda x: len(x.strip()) <= 500)
    permissions = ma_fields.List(ma_fields.Str(), load_default=list)
    rate_limit = ma_fields.Int(validate=lambda x: 1 <= x <= 100000, load_default=1000)
    expires_in_days = ma_fields.Int(validate=lambda x: 1 <= x <= 3650)  # Max 10 years

class APIKeyUpdateSchema(Schema):
    """Schema for API key updates."""
    name = ma_fields.Str(validate=lambda x: 3 <= len(x.strip()) <= 100)
    description = ma_fields.Str(validate=lambda x: len(x.strip()) <= 500)
    permissions = ma_fields.List(ma_fields.Str())
    rate_limit = ma_fields.Int(validate=lambda x: 1 <= x <= 100000)
    is_active = ma_fields.Bool()


@keys_ns.route('')
class APIKeysListResource(Resource):
    """API Keys list endpoint."""
    
    @keys_ns.marshal_list_with(api_key_model)
    @enhanced_login_required
    @role_required_api(['Admin', 'PM'])
    def get(self):
        """Get list of API keys."""
        try:
            user = getattr(g, 'current_user')
            
            # Admins can see all keys, others only their own
            if user.role == 'Admin':
                api_keys = APIKey.query.all()
            else:
                api_keys = APIKey.query.filter_by(user_id=user.id).all()
            
            # Convert to dict and remove sensitive data
            keys_data = []
            for key in api_keys:
                key_data = key.to_dict()
                # Never return the actual key hash
                key_data.pop('key_hash', None)
                keys_data.append(key_data)
            
            get_audit_logger().log_data_access(
                action='read',
                resource_type='api_key',
                details={'count': len(keys_data)}
            )
            
            return keys_data, 200
            
        except Exception as e:
            raise APIError(f"Failed to retrieve API keys: {str(e)}", 500)
    
    @keys_ns.expect(api_key_create_model)
    @keys_ns.marshal_with(api_key_response_model)
    @enhanced_login_required
    @role_required_api(['Admin', 'PM', 'Automation Manager'])
    def post(self):
        """Create new API key."""
        try:
            # Validate request data
            schema = APIKeyCreateSchema()
            data = schema.load(request.get_json())
            
            user = getattr(g, 'current_user')
            
            # Generate API key
            api_key_value = APIKey.generate_key()
            key_hash = APIKey.hash_key(api_key_value)
            
            # Set expiration if specified
            expires_at = None
            if data.get('expires_in_days'):
                expires_at = datetime.utcnow() + timedelta(days=data['expires_in_days'])
            
            # Create API key record
            api_key = APIKey(
                name=data['name'],
                description=data.get('description'),
                key_hash=key_hash,
                user_id=user.id,
                permissions=data.get('permissions', []),
                rate_limit=data.get('rate_limit', 1000),
                expires_at=expires_at
            )
            
            db.session.add(api_key)
            db.session.commit()
            
            # Log API key creation
            get_audit_logger().log_data_access(
                action='create',
                resource_type='api_key',
                resource_id=api_key.id,
                details={
                    'name': api_key.name,
                    'permissions': api_key.permissions,
                    'rate_limit': api_key.rate_limit
                }
            )
            
            # Return the key (only time it's shown)
            result = {
                'api_key': api_key_value,
                'key_info': api_key.to_dict()
            }
            
            return result, 201
            
        except ValidationError as e:
            return ErrorResponse.validation_error(e.messages)
        except Exception as e:
            db.session.rollback()
            raise APIError(f"Failed to create API key: {str(e)}", 500)


@keys_ns.route('/<string:key_id>')
class APIKeyResource(Resource):
    """Individual API key endpoint."""
    
    @keys_ns.marshal_with(api_key_model)
    @enhanced_login_required
    def get(self, key_id):
        """Get API key by ID."""
        try:
            user = getattr(g, 'current_user')
            
            # Find API key
            api_key = APIKey.query.get_or_404(key_id)
            
            # Check permissions
            if user.role != 'Admin' and api_key.user_id != user.id:
                return ErrorResponse.authorization_error()
            
            # Log access
            get_audit_logger().log_data_access(
                action='read',
                resource_type='api_key',
                resource_id=key_id
            )
            
            key_data = api_key.to_dict()
            return key_data, 200
            
        except Exception as e:
            raise APIError(f"Failed to retrieve API key: {str(e)}", 500)
    
    @keys_ns.expect(api_key_update_model)
    @keys_ns.marshal_with(api_key_model)
    @enhanced_login_required
    def put(self, key_id):
        """Update API key."""
        try:
            user = getattr(g, 'current_user')
            
            # Find API key
            api_key = APIKey.query.get_or_404(key_id)
            
            # Check permissions
            if user.role != 'Admin' and api_key.user_id != user.id:
                return ErrorResponse.authorization_error()
            
            # Validate request data
            schema = APIKeyUpdateSchema()
            data = schema.load(request.get_json())
            
            # Update fields
            for field, value in data.items():
                if hasattr(api_key, field):
                    setattr(api_key, field, value)
            
            db.session.commit()
            
            # Log update
            get_audit_logger().log_data_access(
                action='update',
                resource_type='api_key',
                resource_id=key_id,
                details={'updated_fields': list(data.keys())}
            )
            
            return api_key.to_dict(), 200
            
        except ValidationError as e:
            return ErrorResponse.validation_error(e.messages)
        except Exception as e:
            db.session.rollback()
            raise APIError(f"Failed to update API key: {str(e)}", 500)
    
    @enhanced_login_required
    def delete(self, key_id):
        """Delete API key."""
        try:
            user = getattr(g, 'current_user')
            
            # Find API key
            api_key = APIKey.query.get_or_404(key_id)
            
            # Check permissions
            if user.role != 'Admin' and api_key.user_id != user.id:
                return ErrorResponse.authorization_error()
            
            # Soft delete by deactivating
            api_key.is_active = False
            db.session.commit()
            
            # Log deletion
            get_audit_logger().log_data_access(
                action='delete',
                resource_type='api_key',
                resource_id=key_id,
                details={'action_type': 'soft_delete'}
            )
            
            return {'message': 'API key successfully deactivated'}, 200
            
        except Exception as e:
            db.session.rollback()
            raise APIError(f"Failed to delete API key: {str(e)}", 500)


@keys_ns.route('/<string:key_id>/regenerate')
class APIKeyRegenerateResource(Resource):
    """API key regeneration endpoint."""
    
    @keys_ns.marshal_with(api_key_response_model)
    @enhanced_login_required
    def post(self, key_id):
        """Regenerate API key."""
        try:
            user = getattr(g, 'current_user')
            
            # Find API key
            api_key = APIKey.query.get_or_404(key_id)
            
            # Check permissions
            if user.role != 'Admin' and api_key.user_id != user.id:
                return ErrorResponse.authorization_error()
            
            # Generate new key
            new_key_value = APIKey.generate_key()
            api_key.key_hash = APIKey.hash_key(new_key_value)
            
            db.session.commit()
            
            # Log regeneration
            get_audit_logger().log_data_access(
                action='update',
                resource_type='api_key',
                resource_id=key_id,
                details={'action': 'regenerate_key'}
            )
            
            result = {
                'api_key': new_key_value,
                'key_info': api_key.to_dict()
            }
            
            return result, 200
            
        except Exception as e:
            db.session.rollback()
            raise APIError(f"Failed to regenerate API key: {str(e)}", 500)


@keys_ns.route('/<string:key_id>/usage')
class APIKeyUsageResource(Resource):
    """API key usage statistics endpoint."""
    
    @keys_ns.marshal_with(usage_stats_model)
    @enhanced_login_required
    def get(self, key_id):
        """Get API key usage statistics."""
        try:
            user = getattr(g, 'current_user')
            
            # Find API key
            api_key = APIKey.query.get_or_404(key_id)
            
            # Check permissions
            if user.role != 'Admin' and api_key.user_id != user.id:
                return ErrorResponse.authorization_error()
            
            # Get usage statistics
            from api.security import APIUsage
            from sqlalchemy import func
            
            now = datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            this_hour = now.replace(minute=0, second=0, microsecond=0)
            
            # Total requests
            total_requests = APIUsage.query.filter_by(api_key_id=key_id).count()
            
            # Requests today
            requests_today = APIUsage.query.filter(
                APIUsage.api_key_id == key_id,
                APIUsage.timestamp >= today
            ).count()
            
            # Requests this hour
            requests_this_hour = APIUsage.query.filter(
                APIUsage.api_key_id == key_id,
                APIUsage.timestamp >= this_hour
            ).count()
            
            # Average response time
            avg_response_time = db.session.query(
                func.avg(APIUsage.response_time)
            ).filter_by(api_key_id=key_id).scalar() or 0
            
            # Error rate
            error_count = APIUsage.query.filter(
                APIUsage.api_key_id == key_id,
                APIUsage.status_code >= 400
            ).count()
            
            error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
            
            # Top endpoints
            top_endpoints = db.session.query(
                APIUsage.endpoint,
                func.count(APIUsage.id).label('count')
            ).filter_by(api_key_id=key_id).group_by(
                APIUsage.endpoint
            ).order_by(func.count(APIUsage.id).desc()).limit(10).all()
            
            top_endpoints_data = [
                {'endpoint': endpoint, 'count': count}
                for endpoint, count in top_endpoints
            ]
            
            # Current rate limit status
            rate_limit_status = security_manager.rate_limiter.get_rate_limit_status(
                f"api_key:{APIKey.generate_key()}"  # This is just for structure
            )
            
            stats = {
                'total_requests': total_requests,
                'requests_today': requests_today,
                'requests_this_hour': requests_this_hour,
                'average_response_time': float(avg_response_time),
                'error_rate': float(error_rate),
                'top_endpoints': top_endpoints_data,
                'rate_limit_status': rate_limit_status
            }
            
            return stats, 200
            
        except Exception as e:
            raise APIError(f"Failed to retrieve usage statistics: {str(e)}", 500)


@keys_ns.route('/permissions')
class APIPermissionsResource(Resource):
    """Available API permissions endpoint."""
    
    @enhanced_login_required
    def get(self):
        """Get list of available API permissions."""
        permissions = {
            'reports': [
                'reports:read',
                'reports:create',
                'reports:update',
                'reports:delete',
                'reports:approve',
                'reports:download'
            ],
            'users': [
                'users:read',
                'users:create',
                'users:update',
                'users:delete'
            ],
            'files': [
                'files:upload',
                'files:download',
                'files:delete'
            ],
            'admin': [
                'admin:read',
                'admin:manage_users',
                'admin:manage_api_keys',
                'admin:view_audit_logs'
            ]
        }
        
        return permissions, 200
