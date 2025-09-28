from flask import Blueprint, render_template, redirect, url_for, flash, current_app, send_file
import os
import json
from flask_login import current_user, login_required
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
        # ... (database retrieval code remains the same)

        # Generate fresh report using HTML and Pandoc
        current_app.logger.info(f"Generating fresh report for submission {submission_id} using HTML and Pandoc")

        # Define paths
        html_temp_path = os.path.join(current_app.config['OUTPUT_DIR'], f'temp_{submission_id}.html')
        permanent_path = os.path.join(current_app.config['OUTPUT_DIR'], f'SAT_Report_{submission_id}_Final.docx')

        # Remove existing files if they exist
        if os.path.exists(permanent_path):
            os.remove(permanent_path)
        if os.path.exists(html_temp_path):
            os.remove(html_temp_path)

        from models import Report, SATReport
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

        context_data = stored_data.get("context", {})
        if not context_data:
            context_data = stored_data

        # --- Prepare context for the html_generator ---
        context = {
            'document_title': context_data.get('document_title', 'SAT Report'),
            'project_reference': context_data.get('project_reference', ''),
            'document_reference': context_data.get('document_reference', submission_id),
            'date': context_data.get('date', ''),
            'client_name': context_data.get('client_name', ''),
            'revision': context_data.get('revision', '1.0'),
        }

        from services.html_generator import generate_report_html
        
        # Generate the HTML file
        success = generate_report_html(context, html_temp_path)

        if not success:
            flash('Error generating HTML for the report.', 'error')
            return redirect(url_for('status.view_status', submission_id=submission_id))

        # --- Convert HTML to DOCX using Pandoc ---
        try:
            pypandoc.convert_file(html_temp_path, 'docx', outputfile=permanent_path)
        except (OSError, RuntimeError) as e:
            current_app.logger.error(f"Pandoc conversion failed: {e}", exc_info=True)
            flash('Error converting report to DOCX. Please ensure Pandoc is installed and accessible.', 'error')
            return redirect(url_for('status.view_status', submission_id=submission_id))

        # --- Clean up temporary HTML file ---
        if os.path.exists(html_temp_path):
            os.remove(html_temp_path)

        # --- Create download name ---
        project_number = context_data.get("project_reference", "").strip()
        if not project_number:
            project_number = submission_id[:8]
            
        safe_proj_num = "".join(c if c.isalnum() or c in ['_', '-'] else "_" for c in project_number)
        download_name = f"SAT_{safe_proj_num}.docx"

        # Serve the file
        if not os.path.exists(permanent_path) or os.path.getsize(permanent_path) == 0:
            flash('Error: Generated document is empty or corrupted.', 'error')
            return redirect(url_for('status.view_status', submission_id=submission_id))

        return send_file(permanent_path, as_attachment=True, download_name=download_name)

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
        reports = Report.query.order_by(Report.created_at.desc()).all()
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