"""
Users API endpoints.
"""
from flask import request
from flask_restx import Namespace, Resource, fields
from flask_login import current_user
from marshmallow import Schema, fields as ma_fields, ValidationError

from models import User, db
from security.authentication import enhanced_login_required
from security.validation import validate_request_data, rate_limit_check
from security.audit import audit_data_access, get_audit_logger
from monitoring.logging_config import audit_logger as app_logger
from cache.decorators import cached, cache_response, invalidate_cache_pattern
from datetime import timedelta

# Create namespace
users_ns = Namespace('users', description='User management operations')

# Request/Response models
user_model = users_ns.model('User', {
    'id': fields.String(description='User ID'),
    'email': fields.String(description='Email address'),
    'full_name': fields.String(description='Full name'),
    'role': fields.String(description='User role'),
    'is_active': fields.Boolean(description='Account active status'),
    'is_approved': fields.Boolean(description='Account approval status'),
    'created_at': fields.DateTime(description='Account creation date'),
    'last_login': fields.DateTime(description='Last login date')
})

user_update_model = users_ns.model('UserUpdate', {
    'full_name': fields.String(description='Full name'),
    'role': fields.String(description='User role', enum=['Engineer', 'Admin', 'PM', 'Automation Manager']),
    'is_active': fields.Boolean(description='Account active status'),
    'is_approved': fields.Boolean(description='Account approval status')
})

user_list_model = users_ns.model('UserList', {
    'users': fields.List(fields.Nested(user_model)),
    'total': fields.Integer(description='Total number of users'),
    'page': fields.Integer(description='Current page'),
    'per_page': fields.Integer(description='Users per page'),
    'pages': fields.Integer(description='Total pages')
})

# Validation schemas
class UserUpdateSchema(Schema):
    """Schema for user update validation."""
    full_name = ma_fields.Str(validate=lambda x: 2 <= len(x.strip()) <= 100)
    role = ma_fields.Str(validate=lambda x: x in ['Engineer', 'Admin', 'PM', 'Automation Manager'])
    is_active = ma_fields.Bool()
    is_approved = ma_fields.Bool()


@users_ns.route('')
class UsersListResource(Resource):
    """Users list endpoint."""
    
    @users_ns.marshal_with(user_list_model)
    @enhanced_login_required
    @audit_data_access('user', 'read')
    def get(self):
        """Get list of users with pagination."""
        # Check permissions - only admins can view all users
        if current_user.role != 'Admin':
            return {'message': 'Admin access required'}, 403
        
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '').strip()
        role_filter = request.args.get('role')
        status_filter = request.args.get('status')
        
        # Build query
        query = User.query
        
        # Apply filters
        if search:
            query = query.filter(
                db.or_(
                    User.full_name.ilike(f'%{search}%'),
                    User.email.ilike(f'%{search}%')
                )
            )
        
        if role_filter:
            query = query.filter(User.role == role_filter)
        
        if status_filter == 'active':
            query = query.filter(User.is_active == True)
        elif status_filter == 'inactive':
            query = query.filter(User.is_active == False)
        elif status_filter == 'pending':
            query = query.filter(User.is_approved == False)
        
        # Paginate
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        users_data = []
        for user in pagination.items:
            users_data.append({
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'is_active': user.is_active,
                'is_approved': user.is_approved,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None
            })
        
        return {
            'users': users_data,
            'total': pagination.total,
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages
        }, 200


