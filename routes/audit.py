from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db
from security.audit import AuditLog
from auth import role_required
from datetime import datetime, timedelta
from sqlalchemy import func
import json

audit_bp = Blueprint('audit', __name__)

@audit_bp.route('/logs')
@login_required
@role_required(['Admin'])
def audit_logs():
    """View audit logs interface"""
    try:
        # Get unique actions and entity types for filters
        actions = db.session.query(AuditLog.action).distinct().all()
        entity_types = db.session.query(AuditLog.entity_type).distinct().all()
        
        return render_template('audit_logs.html',
                             actions=[a[0] for a in actions],
                             entity_types=[e[0] for e in entity_types],
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error loading audit logs: {e}")
        return jsonify({'error': str(e)}), 500

@audit_bp.route('/api/logs')
@login_required
@role_required(['Admin'])
def get_audit_logs():
    """Get audit logs with filtering"""
    try:
        # Parse filters from query params
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        query = AuditLog.query
        
        # User filter
        user_email = request.args.get('user_email')
        if user_email:
            query = query.filter(AuditLog.user_email == user_email)
        
        # Action filter
        action = request.args.get('action')
        if action:
            query = query.filter(AuditLog.action == action)
        
        # Entity type filter
        entity_type = request.args.get('entity_type')
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        
        # Date range filter
        date_from = request.args.get('date_from')
        if date_from:
            query = query.filter(AuditLog.timestamp >= datetime.fromisoformat(date_from))
        
        date_to = request.args.get('date_to')
        if date_to:
            query = query.filter(AuditLog.timestamp <= datetime.fromisoformat(date_to))
        
        # Success/failure filter
        success = request.args.get('success')
        if success is not None:
            query = query.filter(AuditLog.success == (success == 'true'))
        
        # Order by timestamp descending
        query = query.order_by(AuditLog.timestamp.desc())
        
        # Paginate
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format results
        logs = []
        for log in paginated.items:
            logs.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'user_email': log.user_email,
                'user_name': log.user_name,
                'action': log.action,
                'entity_type': log.entity_type,
                'entity_id': log.entity_id,
                'details': log.details,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'success': log.success
            })
        
        return jsonify({
            'success': True,
            'logs': logs,
            'total': paginated.total,
            'pages': paginated.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting audit logs: {e}")
        return jsonify({'error': str(e)}), 500

@audit_bp.route('/api/stats')
@login_required
@role_required(['Admin'])
def audit_statistics():
    """Get audit log statistics"""
    try:
        # Time range for stats (last 30 days)
        start_date = datetime.utcnow() - timedelta(days=30)
        
        # Activity by action
        activity_by_action = db.session.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= start_date
        ).group_by(AuditLog.action).all()
        
        # Activity by user
        activity_by_user = db.session.query(
            AuditLog.user_email,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= start_date
        ).group_by(AuditLog.user_email).order_by(func.count(AuditLog.id).desc()).limit(10).all()
        
        # Daily activity
        daily_activity = db.session.query(
            func.date(AuditLog.timestamp).label('date'),
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= start_date
        ).group_by(func.date(AuditLog.timestamp)).all()
        
        # Failed actions
        failed_actions = db.session.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.success == False
        ).group_by(AuditLog.action).all()
        
        return jsonify({
            'success': True,
            'stats': {
                'activity_by_action': [
                    {'action': a[0], 'count': a[1]} for a in activity_by_action
                ],
                'activity_by_user': [
                    {'user': u[0], 'count': u[1]} for u in activity_by_user
                ],
                'daily_activity': [
                    {'date': d[0].isoformat(), 'count': d[1]} for d in daily_activity
                ],
                'failed_actions': [
                    {'action': f[0], 'count': f[1]} for f in failed_actions
                ]
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting audit statistics: {e}")
        return jsonify({'error': str(e)}), 500

@audit_bp.route('/api/export')
@login_required
@role_required(['Admin'])
def export_audit_logs():
    """Export audit logs to CSV"""
    try:
        import csv
        import io
        
        # Get filters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        query = AuditLog.query
        
        if date_from:
            query = query.filter(AuditLog.timestamp >= datetime.fromisoformat(date_from))
        
        if date_to:
            query = query.filter(AuditLog.timestamp <= datetime.fromisoformat(date_to))
        
        # Get all logs in range
        logs = query.order_by(AuditLog.timestamp.desc()).all()
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Timestamp', 'User Email', 'User Name', 'Action', 
            'Entity Type', 'Entity ID', 'Details', 'IP Address', 
            'User Agent', 'Success'
        ])
        
        # Write data
        for log in logs:
            writer.writerow([
                log.timestamp.isoformat(),
                log.user_email,
                log.user_name,
                log.action,
                log.entity_type,
                log.entity_id,
                log.details,
                log.ip_address,
                log.user_agent,
                'Yes' if log.success else 'No'
            ])
        
        # Send CSV file
        from flask import Response
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=audit_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Error exporting audit logs: {e}")
        return jsonify({'error': str(e)}), 500

def log_action(action, entity_type, entity_id=None, details=None, success=True):
    """Helper function to log an action"""
    try:
        audit_log = AuditLog(
            user_email=current_user.email if current_user.is_authenticated else 'system',
            user_name=current_user.full_name if current_user.is_authenticated else 'System',
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent', '')[:200] if request else None,
            success=success
        )
        
        db.session.add(audit_log)
        db.session.commit()
        
    except Exception as e:
        current_app.logger.error(f"Error logging action: {e}")

# Decorator for automatic audit logging
def audit_logged(action, entity_type):
    """Decorator to automatically log actions"""
    def decorator(f):
        def wrapped(*args, **kwargs):
            entity_id = kwargs.get('id') or kwargs.get('report_id')
            
            try:
                result = f(*args, **kwargs)
                log_action(action, entity_type, entity_id, success=True)
                return result
            except Exception as e:
                log_action(action, entity_type, entity_id, 
                          details=f"Error: {str(e)}", success=False)
                raise
        
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator