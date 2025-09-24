from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Report, User, UserAnalytics
from api.security import APIUsage
from security.audit import AuditLog
from auth import role_required
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import json

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/dashboard')
@login_required
def analytics_dashboard():
    """Analytics dashboard with visualizations"""
    try:
        # Check permissions
        if current_user.role not in ['Admin', 'Automation Manager', 'TM', 'PM']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        return render_template('analytics_dashboard.html', current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error loading analytics dashboard: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/report-metrics')
@login_required
def get_report_metrics():
    """Get report generation metrics for charts"""
    try:
        # Time range
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Reports by status
        status_counts = db.session.query(
            Report.status,
            func.count(Report.id).label('count')
        ).filter(
            Report.created_at >= start_date
        ).group_by(Report.status).all()
        
        # Reports by type
        type_counts = db.session.query(
            Report.type,
            func.count(Report.id).label('count')
        ).filter(
            Report.created_at >= start_date
        ).group_by(Report.type).all()
        
        # Daily report creation
        daily_reports = db.session.query(
            func.date(Report.created_at).label('date'),
            func.count(Report.id).label('count')
        ).filter(
            Report.created_at >= start_date
        ).group_by(func.date(Report.created_at)).order_by(func.date(Report.created_at)).all()
        
        # Top clients
        top_clients = db.session.query(
            Report.client_name,
            func.count(Report.id).label('count')
        ).filter(
            Report.created_at >= start_date
        ).group_by(Report.client_name).order_by(func.count(Report.id).desc()).limit(10).all()
        
        # Average approval time
        approved_reports = Report.query.filter(
            Report.status.in_(['TECH_APPROVED', 'PM_APPROVED', 'COMPLETED']),
            Report.created_at >= start_date
        ).all()
        
        approval_times = []
        for report in approved_reports:
            if report.updated_at:
                time_diff = (report.updated_at - report.created_at).total_seconds() / 3600  # Hours
                approval_times.append(time_diff)
        
        avg_approval_time = sum(approval_times) / len(approval_times) if approval_times else 0
        
        return jsonify({
            'success': True,
            'metrics': {
                'status_distribution': [
                    {'status': s[0], 'count': s[1]} for s in status_counts
                ],
                'type_distribution': [
                    {'type': t[0], 'count': t[1]} for t in type_counts
                ],
                'daily_trend': [
                    {'date': d[0].isoformat(), 'count': d[1]} for d in daily_reports
                ],
                'top_clients': [
                    {'client': c[0], 'count': c[1]} for c in top_clients
                ],
                'avg_approval_time_hours': round(avg_approval_time, 2),
                'total_reports': Report.query.filter(Report.created_at >= start_date).count()
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting report metrics: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/user-performance')
@login_required
def get_user_performance():
    """Get user performance metrics"""
    try:
        # Time range
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Reports by user
        user_reports = db.session.query(
            Report.user_email,
            func.count(Report.id).label('count'),
            func.avg(
                extract('epoch', Report.updated_at - Report.created_at) / 3600
            ).label('avg_time')
        ).filter(
            Report.created_at >= start_date
        ).group_by(Report.user_email).all()
        
        # Format user data
        user_metrics = []
        for user_data in user_reports:
            user = User.query.filter_by(email=user_data[0]).first()
            if user:
                user_metrics.append({
                    'name': user.full_name,
                    'email': user_data[0],
                    'reports_created': user_data[1],
                    'avg_completion_hours': round(user_data[2] if user_data[2] else 0, 2)
                })
        
        # Sort by reports created
        user_metrics.sort(key=lambda x: x['reports_created'], reverse=True)
        
        # Approval rates
        total_submitted = Report.query.filter(
            Report.status != 'DRAFT',
            Report.created_at >= start_date
        ).count()
        
        total_approved = Report.query.filter(
            Report.status.in_(['TECH_APPROVED', 'PM_APPROVED', 'COMPLETED']),
            Report.created_at >= start_date
        ).count()
        
        approval_rate = (total_approved / total_submitted * 100) if total_submitted > 0 else 0
        
        return jsonify({
            'success': True,
            'performance': {
                'user_metrics': user_metrics[:10],  # Top 10 users
                'approval_rate': round(approval_rate, 2),
                'total_users': len(user_metrics),
                'active_users': len([u for u in user_metrics if u['reports_created'] > 0])
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting user performance: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/system-health')
@login_required
@role_required(['Admin', 'Automation Manager'])
def get_system_health():
    """Get system health metrics"""
    try:
        # Database metrics
        total_reports = Report.query.count()
        total_users = User.query.filter_by(status='Active').count()
        
        # API usage
        api_usage_today = APIUsage.query.filter(
            APIUsage.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        ).count()
        
        # Error rate from audit logs
        recent_errors = AuditLog.query.filter(
            AuditLog.timestamp >= datetime.utcnow() - timedelta(hours=24),
            AuditLog.success == False
        ).count()
        
        total_actions = AuditLog.query.filter(
            AuditLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).count()
        
        error_rate = (recent_errors / total_actions * 100) if total_actions > 0 else 0
        
        # Storage usage (simplified)
        import os
        outputs_size = 0
        if os.path.exists('outputs'):
            for dirpath, dirnames, filenames in os.walk('outputs'):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    outputs_size += os.path.getsize(filepath)
        
        storage_mb = outputs_size / (1024 * 1024)
        
        # Response times from API usage
        recent_api_calls = APIUsage.query.filter(
            APIUsage.timestamp >= datetime.utcnow() - timedelta(hours=1),
            APIUsage.response_time_ms.isnot(None)
        ).all()
        
        avg_response_time = 0
        if recent_api_calls:
            response_times = [call.response_time_ms for call in recent_api_calls]
            avg_response_time = sum(response_times) / len(response_times)
        
        return jsonify({
            'success': True,
            'health': {
                'total_reports': total_reports,
                'active_users': total_users,
                'api_calls_today': api_usage_today,
                'error_rate_24h': round(error_rate, 2),
                'storage_used_mb': round(storage_mb, 2),
                'avg_api_response_ms': round(avg_response_time, 2),
                'system_status': 'healthy' if error_rate < 5 else 'degraded' if error_rate < 10 else 'critical'
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting system health: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/workflow-analytics')
@login_required
def get_workflow_analytics():
    """Get workflow and approval analytics"""
    try:
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Approval cycle times by stage
        reports = Report.query.filter(
            Report.created_at >= start_date
        ).all()
        
        submission_to_tm = []
        tm_to_pm = []
        pm_to_complete = []
        
        for report in reports:
            if report.tm_approved and report.updated_at:
                # Calculate time from submission to TM approval
                # This is simplified - in production would track actual approval timestamps
                time_to_tm = (report.updated_at - report.created_at).total_seconds() / 3600
                submission_to_tm.append(time_to_tm)
        
        # Average cycle times
        avg_submission_to_tm = sum(submission_to_tm) / len(submission_to_tm) if submission_to_tm else 0
        
        # Bottleneck analysis
        pending_tm = Report.query.filter_by(status='SUBMITTED').count()
        pending_pm = Report.query.filter_by(status='TECH_APPROVED').count()
        
        # Rejection rates by stage
        rejected_count = Report.query.filter_by(status='REJECTED').count()
        total_processed = Report.query.filter(
            Report.status != 'DRAFT'
        ).count()
        
        rejection_rate = (rejected_count / total_processed * 100) if total_processed > 0 else 0
        
        return jsonify({
            'success': True,
            'workflow': {
                'avg_tm_approval_hours': round(avg_submission_to_tm, 2),
                'pending_tm_approval': pending_tm,
                'pending_pm_approval': pending_pm,
                'rejection_rate': round(rejection_rate, 2),
                'bottleneck_stage': 'TM Approval' if pending_tm > pending_pm else 'PM Approval' if pending_pm > 0 else 'None'
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting workflow analytics: {e}")
        return jsonify({'error': str(e)}), 500

@analytics_bp.route('/api/export-analytics')
@login_required
@role_required(['Admin', 'Automation Manager'])
def export_analytics():
    """Export analytics data to CSV"""
    try:
        import csv
        import io
        from flask import Response
        
        # Get date range
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Report ID', 'Type', 'Title', 'Project Reference', 'Client',
            'Status', 'Created By', 'Created At', 'Updated At',
            'TM Approved', 'PM Approved'
        ])
        
        # Get reports
        reports = Report.query.filter(
            Report.created_at >= start_date
        ).order_by(Report.created_at.desc()).all()
        
        # Write data
        for report in reports:
            writer.writerow([
                report.id,
                report.type,
                report.document_title,
                report.project_reference,
                report.client_name,
                report.status,
                report.user_email,
                report.created_at.isoformat(),
                report.updated_at.isoformat() if report.updated_at else '',
                'Yes' if report.tm_approved else 'No',
                'Yes' if report.pm_approved else 'No'
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=analytics_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        
    except Exception as e:
        current_app.logger.error(f"Error exporting analytics: {e}")
        return jsonify({'error': str(e)}), 500