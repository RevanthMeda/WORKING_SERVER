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
        # Validate submission ID
        if not submission_id or submission_id == 'None':
            current_app.logger.error(f"Invalid submission ID: {submission_id}")
            flash('Invalid submission ID.', 'error')
            return redirect(url_for('dashboard.home'))

        # Get data from database
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
        current_app.logger.info(f"Generating fresh report for submission {submission_id} programmatically")

        # Define paths
        permanent_path = os.path.join(current_app.config['OUTPUT_DIR'], f'SAT_Report_{submission_id}_Final.docx')

        # Remove existing file if it exists
        if os.path.exists(permanent_path):
            try:
                os.remove(permanent_path)
                current_app.logger.info(f"Removed existing file to force fresh generation: {permanent_path}")
            except Exception as e:
                current_app.logger.warning(f"Could not remove existing file: {e}")

        # --- Prepare context for the new report_builder ---
        context = {
            'document_title': context_data.get('document_title', 'SAT Report'),
            'project_reference': context_data.get('project_reference', ''),
            'document_reference': context_data.get('document_reference', submission_id),
            'date': context_data.get('date', ''),
            'client_name': context_data.get('client_name', ''),
            'revision': context_data.get('revision', '1.0'),
            'revisions': [
                {
                    'revision_no': context_data.get('revision', '1.0'),
                    'date': context_data.get('revision_date', ''),
                    'author': context_data.get('prepared_by', ''),
                    'description': context_data.get('revision_details', '')
                }
            ],
            'approvers': [
                {'role': 'Prepared By', 'name': context_data.get('prepared_by', '')},
                {'role': 'Reviewed By (Tech Lead)', 'name': context_data.get('reviewed_by_tech_lead', '')},
                {'role': 'Reviewed By (PM)', 'name': context_data.get('reviewed_by_pm', '')},
                {'role': 'Approved By (Client)', 'name': context_data.get('approved_by_client', '')},
            ],
            'purpose': context_data.get('purpose', ''),
            'scope': context_data.get('scope', ''),
            'tables': [
                {
                    'title': 'Related Documents',
                    'headers': ['Document Reference', 'Document Title'],
                    'keys': ['doc_ref', 'doc_title'],
                    'data': context_data.get('RELATED_DOCUMENTS', [])
                },
                {
                    'title': 'SAT Protocol Pre-Execution Approval',
                    'headers': ['Print Name', 'Signature', 'Date', 'Initial', 'Company'],
                    'keys': ['pre_approval_print_name', 'pre_approval_signature', 'pre_approval_date', 'pre_approval_initial', 'pre_approval_company'],
                    'data': context_data.get('PRE_EXECUTION_APPROVAL', [])
                },
                {
                    'title': 'SAT Protocol Post Execution Approval',
                    'headers': ['Print Name', 'Signature', 'Date', 'Initial', 'Company'],
                    'keys': ['post_approval_print_name', 'post_approval_signature', 'post_approval_date', 'post_approval_initial', 'post_approval_company'],
                    'data': context_data.get('POST_EXECUTION_APPROVAL', [])
                },
                {
                    'title': 'Pre-Test Requirements',
                    'headers': ['Item', 'Test', 'Method/Test', 'Acceptance', 'Result', 'Punch', 'Verified', 'Comment'],
                    'keys': ['pretest_item', 'pretest_test', 'pretest_method', 'pretest_acceptance', 'pretest_result', 'pretest_punch', 'pretest_verified_by', 'pretest_comment'],
                    'data': context_data.get('PRE_TEST_REQUIREMENTS', [])
                },
                {
                    'title': 'Key Components',
                    'headers': ['S. No.', 'Model', 'Description', 'Remarks'],
                    'keys': ['component_sno', 'component_model', 'component_description', 'component_remarks'],
                    'data': context_data.get('KEY_COMPONENTS', [])
                },
                {
                    'title': 'IP Address Records',
                    'headers': ['Device Name', 'IP Address', 'Comment'],
                    'keys': ['ip_device', 'ip_address', 'ip_comment'],
                    'data': context_data.get('IP_RECORDS', [])
                },
                {
                    'title': 'Digital Signals',
                    'headers': ['S.No', 'Rack', 'Pos', 'Signal TAG', 'Description', 'Result', 'Punch', 'Verified', 'Comment'],
                    'keys': ['digital_s_no', 'digital_rack', 'digital_pos', 'digital_signal_tag', 'digital_description', 'digital_result', 'digital_punch', 'digital_verified', 'digital_comment'],
                    'data': context_data.get('DIGITAL_SIGNALS', [])
                },
                {
                    'title': 'Analogue Input Signals',
                    'headers': ['S.No', 'Rack No', 'Module Position', 'Signal TAG', 'Description', 'Result', 'Punch Item', 'Verified By', 'Comment'],
                    'keys': ['analogue_input_s_no', 'analogue_input_rack_no', 'analogue_input_module_position', 'analogue_input_signal_tag', 'analogue_input_description', 'analogue_input_result', 'analogue_input_punch_item', 'analogue_input_verified_by', 'analogue_input_comment'],
                    'data': context_data.get('ANALOGUE_INPUT_SIGNALS', [])
                },
                {
                    'title': 'Analogue Output Signals',
                    'headers': ['S.No', 'Rack No', 'Module Position', 'Signal TAG', 'Description', 'Result', 'Punch Item', 'Verified By', 'Comment'],
                    'keys': ['analogue_output_s_no', 'analogue_output_rack_no', 'analogue_output_module_position', 'analogue_output_signal_tag', 'analogue_output_description', 'analogue_output_result', 'analogue_output_punch_item', 'analogue_output_verified_by', 'analogue_output_comment'],
                    'data': context_data.get('ANALOGUE_OUTPUT_SIGNALS', [])
                },
                {
                    'title': 'Digital Output Signals',
                    'headers': ['S.No', 'Rack No', 'Module Position', 'Signal TAG', 'Description', 'Result', 'Punch Item', 'Verified By', 'Comment'],
                    'keys': ['digital_output_s_no', 'digital_output_rack_no', 'digital_output_module_position', 'digital_output_signal_tag', 'digital_output_description', 'digital_output_result', 'digital_output_punch_item', 'digital_output_verified_by', 'digital_output_comment'],
                    'data': context_data.get('DIGITAL_OUTPUT_SIGNALS', [])
                },
                {
                    'title': 'Modbus Digital Signals',
                    'headers': ['Address', 'Description', 'Remarks', 'Result', 'Punch Item', 'Verified By', 'Comment'],
                    'keys': ['modbus_digital_address', 'modbus_digital_description', 'modbus_digital_remarks', 'modbus_digital_result', 'modbus_digital_punch_item', 'modbus_digital_verified_by', 'modbus_digital_comment'],
                    'data': context_data.get('MODBUS_DIGITAL_SIGNALS', [])
                },
                {
                    'title': 'Modbus Analogue Signals',
                    'headers': ['Address', 'Description', 'Range', 'Result', 'Punch Item', 'Verified By', 'Comment'],
                    'keys': ['modbus_analogue_address', 'modbus_analogue_description', 'modbus_analogue_range', 'modbus_analogue_result', 'modbus_analogue_punch_item', 'modbus_analogue_verified_by', 'modbus_analogue_comment'],
                    'data': context_data.get('MODBUS_ANALOGUE_SIGNALS', [])
                },
                {
                    'title': 'Process Tests',
                    'headers': ['Item', 'Action', 'Expected Result', 'Pass/Fail', 'Comments'],
                    'keys': ['Process_Item', 'Process_Action', 'Process_Expected / Required Result', 'Process_Pass/Fail', 'Process_Comments'],
                    'data': context_data.get('PROCESS_TEST', [])
                },
                {
                    'title': 'SCADA Verification',
                    'headers': ['Task', 'Expected Result', 'Pass/Fail', 'Comments'],
                    'keys': ['SCADA_Task', 'SCADA_Expected_Result', 'SCADA_Pass/Fail', 'SCADA_Comments'],
                    'data': context_data.get('SCADA_VERIFICATION', [])
                },
                {
                    'title': 'Trends Testing',
                    'headers': ['Trend', 'Expected Behavior', 'Pass/Fail', 'Comments'],
                    'keys': ['Trend', 'Expected Behavior', 'Pass/Fail Trend', 'Comments Trend'],
                    'data': context_data.get('TRENDS_TESTING', [])
                },
            ]
        }

        from services.report_builder import build_sat_report
        
        # Generate the report
        success = build_sat_report(context, permanent_path)

        if not success:
            flash('Error generating report.', 'error')
            return redirect(url_for('status.view_status', submission_id=submission_id))

        # Create download name
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
