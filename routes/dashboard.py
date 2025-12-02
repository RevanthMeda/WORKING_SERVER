from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, make_response, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from auth_utils import admin_required, role_required
from models import (
    db,
    User,
    Report,
    SATReport,
    FDSReport,
    StorageConfig,
    StorageSettingsAudit,
    SystemSettings,
    Notification,
    CullyStatistics,
    test_db_connection,
)
from api.security import APIKey, APIUsage
from datetime import datetime
import time
import os

from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_, func, case, text
import json
from functools import wraps
from sqlalchemy.exc import ProgrammingError, OperationalError
from services.dashboard_stats import get_cached_dashboard_stats, compute_and_cache_dashboard_stats
from services.storage_manager import (
    StorageSettingsService,
    StorageSettingsError,
    StorageSettingsValidationError,
    StorageSettingsConcurrencyError,
)


EMPTY_DASHBOARD_STATS = {
    'draft': 0,
    'pending': 0,
    'rejected': 0,
    'approved': 0,
    'requests_received': 0,
    'requests_approved': 0,
    'total_reports': 0,
}


def _get_storage_settings_payload():
    """Return storage settings, audit history, and optional error message."""
    compression_profiles = current_app.config.get('IMAGE_COMPRESSION_PROFILES', {}) or {}
    fallback_settings = {
        'org_id': 'default',
        'environment': current_app.config.get('ENV', 'production'),
        'upload_root': current_app.config.get('UPLOAD_ROOT_RAW', current_app.config.get('UPLOAD_ROOT', 'static/uploads')),
        'image_storage_limit_gb': current_app.config.get('IMAGE_STORAGE_LIMIT_GB', 50),
        'active_quality': compression_profiles.get('active_quality', 95),
        'approved_quality': compression_profiles.get('approved_quality', 80),
        'archive_quality': compression_profiles.get('archive_quality', 65),
        'preferred_formats': current_app.config.get('IMAGE_PREFERRED_FORMATS', ['jpeg', 'png', 'webp']),
        'version': 1,
    }

    try:
        settings_obj = StorageSettingsService.load_settings()
        storage_dict = settings_obj.to_dict()
        storage_config = (
            db.session.query(StorageConfig)
            .filter_by(org_id=settings_obj.org_id, environment=settings_obj.environment)
            .first()
        )
        audits = []
        if storage_config:
            audits = [
                entry.to_dict()
                for entry in (
                    db.session.query(StorageSettingsAudit)
                    .filter_by(storage_config_id=storage_config.id)
                    .order_by(StorageSettingsAudit.created_at.desc())
                    .limit(20)
                    .all()
                )
            ]
        return storage_dict, audits, None
    except StorageSettingsError as exc:
        current_app.logger.error("Storage settings retrieval failed: %s", exc)
        return fallback_settings, [], str(exc)
    except Exception as exc:
        current_app.logger.error("Unexpected error retrieving storage settings: %s", exc, exc_info=True)
        return fallback_settings, [], str(exc)