@users_ns.route('/<string:user_id>')
class UserResource(Resource):
    """Individual user endpoint."""
    
    @users_ns.marshal_with(user_model)
    @enhanced_login_required
    @audit_data_access('user', 'read')
    def get(self, user_id):
        """Get user by ID."""
        # Users can view their own profile, admins can view any profile
        if current_user.id != user_id and current_user.role != 'Admin':
            return {'message': 'Access denied'}, 403
        
        user = User.query.get_or_404(user_id)
        
        return {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'is_active': user.is_active,
            'is_approved': user.is_approved,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None
        }, 200
    
    @users_ns.expect(user_update_model)
    @users_ns.marshal_with(user_model)
    @enhanced_login_required
    @validate_request_data(UserUpdateSchema)
    @audit_data_access('user', 'update')
    def put(self, user_id):
        """Update user."""
        # Users can update their own profile (limited fields), admins can update any profile
        user = User.query.get_or_404(user_id)
        
        if current_user.id != user_id and current_user.role != 'Admin':
            return {'message': 'Access denied'}, 403
        
        data = request.validated_data
        
        # Regular users can only update their full name
        if current_user.role != 'Admin' and current_user.id == user_id:
            allowed_fields = ['full_name']
            data = {k: v for k, v in data.items() if k in allowed_fields}
        
        # Update user fields
        for field, value in data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        
        db.session.commit()
        
        # Log the update
        get_audit_logger().log_data_access(
            action='update',
            resource_type='user',
            resource_id=user_id,
            details={'updated_fields': list(data.keys())}
        )
        
        return {
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'role': user.role,
            'is_active': user.is_active,
            'is_approved': user.is_approved,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None
        }, 200
    
    @enhanced_login_required
    @audit_data_access('user', 'delete')
    def delete(self, user_id):
        """Delete user (admin only)."""
        if current_user.role != 'Admin':
            return {'message': 'Admin access required'}, 403
        
        user = User.query.get_or_404(user_id)
        
        # Prevent self-deletion
        if user.id == current_user.id:
            return {'message': 'Cannot delete your own account'}, 400
        
        # Soft delete - deactivate instead of actual deletion
        user.is_active = False
        db.session.commit()
        
        # Log the deletion
        get_audit_logger().log_data_access(
            action='delete',
            resource_type='user',
            resource_id=user_id,
            details={'action_type': 'soft_delete'}
        )
        
        return {'message': 'User successfully deactivated'}, 200


@users_ns.route('/<string:user_id>/approve')
class UserApprovalResource(Resource):
    """User approval endpoint."""
    
    @enhanced_login_required
    @audit_data_access('user', 'update')
    def post(self, user_id):
        """Approve user account (admin only)."""
        if current_user.role != 'Admin':
            return {'message': 'Admin access required'}, 403
        
        user = User.query.get_or_404(user_id)
        
        if user.is_approved:
            return {'message': 'User is already approved'}, 400
        
        user.is_approved = True
        user.is_active = True
        db.session.commit()
        
        # Log the approval
        get_audit_logger().log_data_access(
            action='update',
            resource_type='user',
            resource_id=user_id,
            details={'action_type': 'account_approval'}
        )
        
        return {'message': 'User account approved successfully'}, 200


@users_ns.route('/<string:user_id>/reject')
class UserRejectionResource(Resource):
    """User rejection endpoint."""
    
    @enhanced_login_required
    @audit_data_access('user', 'update')
    def post(self, user_id):
        """Reject user account (admin only)."""
        if current_user.role != 'Admin':
            return {'message': 'Admin access required'}, 403
        
        user = User.query.get_or_404(user_id)
        
        if user.is_approved:
            return {'message': 'Cannot reject an already approved user'}, 400
        
        # Delete the user account
        db.session.delete(user)
        db.session.commit()
        
        # Log the rejection
        get_audit_logger().log_data_access(
            action='delete',
            resource_type='user',
            resource_id=user_id,
            details={'action_type': 'account_rejection'}
        )
        
        return {'message': 'User account rejected and removed'}, 200


@users_ns.route('/me')
class CurrentUserResource(Resource):
    """Current user profile endpoint."""
    
    @users_ns.marshal_with(user_model)
    @enhanced_login_required
    def get(self):
        """Get current user profile."""
        return {
            'id': current_user.id,
            'email': current_user.email,
            'full_name': current_user.full_name,
            'role': current_user.role,
            'is_active': current_user.is_active,
            'is_approved': current_user.is_approved,
            'created_at': current_user.created_at.isoformat() if current_user.created_at else None,
            'last_login': current_user.last_login.isoformat() if current_user.last_login else None
        }, 200


@users_ns.route('/stats')
class UserStatsResource(Resource):
    """User statistics endpoint."""
    
    @enhanced_login_required
    def get(self):
        """Get user statistics (admin only)."""
        if current_user.role != 'Admin':
            return {'message': 'Admin access required'}, 403
        
        # Get user statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        pending_approval = User.query.filter_by(is_approved=False).count()
        
        # Role distribution
        role_stats = {}
        for role in ['Engineer', 'Admin', 'PM', 'Automation Manager']:
            role_stats[role] = User.query.filter_by(role=role, is_active=True).count()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': total_users - active_users,
            'pending_approval': pending_approval,
            'role_distribution': role_stats
        }, 200
