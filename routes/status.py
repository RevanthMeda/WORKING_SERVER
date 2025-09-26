from flask import Blueprint, render_template, redirect, url_for, flash, current_app, send_file
import os
import json
import tempfile
import shutil
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
        # Validate submission ID
        if not submission_id or submission_id == 'None':
            current_app.logger.error(f"Invalid submission ID: {submission_id}")
            flash('Invalid submission ID.', 'error')
            return redirect(url_for('dashboard.home'))

        # FORCE REGENERATION - Skip existing file check to create fresh clean document
        permanent_path = os.path.join(current_app.config['OUTPUT_DIR'], f'SAT_Report_{submission_id}_Final.docx')
        
        # Remove existing file if it exists to force fresh generation
        if os.path.exists(permanent_path):
            try:
                os.remove(permanent_path)
                current_app.logger.info(f"Removed existing file to force fresh generation: {permanent_path}")
            except Exception as e:
                current_app.logger.warning(f"Could not remove existing file: {e}")
        
        # If file doesn't exist, try to get data from database and generate
        try:
            from models import Report, SATReport
            report = Report.query.filter_by(id=submission_id).first()
            if not report:
                current_app.logger.error(f"Report not found in database: {submission_id}")
                flash('Report not found in database.', 'error')
                return redirect(url_for('dashboard.home'))

            sat_report = SATReport.query.filter_by(report_id=submission_id).first()
            if not sat_report:
                current_app.logger.error(f"SAT report data not found: {submission_id}")
                flash('Report data not found.', 'error')
                return redirect(url_for('dashboard.home'))

            # Parse stored data
            try:
                stored_data = json.loads(sat_report.data_json) if sat_report.data_json else {}
            except json.JSONDecodeError as json_error:
                current_app.logger.error(f"JSON decode error: {json_error}")
                stored_data = {}

            context_data = stored_data.get("context", {})
            if not context_data:
                current_app.logger.error(f"No context data found for submission: {submission_id}")
                flash('No report data found.', 'error')
                return redirect(url_for('status.view_status', submission_id=submission_id))

        except Exception as db_error:
            current_app.logger.error(f"Database error: {db_error}")
            flash('Database connection error. Cannot generate report.', 'error')
            return redirect(url_for('dashboard.home'))

        # Generate fresh report
        current_app.logger.info(f"Generating fresh report for submission {submission_id}")

        try:
            # Check template file exists
            template_file = current_app.config.get('TEMPLATE_FILE', 'templates/SAT_Template.docx')
            if not os.path.exists(template_file):
                current_app.logger.error(f"Template file not found: {template_file}")
                flash('Report template file not found.', 'error')
                return redirect(url_for('status.view_status', submission_id=submission_id))

            # PRESERVE EXACT TEMPLATE FORMAT - Open original and replace content only
            from docx import Document
            import re
            
            doc = Document(template_file)
            current_app.logger.info(f"Opened original SAT_Template.docx to preserve exact formatting: {template_file}")
            
            raw_data = {
                    'DOCUMENT_TITLE': (
                        context_data.get('DOCUMENT_TITLE') or
                        context_data.get('document_title') or
                        context_data.get('Document_Title') or
                        context_data.get('documentTitle') or 'SAT Report'
                    ),
                    'PROJECT_REFERENCE': (
                        context_data.get('PROJECT_REFERENCE') or
                        context_data.get('project_reference') or
                        context_data.get('Project_Reference') or ''
                    ),
                    'DOCUMENT_REFERENCE': (
                        context_data.get('DOCUMENT_REFERENCE') or
                        context_data.get('document_reference') or
                        context_data.get('Document_Reference') or
                        context_data.get('doc_reference') or submission_id
                    ),
                    'DATE': (
                        context_data.get('DATE') or
                        context_data.get('date') or
                        context_data.get('Date') or ''
                    ),
                    'CLIENT_NAME': (
                        context_data.get('CLIENT_NAME') or
                        context_data.get('client_name') or
                        context_data.get('Client_Name') or ''
                    ),
                    'REVISION': (
                        context_data.get('REVISION') or
                        context_data.get('revision') or
                        context_data.get('Revision') or
                        context_data.get('rev') or '1.0'
                    ),
                    'PREPARED_BY': context_data.get('PREPARED_BY', context_data.get('prepared_by', '')),
                    'PREPARER_DATE': context_data.get('PREPARER_DATE', context_data.get('preparer_date', '')),
                    'REVIEWED_BY_TECH_LEAD': context_data.get('REVIEWED_BY_TECH_LEAD', context_data.get('reviewed_by_tech_lead', '')),
                    'TECH_LEAD_DATE': context_data.get('TECH_LEAD_DATE', context_data.get('tech_lead_date', '')),
                    'REVIEWED_BY_PM': context_data.get('REVIEWED_BY_PM', context_data.get('reviewed_by_pm', '')),
                    'PM_DATE': context_data.get('PM_DATE', context_data.get('pm_date', '')),
                    'APPROVED_BY_CLIENT': context_data.get('APPROVED_BY_CLIENT', context_data.get('approved_by_client', '')),
                    'PURPOSE': context_data.get('PURPOSE', context_data.get('purpose', '')),
                    'SCOPE': context_data.get('SCOPE', context_data.get('scope', '')),
                    'REVISION_DETAILS': context_data.get('REVISION_DETAILS', context_data.get('revision_details', '')),
                    'REVISION_DATE': context_data.get('REVISION_DATE', context_data.get('revision_date', '')),
                    'SIG_PREPARED': '',
                    'SIG_REVIEW_TECH': '',
                    'SIG_REVIEW_PM': '',
                    'SIG_APPROVAL_CLIENT': ''
            }

            replacement_data = {
                key: value.replace('{', '').replace('}', '') if isinstance(value, str) else value
                for key, value in raw_data.items()
            }
            
            current_app.logger.info(f"Final DOCUMENT_TITLE value: '{replacement_data['DOCUMENT_TITLE']}'")
            current_app.logger.info(f"Final DOCUMENT_REFERENCE value: '{replacement_data['DOCUMENT_REFERENCE']}'")
            current_app.logger.info(f"Final REVISION value: '{replacement_data['REVISION']}'")
            current_app.logger.info(f"Final PROJECT_REFERENCE value: '{replacement_data['PROJECT_REFERENCE']}'")
            
            def clean_text(text):
                if not text.strip():
                    return text
                
                original_text = text
                
                def replace_tag(match):
                    tag = match.group(1).strip()
                    value = replacement_data.get(tag)
                    if value is not None:
                        current_app.logger.info(f"REPLACED '{{{{ {tag} }}}}' with '{value}'")
                        return str(value)
                    current_app.logger.warning(f"No value found for tag: {tag}")
                    return match.group(0)

                text = re.sub(r'{{\s*([^}]+)\s*}}', replace_tag, text)
                
                if '{{' in original_text and '{{' not in text:
                    current_app.logger.info(f"SUCCESSFULLY CLEANED: '{original_text[:50]}...' -> '{text[:50]}...'")
                
                return text

            def replace_in_paragraph(paragraph):
                full_text = ''.join(run.text for run in paragraph.runs)
                if '{{' not in full_text:
                    return

                new_text = clean_text(full_text)

                if new_text != full_text:
                    for run in paragraph.runs:
                        run.clear()
                    if new_text.strip():
                        paragraph.add_run(new_text)
                    current_app.logger.info(f"REPLACED in paragraph: '{full_text[:50]}...' -> '{new_text[:50]}...'")

            for paragraph in doc.paragraphs:
                replace_in_paragraph(paragraph)
            
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            replace_in_paragraph(paragraph)
            
            for section in doc.sections:
                for paragraph in section.header.paragraphs:
                    replace_in_paragraph(paragraph)
                for paragraph in section.footer.paragraphs:
                    replace_in_paragraph(paragraph)

            try:
                permanent_dir = current_app.config['OUTPUT_DIR']
                os.makedirs(permanent_dir, exist_ok=True)
                
                import io
                buffer = io.BytesIO()
                doc.save(buffer)
                buffer.seek(0)
                with open(permanent_path, 'wb') as f:
                    f.write(buffer.getvalue())
                
                current_app.logger.info(f"Document saved successfully: {permanent_path} ({os.path.getsize(permanent_path)} bytes)")
                
            except Exception as render_error:
                current_app.logger.error(f"Error rendering/saving document: {render_error}", exc_info=True)
                flash(f'Error generating report document: {str(render_error)}', 'error')
                return redirect(url_for('status.view_status', submission_id=submission_id))

            project_number = context_data.get("PROJECT_REFERENCE", "").strip()
            if not project_number:
                project_number = context_data.get("PROJECT_NUMBER", "").strip()
            if not project_number:
                project_number = submission_id[:8]
                
            safe_proj_num = "".join(c if c.isalnum() or c in ['_', '-'] else "_" for c in project_number)
            download_name = f"SAT_{safe_proj_num}.docx"

            if not os.path.exists(permanent_path) or os.path.getsize(permanent_path) == 0:
                flash('Error: Generated document is empty or corrupted.', 'error')
                return redirect(url_for('status.view_status', submission_id=submission_id))

            return send_file(permanent_path, as_attachment=True, download_name=download_name)

        except Exception as generation_error:
            current_app.logger.error(f"Error during report generation: {generation_error}", exc_info=True)
            flash('Error generating report for download.', 'error')
            return redirect(url_for('status.view_status', submission_id=submission_id))

    except Exception as e:
        current_app.logger.error(f"Error in download_report for {submission_id}: {e}", exc_info=True)
        flash('Error downloading report.', 'error')
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