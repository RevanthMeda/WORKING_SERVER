from flask import Blueprint, request, jsonify, current_app
from models import db, Report, SATReport, User
from api.security import APIKey, APIUsage
from security.audit import AuditLog
from functools import wraps
from datetime import datetime, timedelta
import secrets
import hashlib
import json

api_bp = Blueprint('legacy_api', __name__)

def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = None
        
        # Check for API key in header
        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        # Check for API key in query params
        elif 'api_key' in request.args:
            api_key = request.args.get('api_key')
        
        if not api_key:
            return jsonify({'error': 'API key required'}), 401
        
        # Validate API key
        key_record = APIKey.query.filter_by(key=api_key, is_active=True).first()
        
        if not key_record:
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Check expiration
        if key_record.expires_at and key_record.expires_at < datetime.utcnow():
            return jsonify({'error': 'API key expired'}), 401
        
        # Check rate limit
        if not check_rate_limit(key_record):
            return jsonify({'error': 'Rate limit exceeded'}), 429
        
        # Track usage
        track_api_usage(key_record, request.endpoint, request.method)
        
        # Update last used
        key_record.last_used = datetime.utcnow()
        db.session.commit()
        
        # Add key to request context
        request.api_key = key_record
        
        return f(*args, **kwargs)
    
    return decorated_function

def check_rate_limit(api_key):
    """Check if API key has exceeded rate limit"""
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    
    usage_count = APIUsage.query.filter(
        APIUsage.api_key_id == api_key.id,
        APIUsage.timestamp >= one_hour_ago
    ).count()
    
    return usage_count < api_key.rate_limit

def track_api_usage(api_key, endpoint, method):
    """Track API usage for analytics"""
    usage = APIUsage(
        api_key_id=api_key.id,
        endpoint=endpoint or request.path,
        method=method,
        ip_address=request.remote_addr
    )
    
    db.session.add(usage)
    db.session.commit()

# API Documentation endpoint
@api_bp.route('/docs')
def api_documentation():
    """Return API documentation in OpenAPI format"""
    docs = {
        "openapi": "3.0.0",
        "info": {
            "title": "SAT Report Generator API",
            "version": "1.0.0",
            "description": "REST API for SAT Report management and generation"
        },
        "servers": [
            {"url": "/api/v1", "description": "API v1"}
        ],
        "security": [
            {"ApiKeyAuth": []}
        ],
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            }
        },
        "paths": {
            "/reports": {
                "get": {
                    "summary": "List all reports",
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer"}},
                        {"name": "status", "in": "query", "schema": {"type": "string"}},
                        {"name": "type", "in": "query", "schema": {"type": "string"}}
                    ],
                    "responses": {
                        "200": {"description": "List of reports"},
                        "401": {"description": "Unauthorized"}
                    }
                },
                "post": {
                    "summary": "Create a new report",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    },
                    "responses": {
                        "201": {"description": "Report created"},
                        "400": {"description": "Invalid request"}
                    }
                }
            }
        }
    }
    
    return jsonify(docs)

