from flask import Blueprint, render_template, redirect, url_for, flash, current_app, send_file, Response, Response
import os
import json
from flask_login import current_user, login_required
from services.sat_tables import build_doc_tables_from_context, migrate_context_tables
import datetime as dt

status_bp = Blueprint('status', __name__)

@status_bp.route('/<submission_id>')
@login_required
def view_status(submission_id):
    """View a specific submission with auto-download"""
    from models import Report, SATReport

    # Check if submission_id is valid
    if not submission_id or submission_id == 'None':
        flash('Invalid submission ID.', 'error')
        return redirect(url_for('dashboard.home'))

    report = Report.query.filter_by(id=submission_id).first()
    if not report:
        flash('Report not found.', 'error')
        return redirect(url_for('dashboard.home'))

    sat_report = SATReport.query.filter_by(report_id=report.id).first()
    if not sat_report:
        flash('Report data not found.', 'error')
        return redirect(url_for('dashboard.home'))

    try:
        stored_data = json.loads(sat_report.data_json) if sat_report.data_json else {}
    except json.JSONDecodeError:
        stored_data = {}

    approvals = json.loads(report.approvals_json) if report.approvals_json else []

    # Determine overall status
    statuses = [a.get("status", "pending") for a in approvals]
    if "rejected" in statuses:
        overall_status = "rejected"
    elif all(status == "approved" for status in statuses):
        overall_status = "approved"
    elif any(status == "approved" for status in statuses):
        overall_status = "partially_approved"
    else:
        overall_status = "pending"

    # Get submission data context with fallbacks
    submission_data = stored_data.get("context", {})
    if not submission_data:
        submission_data = stored_data  # Fallback if context doesn't exist

    # Check if report files exist
    pdf_path = os.path.join(current_app.config['OUTPUT_DIR'], f'SAT_Report_{submission_id}_Final.pdf')
    docx_path = os.path.join(current_app.config['OUTPUT_DIR'], f'SAT_Report_{submission_id}_Final.docx')

    download_available = os.path.exists(pdf_path) or os.path.exists(docx_path)
    has_pdf = os.path.exists(pdf_path)

    # Determine if current user can edit this report
    can_edit = False
    if current_user.role == 'Admin':
        can_edit = True  # Admin can edit any report
    elif current_user.role == 'Engineer' and current_user.email == report.user_email:
        # Engineers can edit their own reports until approved by Automation Manager
        tm_approved = any(a.get("status") == "approved" and a.get("stage") == 1 for a in approvals)
        can_edit = not tm_approved
    elif current_user.role == 'Automation Manager':
        # Automation Manager can edit reports until approved by PM
        pm_approved = any(a.get("status") == "approved" and a.get("stage") == 2 for a in approvals)
        can_edit = not pm_approved

    # Build context similar to old version
    context = {
        "submission_id": submission_id,
        "submission_data": submission_data,
        "approvals": approvals,
        "locked": report.locked,
        "can_edit": can_edit,
        "created_at": report.created_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(report.created_at, dt.datetime) else report.created_at,
        "updated_at": report.updated_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(report.updated_at, dt.datetime) else report.updated_at,
        "user_email": report.user_email,
        "document_title": submission_data.get("DOCUMENT_TITLE", "SAT Report"),
        "project_reference": submission_data.get("PROJECT_REFERENCE", ""),
        "client_name": submission_data.get("CLIENT_NAME", ""),
        "prepared_by": submission_data.get("PREPARED_BY", ""),
        "overall_status": overall_status,
        "download_available": download_available,
        "has_pdf": has_pdf,
        "auto_download": True
    }

    return render_template('status.html', **context)

