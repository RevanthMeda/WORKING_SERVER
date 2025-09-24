"""
Reports API endpoints.
"""
from flask import request, send_file, g
from flask_restx import Namespace, Resource, fields
from flask_login import current_user
from datetime import datetime
import os

from models import Report, SATReport, User, db
from security.authentication import enhanced_login_required, role_required_api
from security.validation import validate_request_data
from security.audit import audit_report_action, get_audit_logger
from api.security import require_auth, security_headers
from api.schemas import (
    report_schema, reports_schema, report_create_schema, 
    report_update_schema, report_list_schema, approval_schema,
    stats_schema, pagination_schema
)
from api.errors import APIError, ErrorResponse

# Create namespace
reports_ns = Namespace('reports', description='Report management operations')

# Create Flask-RESTX models from schemas for documentation
report_model = reports_ns.model('Report', {
    'id': fields.String(description='Report ID'),
    'document_title': fields.String(description='Document title'),
    'document_reference': fields.String(description='Document reference'),
    'project_reference': fields.String(description='Project reference'),
    'client_name': fields.String(description='Client name'),
    'revision': fields.String(description='Revision'),
    'prepared_by': fields.String(description='Prepared by'),
    'date': fields.Date(description='Report date'),
    'purpose': fields.String(description='Purpose'),
    'scope': fields.String(description='Scope'),
    'status': fields.String(description='Report status'),
    'created_by': fields.String(description='Created by user ID'),
    'created_at': fields.DateTime(description='Creation timestamp'),
    'updated_at': fields.DateTime(description='Last update timestamp')
})

report_create_model = reports_ns.model('ReportCreate', {
    'document_title': fields.String(required=True, description='Document title'),
    'document_reference': fields.String(required=True, description='Document reference'),
    'project_reference': fields.String(required=True, description='Project reference'),
    'client_name': fields.String(required=True, description='Client name'),
    'revision': fields.String(required=True, description='Revision'),
    'prepared_by': fields.String(required=True, description='Prepared by'),
    'date': fields.Date(required=True, description='Report date'),
    'purpose': fields.String(required=True, description='Purpose'),
    'scope': fields.String(required=True, description='Scope')
})

report_update_model = reports_ns.model('ReportUpdate', {
    'document_title': fields.String(description='Document title'),
    'document_reference': fields.String(description='Document reference'),
    'project_reference': fields.String(description='Project reference'),
    'client_name': fields.String(description='Client name'),
    'revision': fields.String(description='Revision'),
    'prepared_by': fields.String(description='Prepared by'),
    'date': fields.Date(description='Report date'),
    'purpose': fields.String(description='Purpose'),
    'scope': fields.String(description='Scope')
})

report_list_model = reports_ns.model('ReportList', {
    'reports': fields.List(fields.Nested(report_model)),
    'total': fields.Integer(description='Total number of reports'),
    'page': fields.Integer(description='Current page'),
    'per_page': fields.Integer(description='Reports per page'),
    'pages': fields.Integer(description='Total pages')
})

approval_model = reports_ns.model('Approval', {
    'action': fields.String(required=True, description='Approval action', enum=['approve', 'reject']),
    'comments': fields.String(description='Approval comments')
})

stats_model = reports_ns.model('ReportStats', {
    'total_reports': fields.Integer(description='Total number of reports'),
    'draft_reports': fields.Integer(description='Number of draft reports'),
    'pending_approval': fields.Integer(description='Number of reports pending approval'),
    'approved_reports': fields.Integer(description='Number of approved reports'),
    'generated_reports': fields.Integer(description='Number of generated reports'),
    'rejected_reports': fields.Integer(description='Number of rejected reports')
})