# Report endpoints
@api_bp.route('/v1/reports', methods=['GET'])
@require_api_key
def get_reports():
    """Get list of reports with filtering"""
    try:
        # Parse query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        report_type = request.args.get('type')
        client = request.args.get('client')
        
        # Build query
        query = Report.query
        
        if status:
            query = query.filter(Report.status == status)
        
        if report_type:
            query = query.filter(Report.type == report_type)
        
        if client:
            query = query.filter(Report.client_name == client)
        
        # Check permissions
        permissions = json.loads(request.api_key.permissions_json or '[]')
        if 'reports:read:all' not in permissions:
            # Limit to reports created by API key owner
            query = query.filter(Report.user_email == request.api_key.user_email)
        
        # Paginate
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format response
        reports = []
        for report in paginated.items:
            reports.append({
                'id': report.id,
                'type': report.type,
                'document_title': report.document_title,
                'project_reference': report.project_reference,
                'client_name': report.client_name,
                'status': report.status,
                'revision': report.revision,
                'created_at': report.created_at.isoformat(),
                'updated_at': report.updated_at.isoformat() if report.updated_at else None
            })
        
        return jsonify({
            'success': True,
            'data': reports,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated.total,
                'pages': paginated.pages
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"API error getting reports: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/v1/reports/<report_id>', methods=['GET'])
@require_api_key
def get_report(report_id):
    """Get a specific report"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Check permissions
        permissions = json.loads(request.api_key.permissions_json or '[]')
        if 'reports:read:all' not in permissions and report.user_email != request.api_key.user_email:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get SAT data if applicable
        report_data = {
            'id': report.id,
            'type': report.type,
            'document_title': report.document_title,
            'project_reference': report.project_reference,
            'client_name': report.client_name,
            'status': report.status,
            'revision': report.revision,
            'created_at': report.created_at.isoformat(),
            'updated_at': report.updated_at.isoformat() if report.updated_at else None,
            'user_email': report.user_email
        }
        
        if report.type == 'SAT':
            sat_report = SATReport.query.filter_by(report_id=report.id).first()
            if sat_report:
                report_data['sat_data'] = json.loads(sat_report.data_json)
        
        return jsonify({
            'success': True,
            'data': report_data
        })
        
    except Exception as e:
        current_app.logger.error(f"API error getting report: {e}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/v1/reports', methods=['POST'])
@require_api_key
def create_report():
    """Create a new report via API"""
    try:
        # Check permissions
        permissions = json.loads(request.api_key.permissions_json or '[]')
        if 'reports:create' not in permissions:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        data = request.json
        
        # Validate required fields
        required_fields = ['type', 'document_title', 'project_reference', 'client_name']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create report
        import uuid
        report = Report(
            id=str(uuid.uuid4()),
            type=data['type'],
            document_title=data['document_title'],
            project_reference=data['project_reference'],
            client_name=data['client_name'],
            status='DRAFT',
            revision=data.get('revision', 'R0'),
            user_email=request.api_key.user_email,
            created_at=datetime.utcnow()
        )
        
        db.session.add(report)
        
        # Create SAT report if applicable
        if data['type'] == 'SAT' and 'sat_data' in data:
            sat_report = SATReport(
                report_id=report.id,
                data_json=json.dumps(data['sat_data'])
            )
            db.session.add(sat_report)
        
        db.session.commit()
        
        # Log the creation
        audit_log = AuditLog(
            user_email=request.api_key.user_email,
            user_name=f"API: {request.api_key.name}",
            action='create',
            entity_type='report',
            entity_id=report.id,
            details=f"Created via API",
            ip_address=request.remote_addr
        )
        db.session.add(audit_log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': {
                'id': report.id,
                'status': report.status
            }
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"API error creating report: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/v1/reports/<report_id>', methods=['PUT'])
@require_api_key
def update_report(report_id):
    """Update a report"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Check permissions
        permissions = json.loads(request.api_key.permissions_json or '[]')
        if 'reports:update:all' not in permissions and report.user_email != request.api_key.user_email:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.json
        
        # Update allowed fields
        if 'document_title' in data:
            report.document_title = data['document_title']
        if 'project_reference' in data:
            report.project_reference = data['project_reference']
        if 'client_name' in data:
            report.client_name = data['client_name']
        if 'revision' in data:
            report.revision = data['revision']
        if 'status' in data and 'reports:status:update' in permissions:
            report.status = data['status']
        
        report.updated_at = datetime.utcnow()
        
        # Update SAT data if provided
        if report.type == 'SAT' and 'sat_data' in data:
            sat_report = SATReport.query.filter_by(report_id=report.id).first()
            if sat_report:
                sat_report.data_json = json.dumps(data['sat_data'])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Report updated successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"API error updating report: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/v1/reports/<report_id>', methods=['DELETE'])
@require_api_key
def delete_report(report_id):
    """Delete a report"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Check permissions
        permissions = json.loads(request.api_key.permissions_json or '[]')
        if 'reports:delete' not in permissions:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        if 'reports:delete:all' not in permissions and report.user_email != request.api_key.user_email:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete associated data
        if report.type == 'SAT':
            SATReport.query.filter_by(report_id=report.id).delete()
        
        db.session.delete(report)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Report deleted successfully'
        })
        
    except Exception as e:
        current_app.logger.error(f"API error deleting report: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/v1/reports/<report_id>/download', methods=['GET'])
@require_api_key
def download_report(report_id):
    """Download report document"""
    try:
        import os
        from flask import send_file
        
        report = Report.query.get_or_404(report_id)
        
        # Check permissions
        permissions = json.loads(request.api_key.permissions_json or '[]')
        if 'reports:download' not in permissions:
            return jsonify({'error': 'Insufficient permissions'}), 403
        
        format_type = request.args.get('format', 'pdf')
        
        # Get file path
        if format_type == 'pdf':
            file_path = f"outputs/{report.id}/SAT_{report.project_reference}.pdf"
        else:
            file_path = f"outputs/{report.id}/SAT_{report.project_reference}.docx"
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'Document not found'}), 404
        
        return send_file(file_path, as_attachment=True)
        
    except Exception as e:
        current_app.logger.error(f"API error downloading report: {e}")
        return jsonify({'error': str(e)}), 500

# API Key Management endpoints
@api_bp.route('/v1/keys', methods=['POST'])
def create_api_key():
    """Create a new API key (requires authentication)"""
    # This would normally require user authentication
    # For now, we'll require a master key
    master_key = request.headers.get('X-Master-Key')
    if master_key != current_app.config.get('MASTER_API_KEY'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        
        # Generate secure key
        raw_key = secrets.token_urlsafe(32)
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Create API key record
        api_key = APIKey(
            key=hashed_key,
            name=data['name'],
            description=data.get('description'),
            user_email=data['user_email'],
            permissions_json=json.dumps(data.get('permissions', [])),
            rate_limit=data.get('rate_limit', 1000)
        )
        
        if 'expires_days' in data:
            api_key.expires_at = datetime.utcnow() + timedelta(days=data['expires_days'])
        
        db.session.add(api_key)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'api_key': raw_key,  # Return the raw key only once
            'key_id': api_key.id,
            'message': 'Save this key securely. It cannot be retrieved again.'
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Error creating API key: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@api_bp.route('/v1/usage/stats', methods=['GET'])
@require_api_key
def get_usage_stats():
    """Get API usage statistics"""
    try:
        # Get usage for the current API key
        days = int(request.args.get('days', 7))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        usage = APIUsage.query.filter(
            APIUsage.api_key_id == request.api_key.id,
            APIUsage.timestamp >= start_date
        ).all()
        
        # Aggregate by endpoint
        endpoint_stats = {}
        for record in usage:
            if record.endpoint not in endpoint_stats:
                endpoint_stats[record.endpoint] = {
                    'count': 0,
                    'avg_response_time': 0
                }
            
            endpoint_stats[record.endpoint]['count'] += 1
            
        return jsonify({
            'success': True,
            'stats': {
                'total_requests': len(usage),
                'period_days': days,
                'by_endpoint': endpoint_stats,
                'rate_limit': request.api_key.rate_limit,
                'requests_remaining': request.api_key.rate_limit - len(usage)
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting usage stats: {e}")
        return jsonify({'error': str(e)}), 500