@status_bp.route('/download/<submission_id>')
@login_required
def download_report(submission_id):
    """Download the generated report"""
    try:
        from models import Report, SATReport
        import json
        
        # Verify report exists
        report = Report.query.filter_by(id=submission_id).first()
        if not report:
            flash('Report not found.', 'error')
            return redirect(url_for('dashboard.home'))

        sat_report = SATReport.query.filter_by(report_id=report.id).first()
        if not sat_report:
            flash('Report data not found.', 'error')
            return redirect(url_for('dashboard.home'))
        
        # Try to serve the originally generated file first
        permanent_path = os.path.join(current_app.config['OUTPUT_DIR'], f'SAT_Report_{submission_id}_Final.docx')
        
        if os.path.exists(permanent_path) and os.path.getsize(permanent_path) > 1000:
            current_app.logger.info(f"Serving existing report file for {submission_id}")
            
            # Build download name
            try:
                stored_data = json.loads(sat_report.data_json) if sat_report.data_json else {}
                context_data = stored_data.get("context", stored_data)
                project_ref = context_data.get('PROJECT_REFERENCE', '').strip()
                if not project_ref:
                    project_ref = submission_id[:8]
                safe_proj_ref = "".join(c if c.isalnum() or c in ['_', '-'] else "_" for c in project_ref)
                download_name = f"SAT_{safe_proj_ref}.docx"
            except:
                download_name = f"SAT_Report_{submission_id}.docx"
            
            with open(permanent_path, 'rb') as f:
                return Response(
                    f.read(),
                    mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    headers={                        'Content-Disposition': f'attachment; filename={download_name}'                    }
                )
        else:
            # File doesn't exist - inform user to regenerate from form
            flash('Document file not found. Please edit and re-generate this report from the form.', 'warning')
            return redirect(url_for('main.edit_sat', submission_id=submission_id))

    except Exception as e:
        current_app.logger.error(f"Error in download_report for {submission_id}: {e}", exc_info=True)
        flash('An unexpected error occurred while downloading the report.', 'error')
        return redirect(url_for('dashboard.home'))


@status_bp.route('/download-modern/<submission_id>')
@login_required
def download_report_modern(submission_id):
    if not submission_id or submission_id == 'None':
        flash('Invalid submission ID.', 'error')
        return redirect(url_for('dashboard.home'))

    from services.report_renderer import generate_modern_sat_report

    result = generate_modern_sat_report(submission_id)
    if 'error' in result:
        flash(result['error'], 'error')
        return redirect(url_for('status.view_status', submission_id=submission_id))

    try:
        return send_file(
            result['path'],
            as_attachment=True,
            download_name=result['download_name'],
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    except Exception as exc:  # noqa: BLE001 - provide user-facing feedback
        current_app.logger.error(f'Error sending modern report for {submission_id}: {exc}', exc_info=True)
        flash('Error downloading report.', 'error')
        return redirect(url_for('status.view_status', submission_id=submission_id))


@status_bp.route('/list')
@login_required
def list_submissions():
    """List all submissions for admin view"""
    from models import Report, SATReport

    try:
        # SQLAlchemy attaches columns dynamically; getattr avoids static analysis warnings.
        created_at_column = getattr(Report, 'created_at', None)
        query = Report.query
        if created_at_column is not None:
            query = query.order_by(created_at_column.desc())
        else:
            fallback_id = getattr(Report, 'id')
            query = query.order_by(fallback_id.desc())
        reports = query.all()
        submission_list = []

        for report in reports:
            sat_report = SATReport.query.filter_by(report_id=report.id).first()
            if not sat_report:
                continue

            try:
                stored_data = json.loads(sat_report.data_json)
            except json.JSONDecodeError:
                stored_data = {}

            # Determine overall status
            if report.approvals_json:
                try:
                    approvals = json.loads(report.approvals_json)
                    statuses = [a.get("status", "pending") for a in approvals]
                    if "rejected" in statuses:
                        overall_status = "rejected"
                    elif all(status == "approved" for status in statuses):
                        overall_status = "approved"
                    elif any(status == "approved" for status in statuses):
                        overall_status = "partially_approved"
                    else:
                        overall_status = "pending"
                except:
                    overall_status = "pending"
            else:
                overall_status = "draft"

            submission_list.append({
                "id": report.id,
                "document_title": stored_data.get("context", {}).get("DOCUMENT_TITLE", "SAT Report"),
                "client_name": stored_data.get("context", {}).get("CLIENT_NAME", ""),
                "created_at": report.created_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(report.created_at, dt.datetime) else report.created_at,
                "updated_at": report.updated_at.strftime('%Y-%m-%d %H:%M:%S') if isinstance(report.updated_at, dt.datetime) else report.updated_at,
                "status": overall_status,
                "user_email": report.user_email
            })

        return render_template('submissions_list.html', submissions=submission_list)

    except Exception as e:
        current_app.logger.error(f"Error fetching submissions list: {e}")
        flash('Error loading submissions.', 'error')
        return render_template('submissions_list.html', submissions=[])


