"""
Admin API endpoints.
"""
from flask import request, jsonify
from flask_restx import Namespace, Resource
from flask_login import current_user
from security.authentication import enhanced_login_required, role_required_api
from security.audit import get_audit_logger

# Create namespace
admin_ns = Namespace('admin', description='Administrative operations')

@admin_ns.route('/health')
class AdminHealthResource(Resource):
    """Admin health check endpoint."""
    
    @enhanced_login_required
    @role_required_api('Admin')
    def get(self):
        """Get system health status."""
        return {
            'status': 'healthy',
            'message': 'Admin API is operational'
        }, 200