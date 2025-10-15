from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Report, SATReport, FDSReport, ReportEdit, User
import json
import uuid
from datetime import datetime

edit_bp = Blueprint('edit', __name__)

def can_edit_report(report, user):
    """Check if user can edit the report"""
    # Admin can edit any report
    if user.role == 'Admin':
        return True
    
    # Check if report is locked or approved
    if report.locked or report.status == 'APPROVED':
        return False
    
    # Engineers can edit their own reports in DRAFT or PENDING status
    if user.role == 'Engineer':
        return (report.user_email == user.email and 
                report.status in ['DRAFT', 'PENDING'])
    
    # Automation Manager can edit reports until approved by PM
    if user.role == 'Automation Manager':
        if report.approvals_json:
            try:
                approvals = json.loads(report.approvals_json)
                # Check if PM (stage 2) has approved
                pm_approved = any(
                    a.get("status") == "approved" and a.get("stage") == 2 
                    for a in approvals
                )
                return not pm_approved
            except:
                return True
        return True
    
    return False

def increment_version(version):
    """Increment report version (R0 -> R1 -> R2, etc.)"""
    if not version or not version.startswith('R'):
        return 'R1'
    try:
        num = int(version[1:])
        return f'R{num + 1}'
    except:
        return 'R1'

@edit_bp.route('/reports/<report_id>/edit', methods=['GET'])
@login_required
def edit_report(report_id):
    """Display edit form for a report"""
    report = Report.query.get_or_404(report_id)
    
    # Check permissions
    if not can_edit_report(report, current_user):
        flash('You do not have permission to edit this report.', 'error')
        return redirect(url_for('dashboard.home'))
    
    if report.type == 'SAT':
        sat_report = SATReport.query.filter_by(report_id=report_id).first()
        if not sat_report:
            flash('Report data not found.', 'error')
            return redirect(url_for('dashboard.home'))

        # Ensure JSON is readable before redirecting
        try:
            json.loads(sat_report.data_json)
        except Exception:
            flash('Error loading report data.', 'error')
            return redirect(url_for('dashboard.home'))

        return redirect(url_for('reports.sat_wizard',
                                submission_id=report_id,
                                edit_mode='true'))

    if report.type == 'FDS':
        fds_report = FDSReport.query.filter_by(report_id=report_id).first()
        if not fds_report or not fds_report.data_json:
            flash('FDS report data not found.', 'error')
            return redirect(url_for('dashboard.my_reports'))
        return redirect(url_for('reports.fds_wizard',
                                submission_id=report_id,
                                edit_mode='true'))

    flash('Editing is not yet supported for this report type.', 'warning')
    return redirect(url_for('dashboard.my_reports'))