@reports_ns.route('')
class ReportsListResource(Resource):
    """Reports list endpoint."""
    
    @reports_ns.marshal_with(report_list_model)
    @require_auth(permissions=['reports:read'])
    @security_headers
    def get(self):
        """Get list of reports with pagination and filtering."""
        try:
            # Validate query parameters
            args = pagination_schema.load(request.args)
            
            # Build query
            query = Report.query
            
            # Get current user from context
            user = getattr(g, 'current_user', current_user)
            
            # Apply access control - users can only see their own reports unless admin
            if user.role != 'Admin':
                query = query.filter(Report.created_by == user.id)
            
            # Apply search filter
            if args.get('search'):
                search_term = f"%{args['search']}%"
                query = query.filter(
                    db.or_(
                        Report.document_title.ilike(search_term),
                        Report.document_reference.ilike(search_term),
                        Report.project_reference.ilike(search_term),
                        Report.client_name.ilike(search_term)
                    )
                )
            
            # Apply additional filters from query params
            status_filter = request.args.get('status')
            if status_filter:
                query = query.filter(Report.status == status_filter)
            
            client_filter = request.args.get('client')
            if client_filter:
                query = query.filter(Report.client_name.ilike(f'%{client_filter}%'))
            
            created_by_filter = request.args.get('created_by')
            if created_by_filter and user.role == 'Admin':
                query = query.filter(Report.created_by == created_by_filter)
            
            # Apply sorting
            if args['sort_by'] == 'created_at':
                order_col = Report.created_at
            elif args['sort_by'] == 'updated_at':
                order_col = Report.updated_at
            elif args['sort_by'] == 'document_title':
                order_col = Report.document_title
            else:
                order_col = Report.created_at
            
            if args['sort_order'] == 'desc':
                query = query.order_by(order_col.desc())
            else:
                query = query.order_by(order_col.asc())
            
            # Paginate
            pagination = query.paginate(
                page=args['page'], 
                per_page=args['per_page'], 
                error_out=False
            )
            
            # Serialize reports
            reports_data = reports_schema.dump(pagination.items)
            
            # Log data access
            get_audit_logger().log_data_access(
                action='read',
                resource_type='report',
                details={
                    'count': len(reports_data),
                    'filters': {k: v for k, v in args.items() if v}
                }
            )
            
            return {
                'reports': reports_data,
                'total': pagination.total,
                'page': pagination.page,
                'per_page': pagination.per_page,
                'pages': pagination.pages
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to retrieve reports: {str(e)}", 500)
    
    @reports_ns.expect(report_create_model)
    @reports_ns.marshal_with(report_model)
    @enhanced_login_required
    @role_required_api(['Engineer', 'Admin', 'Automation Manager'])
    @audit_report_action('create')
    def post(self):
        """Create new report."""
        try:
            # Validate request data
            data = report_create_schema.load(request.get_json())
            
            # Get current user from context
            user = getattr(g, 'current_user', current_user)
            
            # Check for duplicate document reference
            existing_report = Report.query.filter_by(
                document_reference=data['document_reference']
            ).first()
            
            if existing_report:
                raise APIError('Report with this document reference already exists', 409)
            
            # Create new report
            report = Report(
                document_title=data['document_title'],
                document_reference=data['document_reference'],
                project_reference=data['project_reference'],
                client_name=data['client_name'],
                revision=data['revision'],
                prepared_by=data['prepared_by'],
                date=data['date'],
                purpose=data['purpose'],
                scope=data['scope'],
                status='Draft',
                created_by=user.id
            )
            
            db.session.add(report)
            db.session.commit()
            
            # Serialize response
            result = report_schema.dump(report)
            
            return result, 201
            
        except Exception as e:
            db.session.rollback()
            if isinstance(e, APIError):
                raise
            raise APIError(f"Failed to create report: {str(e)}", 500)


@reports_ns.route('/<string:report_id>')
class ReportResource(Resource):
    """Individual report endpoint."""
    
    @reports_ns.marshal_with(report_model)
    @enhanced_login_required
    def get(self, report_id):
        """Get report by ID."""
        report = Report.query.get_or_404(report_id)
        
        # Check access permissions
        if current_user.role != 'Admin' and report.created_by != current_user.id:
            return {'message': 'Access denied'}, 403
        
        # Log data access
        get_audit_logger().log_data_access(
            action='read',
            resource_type='report',
            resource_id=report_id
        )
        
        return {
            'id': report.id,
            'document_title': report.document_title,
            'document_reference': report.document_reference,
            'project_reference': report.project_reference,
            'client_name': report.client_name,
            'revision': report.revision,
            'prepared_by': report.prepared_by,
            'date': report.date.isoformat() if report.date else None,
            'purpose': report.purpose,
            'scope': report.scope,
            'status': report.status,
            'created_by': report.created_by,
            'created_at': report.created_at.isoformat() if report.created_at else None,
            'updated_at': report.updated_at.isoformat() if report.updated_at else None
        }, 200
    
    @reports_ns.expect(report_update_model)
    @reports_ns.marshal_with(report_model)
    @enhanced_login_required
    @validate_request_data(report_update_schema)
    @audit_report_action('update')
    def put(self, report_id):
        """Update report."""
        report = Report.query.get_or_404(report_id)
        
        # Check access permissions
        if current_user.role != 'Admin' and report.created_by != current_user.id:
            return {'message': 'Access denied'}, 403
        
        # Check if report can be modified
        if report.status in ['Approved', 'Generated']:
            return {'message': 'Cannot modify approved or generated reports'}, 400
        
        data = request.validated_data
        
        # Update report fields
        for field, value in data.items():
            if hasattr(report, field):
                setattr(report, field, value)
        
        report.updated_at = datetime.utcnow()
        db.session.commit()
        
        return {
            'id': report.id,
            'document_title': report.document_title,
            'document_reference': report.document_reference,
            'project_reference': report.project_reference,
            'client_name': report.client_name,
            'revision': report.revision,
            'prepared_by': report.prepared_by,
            'date': report.date.isoformat() if report.date else None,
            'purpose': report.purpose,
            'scope': report.scope,
            'status': report.status,
            'created_by': report.created_by,
            'created_at': report.created_at.isoformat() if report.created_at else None,
            'updated_at': report.updated_at.isoformat() if report.updated_at else None
        }, 200
    
    @enhanced_login_required
    @audit_report_action('delete')
    def delete(self, report_id):
        """Delete report."""
        report = Report.query.get_or_404(report_id)
        
        # Check access permissions
        if current_user.role != 'Admin' and report.created_by != current_user.id:
            return {'message': 'Access denied'}, 403
        
        # Check if report can be deleted
        if report.status in ['Approved', 'Generated']:
            return {'message': 'Cannot delete approved or generated reports'}, 400
        
        # Delete associated SAT reports
        SATReport.query.filter_by(report_id=report_id).delete()
        
        # Delete the report
        db.session.delete(report)
        db.session.commit()
        
        return {'message': 'Report successfully deleted'}, 200


@reports_ns.route('/<string:report_id>/approve')
class ReportApprovalResource(Resource):
    """Report approval endpoint."""
    
    @reports_ns.expect(approval_model)
    @enhanced_login_required
    @audit_report_action('approve')
    def post(self, report_id):
        """Approve or reject report."""
        # Only admins and PMs can approve reports
        if current_user.role not in ['Admin', 'PM']:
            return {'message': 'Approval permissions required'}, 403
        
        report = Report.query.get_or_404(report_id)
        data = request.get_json()
        
        action = data.get('action')
        comments = data.get('comments', '')
        
        if action not in ['approve', 'reject']:
            return {'message': 'Invalid action. Must be approve or reject'}, 400
        
        if report.status != 'Pending Approval':
            return {'message': 'Report is not pending approval'}, 400
        
        if action == 'approve':
            report.status = 'Approved'
            message = 'Report approved successfully'
        else:
            report.status = 'Rejected'
            message = 'Report rejected'
        
        # Update approval fields (assuming these exist in the model)
        report.approved_by = current_user.id
        report.approval_date = datetime.utcnow()
        report.approval_comments = comments
        
        db.session.commit()
        
        # Log the approval action
        get_audit_logger().log_report_event(
            action=action,
            report_id=report_id,
            details={
                'approved_by': current_user.id,
                'comments': comments
            }
        )
        
        return {'message': message}, 200


@reports_ns.route('/<string:report_id>/submit')
class ReportSubmissionResource(Resource):
    """Report submission endpoint."""
    
    @enhanced_login_required
    @audit_report_action('update')
    def post(self, report_id):
        """Submit report for approval."""
        report = Report.query.get_or_404(report_id)
        
        # Check access permissions
        if current_user.role != 'Admin' and report.created_by != current_user.id:
            return {'message': 'Access denied'}, 403
        
        if report.status != 'Draft':
            return {'message': 'Only draft reports can be submitted for approval'}, 400
        
        # Check if report has required SAT reports
        sat_reports_count = SATReport.query.filter_by(report_id=report_id).count()
        if sat_reports_count == 0:
            return {'message': 'Report must have at least one SAT report before submission'}, 400
        
        report.status = 'Pending Approval'
        report.submitted_at = datetime.utcnow()
        db.session.commit()
        
        return {'message': 'Report submitted for approval successfully'}, 200


@reports_ns.route('/<string:report_id>/generate')
class ReportGenerationResource(Resource):
    """Report generation endpoint."""
    
    @enhanced_login_required
    @audit_report_action('generate')
    def post(self, report_id):
        """Generate final report document."""
        report = Report.query.get_or_404(report_id)
        
        # Only approved reports can be generated
        if report.status != 'Approved':
            return {'message': 'Only approved reports can be generated'}, 400
        
        try:
            # This would call the actual report generation logic
            # For now, just update the status
            report.status = 'Generated'
            report.generated_at = datetime.utcnow()
            report.generated_by = current_user.id
            db.session.commit()
            
            return {'message': 'Report generation initiated successfully'}, 200
            
        except Exception as e:
            app_logger.error(f"Report generation failed: {str(e)}")
            return {'message': 'Report generation failed'}, 500


@reports_ns.route('/<string:report_id>/download')
class ReportDownloadResource(Resource):
    """Report download endpoint."""
    
    @enhanced_login_required
    @audit_report_action('download')
    def get(self, report_id):
        """Download generated report."""
        report = Report.query.get_or_404(report_id)
        
        # Check access permissions
        if current_user.role != 'Admin' and report.created_by != current_user.id:
            return {'message': 'Access denied'}, 403
        
        if report.status != 'Generated':
            return {'message': 'Report has not been generated yet'}, 400
        
        # This would return the actual file
        # For now, just return a success message
        return {'message': 'Report download would be initiated here'}, 200


@reports_ns.route('/stats')
class ReportStatsResource(Resource):
    """Report statistics endpoint."""
    
    @enhanced_login_required
    def get(self):
        """Get report statistics."""
        # Build base query
        base_query = Report.query
        
        # Apply access control
        if current_user.role != 'Admin':
            base_query = base_query.filter(Report.created_by == current_user.id)
        
        # Get statistics
        total_reports = base_query.count()
        draft_reports = base_query.filter_by(status='Draft').count()
        pending_reports = base_query.filter_by(status='Pending Approval').count()
        approved_reports = base_query.filter_by(status='Approved').count()
        generated_reports = base_query.filter_by(status='Generated').count()
        rejected_reports = base_query.filter_by(status='Rejected').count()
        
        return {
            'total_reports': total_reports,
            'draft_reports': draft_reports,
            'pending_approval': pending_reports,
            'approved_reports': approved_reports,
            'generated_reports': generated_reports,
            'rejected_reports': rejected_reports
        }, 200