def no_cache(f):
    """Decorator to prevent caching of routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated_function

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
@no_cache
def home():
    """Role-based dashboard home"""
    # Double-check authentication at route level
    if not current_user.is_authenticated:
        session.clear()
        return redirect(url_for('auth.welcome'))
    
    role = current_user.role

    if role == 'Admin':
        return redirect(url_for('dashboard.admin'))
    elif role == 'Engineer':
        return redirect(url_for('dashboard.engineer'))
    elif role == 'Automation Manager':
        return redirect(url_for('dashboard.automation_manager'))
    elif role == 'PM':
        return redirect(url_for('dashboard.pm'))
    else:
        flash('Invalid role. Contact your administrator.', 'error')
        return redirect(url_for('auth.logout'))

@dashboard_bp.route('/admin')
@admin_required
@no_cache
def admin():
    """Admin dashboard"""
    db_connected = test_db_connection()

    # Calculate user statistics with optimized single query
    user_stats = db.session.query(
        func.count(User.id).label('total'),
        func.sum(case((User.status == 'Active', 1), else_=0)).label('active'),
        func.sum(case((User.status == 'Pending', 1), else_=0)).label('pending')
    ).first()
    
    total_users = user_stats.total or 0
    pending_users_count = user_stats.pending or 0
    
    # Get all users for display (only if needed)
    users = db.session.query(User).all()

    # Get actual pending users (users who need approval)
    pending_users_list = (
        db.session.query(User)
        .filter_by(status='Pending')
        .order_by(User.created_date.desc())
        .limit(5)
        .all()
    )

    # Calculate report statistics
    try:
        # Use optimized query for report count
        total_reports = db.session.query(func.count(Report.id)).scalar() or 0
        current_app.logger.info(f"Admin dashboard: Found {total_reports} total reports")
        
        # Eager load SAT reports to prevent N+1 queries
        recent_reports = (
            db.session.query(Report)
            .options(joinedload(Report.sat_report))
            .order_by(Report.created_at.desc())
            .limit(5)
            .all()
        )
        current_app.logger.info(f"Admin dashboard: Processing {len(recent_reports)} recent reports")
        
        # Add basic report info for display
        for report in recent_reports:
            # Use the actual status from the database - DO NOT override!
            if not report.status:
                report.status = 'DRAFT'  # Default only if somehow missing
            
            # Ensure we have a document title
            report.document_title = report.document_title or 'Untitled Report'
            report.project_reference = report.project_reference or 'N/A'
            
            # Use pre-loaded sat_report data (no additional query needed)
            try:
                if report.sat_report and report.sat_report.data_json:
                    data = json.loads(report.sat_report.data_json)
                    context_data = data.get('context', {})
                    if context_data.get('DOCUMENT_TITLE'):
                        report.document_title = context_data['DOCUMENT_TITLE']
                    if context_data.get('PROJECT_REFERENCE'):
                        report.project_reference = context_data['PROJECT_REFERENCE']
            except Exception:
                # Silent fail to prevent log spam and hanging
                pass

            # Keep the actual database status - don't compute it from approvals!
            # The status field should reflect the true report state
            # Normalize to lowercase for display consistency
            report.status = report.status.lower() if report.status else 'draft'
                    
    except Exception as e:
        current_app.logger.error(f"Could not retrieve report statistics for admin: {e}", exc_info=True)
        total_reports = 0
        recent_reports = []

    # Get settings
    company_logo = SystemSettings.get_setting('company_logo', 'static/cully.png')
    storage_settings, storage_audit_entries, _ = _get_storage_settings_payload()
    storage_location = storage_settings.get('upload_root')

    return render_template('admin_dashboard.html',
                         users=users,
                         total_users=total_users,
                         pending_users=pending_users_count,
                         total_reports=total_reports,
                         db_status=db_connected,
                         pending_users_list=pending_users_list,
                         storage_location=storage_location,
                         storage_settings=storage_settings,
                         storage_audit_entries=storage_audit_entries,
                         company_logo=company_logo,
                         recent_reports=recent_reports)

@dashboard_bp.route('/engineer')
@role_required(['Engineer'])
@no_cache
def engineer():
    """Engineer dashboard"""
    current_app.logger.info(f"Fetching dashboard for user: {current_user.email}")

    # Get unread notifications count
    try:
        unread_count = Notification.query.filter_by(
            user_email=current_user.email,
            read=False
        ).count()
    except Exception as e:
        current_app.logger.warning(f"Could not get unread count for engineer: {e}")
        unread_count = 0

    # Get report statistics for current user
    user_reports = Report.query.filter_by(user_email=current_user.email).order_by(Report.updated_at.desc()).all()
    current_app.logger.info(f"Found {len(user_reports)} reports for user {current_user.email}")

    # Calculate statistics
    draft_reports = 0
    pending_reports = 0
    rejected_reports = 0
    approved_reports = 0

    for report in user_reports:
        current_app.logger.info(f"Report {report.id} has status: {report.status}")
        if report.status == 'DRAFT':
            draft_reports += 1
        elif report.status == 'PENDING':
            pending_reports += 1
        elif report.status == 'REJECTED':
            rejected_reports += 1
        elif report.status == 'APPROVED':
            approved_reports += 1

    stats = {
        'draft': draft_reports,
        'pending': pending_reports,
        'rejected': rejected_reports,
        'approved': approved_reports
    }
    current_app.logger.info(f"Calculated stats: {stats}")

    return render_template('engineer_dashboard.html', stats=stats, reports=user_reports, unread_count=unread_count)

@dashboard_bp.route('/automation_manager')
@role_required(['Automation Manager'])
@no_cache
def automation_manager():
    """Automation Manager dashboard"""
    # Get unread notifications count
    try:
        unread_count = Notification.query.filter_by(
            user_email=current_user.email,
            read=False
        ).count()
    except Exception as e:
        current_app.logger.warning(f"Could not get unread count for Automation Manager: {e}")
        unread_count = 0

    # Get pending reports for Automation Manager (Stage 1 approval)
    pending_reports = []
    pending_approvals = 0
    
    try:
        # Get all reports with PENDING status
        all_reports = Report.query.filter_by(status='PENDING').all()
        current_app.logger.info(f"Automation Manager: Found {len(all_reports)} PENDING reports")
        
        for report in all_reports:
            if report.approvals_json:
                try:
                    approvals = json.loads(report.approvals_json)
                    # Find stage 1 approval for Automation Manager
                    for approval in approvals:
                        if (approval.get('stage') == 1 and 
                            approval.get('approver_email') == current_user.email and 
                            approval.get('status') == 'pending'):
                            
                            # Get additional data from SAT report
                            sat_report = SATReport.query.filter_by(report_id=report.id).first()
                            if sat_report and sat_report.data_json:
                                try:
                                    data = json.loads(sat_report.data_json)
                                    context_data = data.get('context', {})
                                    report.document_title = context_data.get('DOCUMENT_TITLE', report.document_title or 'Untitled')
                                    report.project_reference = context_data.get('PROJECT_REFERENCE', report.project_reference or 'N/A')
                                    report.client_name = context_data.get('CLIENT_NAME', report.client_name or 'N/A')
                                    report.prepared_by = context_data.get('PREPARED_BY', report.prepared_by or 'N/A')
                                except:
                                    pass
                            
                            # Add approval stage info
                            report.approval_stage = 1
                            report.approval_url = url_for('approval.approve_submission', 
                                                         submission_id=report.id, 
                                                         stage=1)
                            pending_reports.append(report)
                            pending_approvals += 1
                            current_app.logger.info(f"Found pending approval for AM: Report {report.id}")
                            break
                except json.JSONDecodeError:
                    current_app.logger.warning(f"Could not decode approvals_json for report {report.id}")
                    continue
        
        current_app.logger.info(f"Automation Manager has {pending_approvals} pending approvals")
        
    except Exception as e:
        current_app.logger.error(f"Error getting pending approvals for Automation Manager: {e}")
    
    # Test database connection
    try:
        db_status = test_db_connection()
    except Exception as e:
        current_app.logger.warning(f"Database connection test failed: {e}")
        db_status = False

    stats = get_cached_dashboard_stats('Automation Manager', current_user.email)
    if not stats:
        try:
            stats = compute_and_cache_dashboard_stats('Automation Manager', current_user.email)
        except Exception as exc:
            current_app.logger.error(
                "Failed to compute Automation Manager dashboard stats for %s: %s",
                current_user.email,
                exc,
                exc_info=exc
            )
            stats = EMPTY_DASHBOARD_STATS.copy()

    completed_automations = stats.get('approved', 0)

    # Get recent reports (limit to 5 for display)
    recent_reports = Report.query.order_by(Report.updated_at.desc()).limit(5).all()

    return render_template('automation_manager_dashboard.html',
                           stats=stats,
                           pending_reports=pending_reports,
                           recent_reports=recent_reports,
                           unread_count=unread_count,
                           automation_count=len(pending_reports),
                           pending_workflows=pending_approvals,
                           completed_automations=completed_automations,
                           db_status=db_status)

@dashboard_bp.route('/automation-manager-reviews')
@role_required(['Automation Manager'])
@no_cache
def automation_manager_reviews():
    """Automation Manager reviews page - alias for dashboard"""
    return redirect(url_for('dashboard.automation_manager'))

@dashboard_bp.route('/pm')
@role_required(['PM'])
@no_cache
def pm():
    """Project Manager dashboard"""
    # Get unread notifications count
    try:
        unread_count = Notification.query.filter_by(
            user_email=current_user.email,
            read=False
        ).count()
    except Exception as e:
        current_app.logger.warning(f"Could not get unread count for PM: {e}")
        unread_count = 0

    pm_email = (current_user.email or '').lower()

    def _enrich_sat_metadata(report):
        """Fill in SAT metadata used on the dashboard cards."""
        if getattr(report, 'type', '') != 'SAT':
            return report
        sat_report = SATReport.query.filter_by(report_id=report.id).first()
        if sat_report and sat_report.data_json:
            try:
                data = json.loads(sat_report.data_json)
                context_data = data.get('context', {})
                report.document_title = context_data.get('DOCUMENT_TITLE', report.document_title or 'Untitled')
                report.project_reference = context_data.get('PROJECT_REFERENCE', report.project_reference or 'N/A')
                report.client_name = context_data.get('CLIENT_NAME', report.client_name or 'N/A')
                report.prepared_by = context_data.get('PREPARED_BY', report.prepared_by or 'N/A')
            except json.JSONDecodeError:
                current_app.logger.warning(f"Could not decode SAT report data for report {report.id}")
        return report

    # Get pending reports for PM (Stage 2 approval)
    pending_reports = []
    pending_deliverables = 0
    
    try:
        # Get all reports with PENDING status
        all_reports = Report.query.filter_by(status='PENDING').all()
        current_app.logger.info(f"PM: Found {len(all_reports)} PENDING reports")
        
        for report in all_reports:
            if report.approvals_json:
                try:
                    approvals = json.loads(report.approvals_json)
                    
                    # Check if stage 1 is approved (AM approved)
                    stage1_approved = any(
                        str(a.get('stage')) == '1' and (a.get('status') or '').lower() == 'approved'
                        for a in approvals
                    )
                    
                    if stage1_approved:
                        # Find stage 2 approval for PM
                        for approval in approvals:
                            approval_email = (approval.get('approver_email') or '').strip().lower()
                            approval_status = (approval.get('status') or '').strip().lower() or 'pending'
                            is_pm_stage = str(approval.get('stage')) == '2'
                            if (
                                is_pm_stage
                                and approval_email == pm_email
                                and approval_status in ['pending', 'in_review']
                            ):

                                _enrich_sat_metadata(report)
                                
                                # Add approval stage info
                                stage_number = approval.get('stage') or 2
                                report.approval_stage = stage_number
                                report.approval_url = url_for(
                                    'approval.approve_submission', 
                                    submission_id=report.id, 
                                    stage=stage_number
                                )
                                pending_reports.append(report)
                                pending_deliverables += 1
                                current_app.logger.info(f"Found pending approval for PM: Report {report.id}")
                                break
                except json.JSONDecodeError:
                    current_app.logger.warning(f"Could not decode approvals_json for report {report.id}")
                    continue
        
        current_app.logger.info(f"PM has {pending_deliverables} pending approvals")
        
    except Exception as e:
        current_app.logger.error(f"Error getting pending approvals for PM: {e}")
    
    stats = get_cached_dashboard_stats('PM', current_user.email)
    if not stats:
        try:
            stats = compute_and_cache_dashboard_stats('PM', current_user.email)
        except Exception as exc:
            current_app.logger.error(
                "Failed to compute PM dashboard stats for %s: %s",
                current_user.email,
                exc,
                exc_info=exc
            )
            stats = EMPTY_DASHBOARD_STATS.copy()

    # Get recent reports for PM - only after Automation Manager approval
    recent_reports = []
    try:
        candidates = Report.query.order_by(Report.updated_at.desc()).limit(50).all()
        for report in candidates:
            if not report.approvals_json:
                continue
            try:
                approvals = json.loads(report.approvals_json)
            except json.JSONDecodeError:
                current_app.logger.warning(f"Could not decode approvals_json for report {report.id}")
                continue

            stage1_approved = any(
                str(approval.get('stage')) == '1' and (approval.get('status') or '').lower() == 'approved'
                for approval in approvals
            )
            pm_assigned = any(
                str(approval.get('stage')) == '2' and (approval.get('approver_email') or '').lower() == pm_email
                for approval in approvals
            )

            if not (stage1_approved and pm_assigned):
                continue

            _enrich_sat_metadata(report)
            recent_reports.append(report)
            if len(recent_reports) >= 5:
                break
    except Exception as exc:
        current_app.logger.warning(f"Could not build PM recent reports: {exc}")

    return render_template('pm_dashboard.html',
                             pending_deliverables=pending_deliverables,
                             recent_reports=recent_reports,
                             pending_reports=pending_reports,
                             unread_count=unread_count,
                             stats=stats)

# Legacy redirects for dashboard routes
@dashboard_bp.route('/technical-manager')
@role_required(['Automation Manager'])
def technical_manager():
    """Legacy redirect for TM dashboard"""
    return redirect(url_for('dashboard.automation_manager'))

@dashboard_bp.route('/project-manager')
@role_required(['PM'])
def project_manager():
    """Legacy redirect for PM dashboard"""
    return redirect(url_for('dashboard.pm'))

@dashboard_bp.route('/profile/settings', methods=['GET', 'POST'])
@login_required
def profile_settings():
    """Allow any user to manage their saved signature"""
    key = f"user_signature_{current_user.id}"
    existing_signature = SystemSettings.get_setting(key, None)
    error = None

    if request.method == 'POST':
        upload = request.files.get('signature_file')
        if not upload or not upload.filename:
            error = 'Please choose a PNG/JPG file to upload.'
        else:
            ext = upload.filename.rsplit('.', 1)[-1].lower()
            if ext not in ['png', 'jpg', 'jpeg']:
                error = 'Only PNG or JPG files are allowed for signatures.'
            else:
                try:
                    filename = secure_filename(upload.filename)
                    unique_name = f"user_{current_user.id}_{int(time.time())}_{filename}"
                    sig_dir = current_app.config.get('SIGNATURES_FOLDER', os.path.join(current_app.root_path, 'static', 'signatures'))
                    os.makedirs(sig_dir, exist_ok=True)
                    save_path = os.path.join(sig_dir, unique_name)
                    upload.save(save_path)

                    SystemSettings.set_setting(key, unique_name)
                    existing_signature = unique_name
                    flash('Signature uploaded successfully. It will be used automatically for prepared-by.', 'success')
                except Exception as e:
                    current_app.logger.error(f"Error saving profile signature: {e}", exc_info=True)
                    error = 'Could not save signature. Please try again.'

        if error:
            flash(error, 'error')

    # Build a preview URL if we have a saved file
    preview_url = None
    if existing_signature:
        try:
            preview_url = url_for('static', filename=f"signatures/{existing_signature}")
        except Exception:
            preview_url = None

    return render_template('profile_settings.html', signature_url=preview_url, signature_filename=existing_signature)

@dashboard_bp.route('/user-management')
@admin_required
def user_management():
    """User management page"""
    status_filter = request.args.get('status', 'All')

    if status_filter == 'All':
        users = User.query.all()
    else:
        users = User.query.filter_by(status=status_filter).all()

    return render_template('user_management.html', users=users, current_filter=status_filter)

@dashboard_bp.route('/approve-user/<int:user_id>', methods=['POST'])
@admin_required
def approve_user(user_id):
    """Approve a user and assign role, then send approval email"""
    user = User.query.get_or_404(user_id)
    role = request.form.get('role')

    if role not in ['Admin', 'Engineer', 'Automation Manager', 'PM']:
        flash('Invalid role selection.', 'error')
        return redirect(url_for('dashboard.user_management'))

    user.role = role
    user.status = 'Active'

    try:
        db.session.commit()
        flash(f'User {user.full_name} approved as {role}.', 'success')
        
        # Automatically send approval email
        email_sent = _send_user_approval_email(user)
        if email_sent:
            flash(f'Approval email sent to {user.email}.', 'success')
        else:
            flash(f'User approved but email could not be sent. Use "Resend Email" to try again.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to approve user {user.full_name} ({user_id}): {e}")
        flash('Failed to approve user.', 'error')

    return redirect(url_for('dashboard.user_management'))


def _send_user_approval_email(user):
    """Helper function to send approval email to a user."""
    try:
        from services.user_email_service import generate_user_approval_email
        from utils import send_email
        
        # Build login URL
        login_url = url_for('auth.login', _external=True)
        
        user_data = {
            'full_name': user.full_name,
            'email': user.email,
            'role': user.role,
            'company_name': 'Cully Automation',
            'login_url': login_url
        }
        
        # Generate AI-written email
        email_content = generate_user_approval_email(user_data)
        
        # Send the email
        success = send_email(
            to_email=user.email,
            subject=email_content['subject'],
            html_content=email_content['body'],
            text_content=email_content.get('text')
        )
        
        if success:
            current_app.logger.info(f"Approval email sent to {user.email}")
        else:
            current_app.logger.warning(f"Failed to send approval email to {user.email}")
        
        return success
        
    except Exception as e:
        current_app.logger.error(f"Error sending approval email to {user.email}: {e}", exc_info=True)
        return False


@dashboard_bp.route('/send-user-email/<int:user_id>', methods=['POST'])
@admin_required
def send_user_email(user_id):
    """Send or resend approval/welcome email to a user"""
    user = User.query.get_or_404(user_id)
    email_type = request.form.get('email_type', 'approval')
    
    try:
        from services.user_email_service import generate_user_approval_email, generate_welcome_email
        from utils import send_email
        
        login_url = url_for('auth.login', _external=True)
        
        user_data = {
            'full_name': user.full_name,
            'email': user.email,
            'role': user.role,
            'company_name': 'Cully Automation',
            'login_url': login_url
        }
        
        # Generate email based on type
        if email_type == 'welcome':
            email_content = generate_welcome_email(user_data)
        else:
            email_content = generate_user_approval_email(user_data)
        
        # Send the email
        success = send_email(
            to_email=user.email,
            subject=email_content['subject'],
            html_content=email_content['body'],
            text_content=email_content.get('text')
        )
        
        if success:
            current_app.logger.info(f"Email ({email_type}) sent to {user.email} by admin {current_user.email}")
            if request.is_json:
                return jsonify({'success': True, 'message': f'Email sent successfully to {user.email}'})
            flash(f'Email sent successfully to {user.email}.', 'success')
        else:
            current_app.logger.warning(f"Failed to send email to {user.email}")
            if request.is_json:
                return jsonify({'success': False, 'error': 'Failed to send email. Check SMTP configuration.'}), 500
            flash('Failed to send email. Please check email configuration.', 'error')
            
    except Exception as e:
        current_app.logger.error(f"Error sending email to {user.email}: {e}", exc_info=True)
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        flash(f'Error sending email: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.user_management'))

@dashboard_bp.route('/disable-user/<int:user_id>', methods=['POST'])
@admin_required
def disable_user(user_id):
    """Disable a user"""
    user = User.query.get_or_404(user_id)

    if user.email == current_user.email:
        flash('You cannot disable your own account.', 'error')
        return redirect(url_for('dashboard.user_management'))

    user.status = 'Disabled'

    try:
        db.session.commit()
        flash(f'User {user.full_name} disabled.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to disable user {user.full_name} ({user_id}): {e}")
        flash('Failed to disable user.', 'error')

    return redirect(url_for('dashboard.user_management'))

@dashboard_bp.route('/enable-user/<int:user_id>', methods=['POST'])
@admin_required
def enable_user(user_id):
    """Enable a user"""
    user = User.query.get_or_404(user_id)
    user.status = 'Active'

    try:
        db.session.commit()
        flash(f'User {user.full_name} enabled.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to enable user {user.full_name} ({user_id}): {e}")
        flash('Failed to enable user.', 'error')

    return redirect(url_for('dashboard.user_management'))

@dashboard_bp.route('/change-user-role/<int:user_id>', methods=['POST'])
@admin_required
def change_user_role(user_id):
    """Change a user's role"""
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')

    if user.email == current_user.email:
        flash('You cannot change your own role.', 'error')
        return redirect(url_for('dashboard.user_management'))

    if new_role not in ['Admin', 'Engineer', 'Automation Manager', 'PM']:
        flash('Invalid role selection.', 'error')
        return redirect(url_for('dashboard.user_management'))

    old_role = user.role
    user.role = new_role

    try:
        db.session.commit()
        flash(f'User {user.full_name} role changed from {old_role} to {new_role}.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to change role for user {user.full_name} ({user_id}): {e}")
        flash('Failed to change user role.', 'error')

    return redirect(url_for('dashboard.user_management'))

@dashboard_bp.route('/update-user-name/<int:user_id>', methods=['POST'])
@admin_required
def update_user_name(user_id):
    """Update a user's name (admin only)"""
    user = User.query.get_or_404(user_id)
    
    # Get new name from form or JSON
    if request.is_json:
        new_name = request.json.get('name', '').strip()
    else:
        new_name = request.form.get('name', '').strip()
    
    if not new_name:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Name cannot be empty'}), 400
        flash('Name cannot be empty.', 'error')
        return redirect(url_for('dashboard.user_management'))
    
    if len(new_name) < 2:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Name must be at least 2 characters'}), 400
        flash('Name must be at least 2 characters.', 'error')
        return redirect(url_for('dashboard.user_management'))
    
    if len(new_name) > 100:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Name cannot exceed 100 characters'}), 400
        flash('Name cannot exceed 100 characters.', 'error')
        return redirect(url_for('dashboard.user_management'))
    
    old_name = user.full_name
    user.full_name = new_name
    
    try:
        db.session.commit()
        current_app.logger.info(f"Admin {current_user.email} changed user name from '{old_name}' to '{new_name}' for user ID {user_id}")
        if request.is_json:
            return jsonify({'success': True, 'message': f'Name updated successfully', 'new_name': new_name})
        flash(f'User name changed from "{old_name}" to "{new_name}".', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update name for user {user_id}: {e}")
        if request.is_json:
            return jsonify({'success': False, 'error': 'Failed to update name'}), 500
        flash('Failed to update user name.', 'error')
    
    return redirect(url_for('dashboard.user_management'))

@dashboard_bp.route('/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user permanently"""
    user = User.query.get_or_404(user_id)

    if user.email == current_user.email:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('dashboard.user_management'))

    user_name = user.full_name
    user_email = user.email

    try:
        # Delete associated notifications first (to maintain referential integrity)
        Notification.query.filter_by(user_email=user_email).delete(synchronize_session=False)

        # The deletion of the user will cascade to api_keys and api_usage tables
        # thanks to the `ondelete='CASCADE'` setting in the models.

        # Delete the user
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user_name} ({user_email}) has been permanently deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete user {user_name} ({user_email}, ID: {user_id}): {e}")
        flash(f'Failed to delete user: {str(e)}', 'error')

    return redirect(url_for('dashboard.user_management'))

@dashboard_bp.route('/system-settings')
@admin_required
def system_settings():
    """System settings page"""
    from models import SystemSettings
    company_logo = SystemSettings.get_setting('company_logo', 'static/cully.png')
    storage_location = SystemSettings.get_setting('default_storage_location', '/outputs/')

    return render_template('system_settings.html',
                         company_logo=company_logo,
                         storage_location=storage_location)

@dashboard_bp.route('/update-settings', methods=['POST'])
@admin_required
def update_settings():
    """Update system settings"""
    from models import SystemSettings
    storage_location = request.form.get('storage_location', '').strip()

    if storage_location:
        SystemSettings.set_setting('default_storage_location', storage_location)
        flash('Settings saved successfully.', 'success')
    else:
        flash('Storage location is required.', 'error')

    return redirect(url_for('dashboard.system_settings'))

@dashboard_bp.route('/refresh-cully-stats', methods=['POST'])
@admin_required
def refresh_cully_stats():
    """Manually refresh Cully statistics"""
    try:

        
        # Fetch updated statistics
        success = CullyStatistics.fetch_and_update_from_cully()
        
        if success:
            stats = CullyStatistics.get_current_statistics()
            flash(f'Cully statistics refreshed successfully! Current stats: {stats["instruments"]} instruments, {stats["engineers"]} engineers, {stats["experience"]} years experience, {stats["plants"]} water plants.', 'success')
            current_app.logger.info(f"Manual Cully stats refresh successful: {stats}")
        else:
            flash('Failed to refresh Cully statistics. Using cached data.', 'warning')
            current_app.logger.warning("Manual Cully stats refresh failed")
            
    except Exception as e:
        current_app.logger.error(f"Error during manual Cully stats refresh: {e}")
        flash(f'Error refreshing statistics: {str(e)}', 'error')
    
    return redirect(url_for('dashboard.system_settings'))

@dashboard_bp.route('/api/cully-stats')
@admin_required
def api_cully_stats():
    """API endpoint to get current Cully statistics"""
    try:

        
        stats = CullyStatistics.get_current_statistics()
        stats_record = CullyStatistics.query.first()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'last_sync_successful': stats_record.fetch_successful if stats_record else True,
            'error_message': stats_record.error_message if stats_record else None
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching Cully stats via API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@dashboard_bp.route('/reports')
@admin_required
def admin_reports():
    """Admin reports view - show all system reports"""

    
    try:
        # Calculate this month start for template
        now = datetime.now()
        this_month_start = datetime(now.year, now.month, 1)
        
        # Get all reports - don't filter, get everything
        reports = Report.query.order_by(Report.created_at.desc()).all()
        reports_data = []
        
        current_app.logger.info(f"Admin reports: Found {len(reports)} total reports in database")
        
        for report in reports:
            try:
                # Get SAT report data if it exists
                sat_report = SATReport.query.filter_by(report_id=report.id).first()
                
                # Start with basic report data
                project_name = report.document_title or 'Untitled Report'
                client_name = report.client_name or ''
                location = report.project_reference or ''
                status = 'Draft'
                
                # If SAT report exists, try to get enhanced data
                if sat_report and sat_report.data_json:
                    try:
                        stored_data = json.loads(sat_report.data_json)
                        context_data = stored_data.get('context', {})
                        
                        # Override with SAT data if available
                        if context_data.get('DOCUMENT_TITLE'):
                            project_name = context_data['DOCUMENT_TITLE']
                        if context_data.get('CLIENT_NAME'):
                            client_name = context_data['CLIENT_NAME']
                        if context_data.get('PROJECT_REFERENCE'):
                            location = context_data['PROJECT_REFERENCE']
                            
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        current_app.logger.warning(f"Could not decode SATReport data for report ID {report.id}: {e}")
                
                # Determine status from approvals
                if report.approvals_json:
                    try:
                        approvals = json.loads(report.approvals_json)
                        if approvals:
                            statuses = [a.get("status", "pending") for a in approvals]
                            if "rejected" in statuses:
                                status = "Rejected"
                            elif all(s == "approved" for s in statuses):
                                status = "Approved"
                            elif any(s == "approved" for s in statuses):
                                status = "Partially Approved"
                            else:
                                status = "Pending Review"
                        else:
                            status = "Draft"
                    except (json.JSONDecodeError, TypeError):
                        status = "Pending Review"
                else:
                    status = "Draft"
                
                # Add report to list
                reports_data.append({
                    'id': report.id,
                    'project_name': project_name,
                    'client_name': client_name,
                    'location': location,
                    'created_by': report.user_email,
                    'status': status,
                    'created_date': report.created_at
                })
                
                current_app.logger.debug(f"Processed report {report.id}: {project_name}")
                
            except Exception as report_error:
                current_app.logger.error(f"Error processing report {report.id}: {report_error}", exc_info=True)
                # Add basic report info even if processing fails
                reports_data.append({
                    'id': report.id,
                    'project_name': report.document_title or f'Report {report.id}',
                    'client_name': report.client_name or '',
                    'location': report.project_reference or '',
                    'created_by': report.user_email,
                    'status': 'Error',
                    'created_date': report.created_at
                })
        
        current_app.logger.info(f"Admin reports: Successfully processed {len(reports_data)} reports for display")
        
        return render_template('admin_reports.html', 
                             reports=reports_data,
                             this_month_start=this_month_start)
        
    except Exception as e:
        current_app.logger.error(f"Error in admin_reports function: {e}", exc_info=True)
        
        # Try to get basic report count for debugging
        try:
            report_count = Report.query.count()
            current_app.logger.info(f"Database has {report_count} reports total")
        except Exception as count_error:
            current_app.logger.error(f"Cannot even count reports: {count_error}")
            
        # Still provide this_month_start even on error
        now = datetime.now()
        this_month_start = datetime(now.year, now.month, 1)
        return render_template('admin_reports.html', 
                             reports=[],
                             this_month_start=this_month_start)

@dashboard_bp.route('/create-report')
@role_required(['Engineer'])
def create_report():
    """Create report - redirect to report type selector"""
    return redirect(url_for('reports.new'))

@dashboard_bp.route('/db-status')
@login_required
def db_status():
    """Check database connection status"""
    try:
        # Try to connect to database
        db.engine.connect().close()
        return jsonify({'status': 'connected', 'message': 'Database connection successful'})
    except Exception as e:
        current_app.logger.error(f"Database status check failed: {e}")
        return jsonify({'status': 'error', 'message': f'Database connection failed: {str(e)}'}), 500

@dashboard_bp.route('/dashboard/api/admin/users')
@admin_required
def api_admin_users():
    """API endpoint for user management data"""
    try:
        users = User.query.all()
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role,
                'status': user.status,
                'created_date': user.created_date.isoformat() if user.created_date else None
            })

        return jsonify({
            'success': True,
            'users': users_data
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching users: {e}")
        return jsonify({'success': False, 'error': str(e)})

@dashboard_bp.route('/dashboard/api/admin/reports')
@admin_required
def api_admin_reports():
    """API endpoint for reports data"""
    try:
        reports = Report.query.order_by(Report.created_at.desc()).limit(50).all()
        reports_data = []

        for report in reports:
            # Get report title from SAT data if available
            title = 'Untitled Report'
            if hasattr(report, 'sat_report') and report.sat_report:
                try:
                    data = json.loads(report.sat_report.data_json)
                    title = data.get('context', {}).get('DOCUMENT_TITLE', 'Untitled Report')
                except:
                    pass

            # Determine status
            status = 'pending'
            if report.approvals_json:
                try:
                    approvals = json.loads(report.approvals_json)
                    statuses = [a.get("status", "pending") for a in approvals]
                    if "rejected" in statuses:
                        status = "rejected"
                    elif all(s == "approved" for s in statuses):
                        status = "approved"
                    elif any(s == "approved" for s in statuses):
                        status = "partially_approved"
                except:
                    pass

            reports_data.append({
                'id': report.id,
                'title': title,
                'user_email': report.user_email,
                'status': status,
                'created_at': report.created_at.isoformat() if report.created_at else None
            })

        return jsonify({
            'success': True,
            'reports': reports_data
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching reports: {e}")
        return jsonify({'success': False, 'error': str(e)})

@dashboard_bp.route('/dashboard/api/admin/settings', methods=['GET', 'POST'])
@admin_required
def api_admin_settings():
    """API endpoint for storage system settings management."""
    from models import SystemSettings

    if request.method == 'GET':
        storage_settings, audits, error = _get_storage_settings_payload()
        company_logo = SystemSettings.get_setting('company_logo', 'static/cully.png')
        response = {
            'success': error is None,
            'settings': storage_settings,
            'audits': audits,
            'company_logo': company_logo,
        }
        if error:
            response['error'] = error
        return jsonify(response)

    data = request.get_json(silent=True) or {}
    allowed_keys = {
        'upload_root',
        'image_storage_limit_gb',
        'active_quality',
        'approved_quality',
        'archive_quality',
        'preferred_formats',
    }
    payload = {key: data.get(key) for key in allowed_keys if key in data}
    expected_version = data.get('version')

    try:
        updated = StorageSettingsService.update_settings(
            payload=payload,
            actor_email=current_user.email,
            actor_id=getattr(current_user, 'id', None),
            expected_version=expected_version,
            ip_address=request.remote_addr,
        ).to_dict()
        storage_config = StorageConfig.query.filter_by(
            org_id=updated['org_id'],
            environment=updated['environment'],
        ).first()
        audits = []
        if storage_config:
            audits = [
                entry.to_dict()
                for entry in StorageSettingsAudit.query.filter_by(storage_config_id=storage_config.id)
                .order_by(StorageSettingsAudit.created_at.desc())
                .limit(20)
                .all()
            ]
        return jsonify({'success': True, 'settings': updated, 'audits': audits})
    except StorageSettingsValidationError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    except StorageSettingsConcurrencyError as exc:
        return jsonify({'success': False, 'error': str(exc), 'code': 'conflict'}), 409
    except StorageSettingsError as exc:
        current_app.logger.error('Storage settings update failed: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500
    except Exception as exc:
        current_app.logger.error('Unexpected error updating storage settings: %s', exc, exc_info=True)
        return jsonify({'success': False, 'error': 'Unexpected error occurred'}), 500


@dashboard_bp.route('/dashboard/api/admin/stats')
@admin_required
def api_admin_stats():
    """API endpoint for dashboard statistics"""
    try:
        users = User.query.all()
        total_users = len(users)
        pending_users = len([u for u in users if u.status == 'Pending'])
        total_reports = Report.query.count()

        return jsonify({
            'success': True,
            'stats': {
                'total_users': total_users,
                'pending_users': pending_users,
                'total_reports': total_reports
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching stats: {e}")
        return jsonify({'success': False, 'error': str(e)})

@dashboard_bp.route('/debug/reports')
@admin_required
def debug_reports():
    """Debug endpoint to check report data"""
    try:

        
        # Get basic report count
        total_reports = Report.query.count()
        
        # Get all reports with basic info
        reports = Report.query.all()
        report_info = []
        
        for report in reports:
            sat_report = SATReport.query.filter_by(report_id=report.id).first()
            report_info.append({
                'id': report.id,
                'type': report.type,
                'user_email': report.user_email,
                'document_title': report.document_title,
                'created_at': str(report.created_at),
                'has_sat_data': sat_report is not None
            })
        
        return jsonify({
            'success': True,
            'total_reports': total_reports,
            'reports': report_info
        })
        
    except Exception as e:
        current_app.logger.error(f"Debug reports error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@dashboard_bp.route('/revoke-approval/<report_id>', methods=['POST'])
@admin_required
def revoke_approval(report_id):
    """Revoke approval for a report"""
    try:
        report = Report.query.get(report_id)
        if not report:
            return jsonify({'success': False, 'message': 'Report not found'}), 404
        
        # Get the comment from request
        data = request.get_json()
        comment = data.get('comment', '').strip()
        
        if not comment:
            return jsonify({'success': False, 'message': 'Comment is required for revocation'}), 400
        
        # Check if report has approval workflow before resetting
        current_approvals = json.loads(report.approvals_json) if report.approvals_json else []
        
        if not current_approvals:
            # If no approval workflow exists, just unlock the report
            report.locked = False
            report.status = 'DRAFT'
        else:
            # Reset approvals and unlock the report
            report.approvals_json = json.dumps([])
            report.locked = False
            report.status = 'DRAFT'
        
        # Create notification for the report creator
        try:
            Notification.create_notification(
                user_email=report.user_email,
                title='Report Approval Revoked',
                message=f'Your report "{report.document_title or "SAT Report"}" approval has been revoked by admin. Reason: {comment}',
                notification_type='approval_revoked',
                submission_id=report_id,
                action_url=f'/status/{report_id}'
            )
        except Exception as notif_error:
            current_app.logger.warning(f"Could not create notification: {notif_error}")
        
        db.session.commit()
        
        current_app.logger.info(f"Report {report_id} approval revoked by admin {current_user.email}. Reason: {comment}")
        return jsonify({
            'success': True, 
            'message': 'Report unlocked and status reset successfully. You can now edit the report.'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error revoking approval for report {report_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to revoke approval'}), 500

@dashboard_bp.route('/delete-report/<report_id>', methods=['POST'])
@login_required
def delete_report(report_id):
    """Delete a report with role-based safeguards."""
    try:
        report = Report.query.get(report_id)
        if not report:
            return jsonify({'success': False, 'message': 'Report not found'}), 404

        is_admin = current_user.role == 'Admin'

        if not is_admin:
            if report.user_email != current_user.email:
                current_app.logger.warning(
                    "User %s attempted to delete report %s they do not own.",
                    current_user.email,
                    report_id,
                )
                return jsonify({'success': False, 'message': 'You are not permitted to delete this report.'}), 403

            status_upper = (report.status or 'DRAFT').upper()
            approvals = []
            has_stage_approved = False
            if report.approvals_json:
                try:
                    approvals = json.loads(report.approvals_json)
                    has_stage_approved = any(
                        (approval.get('status') or '').lower() == 'approved'
                        for approval in approvals
                    )
                except json.JSONDecodeError:
                    has_stage_approved = False

            if has_stage_approved or status_upper in ['APPROVED', 'REJECTED']:
                return jsonify({
                    'success': False,
                    'message': 'This report has been approved/rejected and can only be deleted by an administrator.'
                }), 403

        sat_report = SATReport.query.filter_by(report_id=report_id).first()
        if sat_report:
            db.session.delete(sat_report)
            db.session.flush()

        cleanup_statements = [
            ('sat_reports', 'report_id'),
            ('fds_reports', 'report_id'),
            ('hds_reports', 'report_id'),
            ('site_survey_reports', 'report_id'),
            ('sds_reports', 'report_id'),
            ('fat_reports', 'report_id'),
            ('report_edits', 'report_id'),
            ('report_versions', 'report_id'),
            ('report_comments', 'report_id'),
            ('notifications', 'related_submission_id'),
        ]
        for table_name, column_name in cleanup_statements:
            try:
                db.session.execute(
                    text(f"DELETE FROM {table_name} WHERE {column_name} = :rid"),
                    {"rid": report_id},
                )
            except (ProgrammingError, OperationalError) as cleanup_error:
                current_app.logger.warning(
                    "Skipping cleanup for %s due to schema mismatch: %s",
                    table_name,
                    cleanup_error,
                )

        db.session.expunge(report)
        db.session.execute(
            text("DELETE FROM reports WHERE id = :rid"),
            {"rid": report_id},
        )
        db.session.commit()

        current_app.logger.info(
            "Report %s deleted by %s",
            report_id,
            current_user.email,
        )
        return jsonify({'success': True, 'message': 'Report deleted successfully'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting report {report_id}: {e}")
        return jsonify({'success': False, 'message': 'Failed to delete report'}), 500

@dashboard_bp.route('/my-reports')
@role_required(['Engineer', 'Automation Manager', 'PM'])
def my_reports():
    """View reports relevant to the current user"""

    pm_email = (current_user.email or '').lower()

    # Build reports queryset based on role
    if current_user.role == 'Engineer':
        reports_query = Report.query.filter_by(user_email=current_user.email)
    elif current_user.role == 'Automation Manager':
        approver_match = f'"approver_email": "{current_user.email}"'
        reports_query = Report.query.filter(
            or_(
                Report.user_email == current_user.email,
                and_(
                    Report.approvals_json.isnot(None),
                    Report.approvals_json.contains(approver_match)
                )
            )
        )
    else:
        approver_match = f'"approver_email": "{current_user.email}"'
        stage_match = '"stage": 2'
        reports_query = Report.query.filter(
            or_(
                Report.user_email == current_user.email,
                and_(
                    Report.approvals_json.isnot(None),
                    Report.approvals_json.contains(approver_match),
                    Report.approvals_json.contains(stage_match)
                )
            )
        )
    reports = reports_query.order_by(Report.updated_at.desc()).all()

    report_list = []
    for report in reports:
        approvals_raw = []
        has_stage_approved = False
        pm_assigned = current_user.role != 'PM'
        stage1_approved_for_pm = current_user.role != 'PM'

        if report.approvals_json:
            try:
                approvals_raw = json.loads(report.approvals_json)
                has_stage_approved = any(
                    (stage.get('status') or '').lower() == 'approved'
                    for stage in approvals_raw
                )
                if current_user.role == 'PM':
                    pm_assigned = any(
                        str(stage.get('stage')) == '2'
                        and (stage.get('approver_email') or '').lower() == pm_email
                        for stage in approvals_raw
                    )
                    stage1_approved_for_pm = any(
                        str(stage.get('stage')) == '1'
                        and (stage.get('status') or '').lower() == 'approved'
                        for stage in approvals_raw
                    )
            except json.JSONDecodeError:
                approvals_raw = []
                pm_assigned = current_user.role != 'PM'
                stage1_approved_for_pm = current_user.role != 'PM'

        if current_user.role == 'PM' and not (pm_assigned and stage1_approved_for_pm):
            current_app.logger.info(
                "Skipping report %s for PM %s - awaiting Automation Manager approval or assignment",
                report.id,
                current_user.email,
            )
            continue

        document_title = report.document_title or f"{report.type} Report"
        project_reference = report.project_reference or ''
        client_name = report.client_name or ''

        if report.type == 'SAT':
            sat_report = getattr(report, 'sat_report', None) or SATReport.query.filter_by(report_id=report.id).first()
            if sat_report and sat_report.data_json:
                try:
                    stored_data = json.loads(sat_report.data_json)
                    context = stored_data.get('context', {})
                    document_title = context.get('DOCUMENT_TITLE') or document_title
                    project_reference = context.get('PROJECT_REFERENCE') or project_reference
                    client_name = context.get('CLIENT_NAME') or client_name
                except json.JSONDecodeError:
                    current_app.logger.warning(f"Could not decode SAT report data for report ID: {report.id}")
        elif report.type == 'FDS':
            fds_report = getattr(report, 'fds_report', None) or FDSReport.query.filter_by(report_id=report.id).first()
            if fds_report and fds_report.data_json:
                try:
                    fds_data = json.loads(fds_report.data_json)
                    header = fds_data.get('document_header', {}) or {}
                    document_title = header.get('document_title') or document_title
                    project_reference = header.get('project_reference') or project_reference
                    client_name = header.get('prepared_for') or client_name

                    context = fds_data.get('context', {}) or {}
                    document_title = context.get('DOCUMENT_TITLE') or document_title
                    project_reference = context.get('PROJECT_REFERENCE') or project_reference
                    client_name = context.get('PREPARED_FOR') or client_name
                except json.JSONDecodeError:
                    current_app.logger.warning(f"Could not decode FDS report data for report ID: {report.id}")

        # Fall back to descriptive defaults when metadata is still missing
        if not document_title:
            document_title = f"{report.type} Report"

        # Use the actual status from the database - DO NOT compute from approvals!
        actual_status = report.status if report.status else 'DRAFT'

        # Normalize status for display (convert DRAFT -> draft, etc.)
        normalized_status = actual_status.lower() if actual_status else 'draft'

        status_upper = (actual_status or 'DRAFT').upper()
        is_admin = current_user.role == 'Admin'
        is_owner = report.user_email == current_user.email
        can_delete = False
        delete_reason = ''

        if is_admin:
            can_delete = True
        else:
            if not is_owner:
                delete_reason = 'Only the report owner can delete this report.'
            elif has_stage_approved or status_upper in ['APPROVED', 'REJECTED']:
                delete_reason = 'This report has been approved or rejected; only an administrator may delete it.'
            else:
                can_delete = True

        report_list.append({
            "id": report.id,
            "document_title": document_title,
            "client_name": client_name,
            "project_reference": project_reference,
            "created_at": report.created_at,
            "updated_at": report.updated_at,
            "status": normalized_status,
            "locked": report.locked,
            "user_email": report.user_email,
            "can_delete": can_delete,
            "delete_reason": delete_reason,
            "requires_admin_delete": has_stage_approved or status_upper != 'DRAFT',
            "report_type": report.type
        })
    
    current_app.logger.info(f"Report list for {current_user.email}: {report_list}")
    return render_template('my_reports.html', reports=report_list)

@dashboard_bp.route('/reviews')
@login_required
@role_required(['Automation Manager', 'Admin'])
def reviews():
    """Reviews and Approvals page for Automation Manager"""


    # Get all reports that need approval by this Automation Manager
    pending_reviews = []
    viewer_email = current_user.email.lower()
    viewer_is_admin = current_user.role == 'Admin'
    try:
        all_reports = db.session.query(Report).all()
        for report in all_reports:
            if report.approvals_json:
                try:
                    approvals = json.loads(report.approvals_json)
                    for approval in approvals:
                        if approval.get('stage') != 1 or approval.get('status') != 'pending':
                            continue

                        approver_email = (approval.get('approver_email') or '').lower()

                        # Skip items not assigned to this user unless admin viewing
                        if not viewer_is_admin:
                            if approver_email and approver_email != viewer_email:
                                continue
                            if not approver_email:
                                # If no approver email recorded, fall back to default config
                                default_approvers = current_app.config.get('DEFAULT_APPROVERS', [])
                                stage1_defaults = [
                                    a.get('approver_email', '').lower()
                                    for a in default_approvers
                                    if a.get('stage') == 1
                                ]
                                if stage1_defaults and viewer_email not in stage1_defaults:
                                    continue

                        # Get SAT report data for context
                        sat_report = (
                            db.session.query(SATReport)
                            .filter_by(report_id=report.id)
                            .first()
                        )
                        report_data = {}
                        if sat_report:
                            try:
                                stored_data = json.loads(sat_report.data_json)
                                report_data = stored_data.get('context', {})
                            except json.JSONDecodeError:
                                pass

                        pending_reviews.append({
                            'id': report.id,
                            'document_title': report_data.get('DOCUMENT_TITLE', 'SAT Report'),
                            'client_name': report_data.get('CLIENT_NAME', ''),
                            'project_reference': report_data.get('PROJECT_REFERENCE', ''),
                            'prepared_by': report_data.get('PREPARED_BY', ''),
                            'user_email': report.user_email,
                            'created_at': report.created_at,
                            'updated_at': report.updated_at,
                            'stage': approval.get('stage'),
                            'approver_email': approval.get('approver_email')
                        })
                        break  # Only add once per report
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        current_app.logger.error(f"Error getting pending reviews: {e}")
    
    return render_template('automation_manager_reviews.html', 
                         pending_reviews=pending_reviews,
                         unread_count=0)