@edit_bp.route('/reports/<report_id>/save-edit', methods=['POST'])
@login_required
def save_edit(report_id):
    """Save edits to a report with CSRF protection and concurrency control"""
    report = Report.query.get_or_404(report_id)
    
    # Check permissions
    if not can_edit_report(report, current_user):
        return jsonify({'error': 'Permission denied'}), 403
    
    # CSRF Protection for JSON requests
    from flask_wtf.csrf import validate_csrf
    try:
        # Get CSRF token from headers or request data
        csrf_token = request.headers.get('X-CSRFToken') or request.json.get('csrf_token')
        if csrf_token:
            validate_csrf(csrf_token)
        else:
            # For backwards compatibility, log warning but continue
            current_app.logger.warning(f"No CSRF token provided for edit on report {report_id}")
    except Exception as e:
        current_app.logger.error(f"CSRF validation failed: {e}")
        return jsonify({'error': 'CSRF token validation failed'}), 403
    
    # Get existing SAT report
    sat_report = SATReport.query.filter_by(report_id=report_id).first()
    if not sat_report:
        return jsonify({'error': 'Report not found'}), 404
    
    # Store the before state for audit
    before_json = sat_report.data_json
    before_version = report.version
    
    # Get the new data from request
    try:
        new_data = request.json
        if not new_data:
            return jsonify({'error': 'No data provided'}), 400
    except:
        return jsonify({'error': 'Invalid data format'}), 400
    
    # Optimistic Concurrency Control - check if report was modified by someone else
    last_updated_timestamp = new_data.get('last_updated_timestamp')
    if last_updated_timestamp:
        try:
            # Convert timestamp string to datetime for comparison
            client_timestamp = datetime.fromisoformat(last_updated_timestamp)
            
            # Check if report was modified since client loaded it
            if report.updated_at and report.updated_at > client_timestamp:
                current_app.logger.warning(f"Concurrent edit conflict on report {report_id}. Client timestamp: {client_timestamp}, Server timestamp: {report.updated_at}")
                return jsonify({
                    'error': 'Report was modified by another user',
                    'conflict': True,
                    'message': 'This report has been modified by another user. Please reload the page to see the latest version.',
                    'server_version': report.version,
                    'server_updated_at': report.updated_at.isoformat() if report.updated_at else None
                }), 409
        except (ValueError, TypeError) as e:
            current_app.logger.error(f"Error parsing timestamp for concurrency check: {e}")
            # Continue without concurrency check if timestamp parsing fails
    
    # Update the SAT report data
    sat_report.data_json = json.dumps(new_data)
    
    # Update the report metadata from the new data
    context = new_data.get('context', {})
    report.document_title = context.get('DOCUMENT_TITLE', report.document_title)
    report.document_reference = context.get('DOCUMENT_REFERENCE', report.document_reference)
    report.project_reference = context.get('PROJECT_REFERENCE', report.project_reference)
    report.client_name = context.get('CLIENT_NAME', report.client_name)
    report.revision = context.get('REVISION', report.revision)
    report.prepared_by = context.get('PREPARED_BY', report.prepared_by)
    
    # Update timestamps and version
    report.updated_at = datetime.utcnow()
    new_version = increment_version(report.version)
    report.version = new_version
    report.edit_count = (report.edit_count or 0) + 1
    
    # Create audit trail entry
    edit_entry = ReportEdit(
        report_id=report_id,
        editor_user_id=current_user.id,
        editor_email=current_user.email,
        before_json=before_json,
        after_json=json.dumps(new_data),
        changes_summary=f"Report edited by {current_user.full_name}",
        version_before=before_version,
        version_after=new_version
    )
    
    try:
        db.session.add(edit_entry)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Report updated successfully',
            'new_version': new_version,
            'redirect_url': url_for('status.view_status', submission_id=report_id)
        })
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving edit: {e}")
        return jsonify({'error': 'Failed to save changes'}), 500

@edit_bp.route('/reports/<report_id>/edit-history', methods=['GET'])
@login_required
def view_edit_history(report_id):
    """View edit history for a report"""
    report = Report.query.get_or_404(report_id)
    
    # Check if user can view this report
    if not (current_user.role == 'Admin' or 
            report.user_email == current_user.email or
            current_user.role in ['Automation Manager', 'PM']):
        flash('Permission denied.', 'error')
        return redirect(url_for('dashboard.home'))
    
    # Get edit history
    edits = ReportEdit.query.filter_by(report_id=report_id)\
                           .order_by(ReportEdit.created_at.desc()).all()
    
    return render_template('edit_history.html',
                         report=report,
                         edits=edits)

@edit_bp.route('/api/reports/<report_id>/can-edit', methods=['GET'])
@login_required
def check_edit_permission(report_id):
    """API endpoint to check if current user can edit a report"""
    report = Report.query.get(report_id)
    if not report:
        return jsonify({'can_edit': False, 'reason': 'Report not found'}), 404
    
    can_edit = can_edit_report(report, current_user)
    
    reason = ''
    if not can_edit:
        if report.locked:
            reason = 'Report is locked'
        elif report.status == 'APPROVED':
            reason = 'Report is already approved'
        elif report.user_email != current_user.email:
            reason = 'You can only edit your own reports'
        else:
            reason = 'Permission denied'
    
    return jsonify({
        'can_edit': can_edit,
        'reason': reason,
        'status': report.status,
        'locked': report.locked,
        'version': report.version,
        'updated_at': report.updated_at.isoformat() if report.updated_at else None
    })
