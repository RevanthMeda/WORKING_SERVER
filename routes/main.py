
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from models import db, Report, SATReport, CullyStatistics
import json

main_bp = Blueprint('main', __name__)

@main_bp.route('/edit/<submission_id>')
@login_required
def edit_submission(submission_id):
    """Edit a submission with role-based permissions"""
    
    # Get the report
    report = Report.query.get(submission_id)
    if not report:
        flash('Report not found.', 'error')
        return redirect(url_for('dashboard.home'))
    
    # Check permissions
    can_edit = False
    if current_user.role == 'Admin':
        can_edit = True  # Admin can edit any report
    elif current_user.role == 'Engineer' and current_user.email == report.user_email:
        # Engineers can edit their own reports until approved by Automation Manager
        if report.approvals_json:
            try:
                approvals = json.loads(report.approvals_json)
                tm_approved = any(a.get("status") == "approved" and a.get("stage") == 1 for a in approvals)
                can_edit = not tm_approved
            except:
                can_edit = True  # If can't parse approvals, allow edit
        else:
            can_edit = True
    elif current_user.role == 'Automation Manager':
        # Automation Manager can edit reports until approved by PM
        if report.approvals_json:
            try:
                approvals = json.loads(report.approvals_json)
                pm_approved = any(a.get("status") == "approved" and a.get("stage") == 2 for a in approvals)
                can_edit = not pm_approved
            except:
                can_edit = True
        else:
            can_edit = True
    
    if not can_edit:
        flash('You do not have permission to edit this report.', 'error')
        return redirect(url_for('status.view_status', submission_id=submission_id))
    
    # If user can edit, redirect to the SAT wizard with the submission ID
    return redirect(url_for('reports.sat_wizard', submission_id=submission_id))

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, send_file, current_app
from flask_login import current_user
from auth import login_required
import json
import os
import uuid
import datetime as dt
from datetime import datetime

try:
    from models import db, Report, SATReport, test_db_connection
except ImportError as e:
    print(f"Warning: Could not import models: {e}")
    db = None
    Report = None
    SATReport = None
    test_db_connection = lambda: False

try:
    from utils import (load_submissions, save_submissions, send_edit_link,
                  setup_approval_workflow, process_table_rows, handle_image_removals,
                  allowed_file, save_uploaded_file, generate_sat_report as create_docx_from_template)
except ImportError as e:
    print(f"Warning: Could not import utils: {e}")
    generate_sat_report = None
    create_docx_from_template = None
    convert_to_pdf = None

# Helper function to get unread notification count (assuming it exists elsewhere)
def get_unread_count():
    """Placeholder for getting unread notification count"""
    # Replace with actual implementation if available
    return 0

def setup_approval_workflow_db(report, approver_emails):
    """Set up approval workflow for database-stored reports"""
    approvals = []
    valid_emails = [email for email in approver_emails if email]

    for i, email in enumerate(valid_emails, 1):
        approvals.append({
            "stage": i,
            "approver_email": email,
            "status": "pending",
            "approved_at": None,
            "signature": None
        })

    # Reports should NOT be locked when pending approval
    # They should only be locked when approved
    locked = False
    return approvals, locked

def send_approval_link(email, submission_id, stage):
    """Send approval link to approver"""
    try:
        from flask import url_for
        from utils import send_email

        approval_url = url_for('approval.approve_submission', submission_id=submission_id, stage=stage, _external=True)
        subject = f"SAT Report Approval Required - Stage {stage}"
        body = f"""
        You have been assigned to review and approve a SAT report.

        Please click the following link to review and approve:
        {approval_url}

        Submission ID: {submission_id}
        Stage: {stage}
        """

        return send_email(email, subject, body)
    except Exception as e:
        current_app.logger.error(f"Error sending approval link: {e}")
        return False

def create_approval_notification(approver_email, submission_id, stage, document_title):
    """Create approval notification"""
    try:
        from models import Notification, db

        notification = Notification(
            user_email=approver_email,
            title="New Approval Request",
            message=f"You have a new approval request for: {document_title}",
            type="approval",
            read=False
        )
        db.session.add(notification)
        db.session.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error creating approval notification: {e}")
        return False

def create_new_submission_notification(admin_emails, submission_id, document_title, submitter_email):
    """Create new submission notification for admins"""
    try:
        from models import Notification, db

        for email in admin_emails:
            notification = Notification(
                user_email=email,
                title="New Report Submission",
                message=f"New report submitted: {document_title} by {submitter_email}",
                type="submission",
                read=False
            )
            db.session.add(notification)

        db.session.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error creating submission notifications: {e}")
        return False

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    """Render the main form with empty data for a new submission"""
    # Redirect to SAT form if user is logged in and it's the main entry point
    return redirect(url_for('main.sat_form'))

@main_bp.route('/sat_form', methods=['GET', 'POST'])
@login_required
def sat_form():
    """Render the SAT form (index.html) for creating a new report"""
    from flask import session

    # Handle POST request from wizard
    if request.method == 'POST':
        # Get the form data from the wizard
        wizard_data = {
            'document_title': request.form.get('document_title', ''),
            'project_reference': request.form.get('project_reference', ''),
            'client_name': request.form.get('client_name', ''),
            'date': request.form.get('date', ''),
            'prepared_by': request.form.get('prepared_by', ''),
            'revision': request.form.get('revision', ''),
            'purpose': request.form.get('purpose', ''),
            'scope': request.form.get('scope', ''),
            'approver_1_email': request.form.get('approver_1_email', ''),
            'approver_2_email': request.form.get('approver_2_email', ''),
            'approver_3_email': request.form.get('approver_3_email', ''),
        }
        # Store in session for rendering
        session['wizard_data'] = wizard_data

    # Check if we have wizard data in the session
    wizard_data = session.pop('wizard_data', {})

    # Pre-populate submission_data with wizard data if available
    submission_data = {
        'USER_EMAIL': current_user.email if current_user.is_authenticated else '',
        'PREPARED_BY': current_user.full_name if current_user.is_authenticated else '',
    }
    if wizard_data:
        submission_data.update({
            'DOCUMENT_TITLE': wizard_data.get('document_title', ''),
            'PROJECT_REFERENCE': wizard_data.get('project_reference', ''),
            'CLIENT_NAME': wizard_data.get('client_name', ''),
            'DATE': wizard_data.get('date', ''),
            'PREPARED_BY': current_user.full_name if current_user.is_authenticated else wizard_data.get('prepared_by', ''),
            'REVISION': wizard_data.get('revision', ''),
            'PURPOSE': wizard_data.get('purpose', ''),
            'SCOPE': wizard_data.get('scope', ''),
            'approver_1_email': wizard_data.get('approver_1_email', ''),
            'approver_2_email': wizard_data.get('approver_2_email', ''),
            'approver_3_email': wizard_data.get('approver_3_email', ''),
            'USER_EMAIL': current_user.email if current_user.is_authenticated else wizard_data.get('user_email', ''),
        })

    # Always render the SAT.html template (the full SAT form)
    return render_template(
        'SAT.html',
        submission_data=submission_data,
        user_role=current_user.role if hasattr(current_user, 'role') else 'user'
    )

@main_bp.route('/edit/<submission_id>')
@login_required  
def edit_submission(submission_id):
    """Edit an existing submission (if not yet locked)"""
    try:
        from models import Report, SATReport

        # Get report from database
        report = Report.query.get(submission_id)
        if not report:
            flash("Submission not found", "error")
            return redirect(url_for('main.index'))

        # Check if the current user is authorized to edit based on approval status
        if report.locked:
            flash("This submission is locked and cannot be edited", "warning")
            return redirect(url_for('status.view_status', submission_id=submission_id))

        # Check if the current user is authorized to edit
        if current_user.role != 'admin' and report.user_email != current_user.email:
            flash("You are not authorized to edit this submission.", "error")
            return redirect(url_for('main.index'))

        # Get SAT report data
        sat_report = SATReport.query.filter_by(report_id=submission_id).first()
        if not sat_report:
            flash("SAT report data not found", "error")
            return redirect(url_for('main.index'))

        # Parse the stored data
        stored_data = json.loads(sat_report.data_json)
        context_data = stored_data.get("context", {})

        # Get unread notifications count
        unread_count = get_unread_count()

        return render_template('SAT.html',
                              submission_data=context_data,
                              submission_id=submission_id,
                              unread_count=unread_count,
                              user_role=current_user.role if hasattr(current_user, 'role') else 'user',
                              edit_mode=True)
    except Exception as e:
        current_app.logger.error(f"Error in edit_submission: {e}", exc_info=True)
        current_app.logger.error(f"Template rendering error: {str(e)}")
        flash("An error occurred while loading the submission", "error")
        return redirect(url_for('dashboard.my_reports'))

@main_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    """Generate a SAT report from form data"""
    try:
        # Log request details for debugging
        current_app.logger.info(f"Generate request from: {request.remote_addr}")
        current_app.logger.info(f"Request headers: {request.headers}")
        current_app.logger.info(f"Request form data keys: {list(request.form.keys())}")

        # Import database models
        from models import db, Report, SATReport

        # Retrieve submission id and current report
        submission_id = request.form.get("submission_id", "")

        # Create a new submission ID if needed
        if not submission_id:
            submission_id = str(uuid.uuid4())

        # Get or create report record
        report = Report.query.get(submission_id)
        is_new_report = False
        if not report:
            is_new_report = True
            report = Report(
                id=submission_id,
                type='SAT',
                status='DRAFT',
                user_email=current_user.email if hasattr(current_user, 'email') else '',
                approvals_json='[]',
                version='R0'  # Always start with R0 for new reports
            )
            db.session.add(report)
        else:
            # This is an edit/resubmit - increment version
            if not is_new_report:
                current_version = report.version or 'R0'
                if current_version.startswith('R'):
                    try:
                        version_num = int(current_version[1:])
                        report.version = f'R{version_num + 1}'
                    except ValueError:
                        report.version = 'R1'
                else:
                    report.version = 'R1'
                current_app.logger.info(f"Version incremented to: {report.version}")

            # Reset approval workflow for resubmission
            report.status = 'DRAFT'
            report.locked = False
            report.approval_notification_sent = False

        # Get or create SAT report record
        sat_report = SATReport.query.filter_by(report_id=submission_id).first()
        if not sat_report:
            sat_report = SATReport(
                report_id=submission_id,
                data_json='{}',
                scada_image_urls='[]',
                trends_image_urls='[]',
                alarm_image_urls='[]'
            )
            db.session.add(sat_report)

        # Load existing data for processing
        existing_data = json.loads(sat_report.data_json) if sat_report.data_json != '{}' else {}
        sub = existing_data  # For compatibility with existing code

        # Grab the approver emails from the form
        approver_emails = [
            request.form.get("approver_1_email", "").strip(),
            request.form.get("approver_2_email", "").strip(),
            request.form.get("approver_3_email", "").strip(),
        ]

        # Initialize (or update) the approvals list and lock flag
        approvals, locked = setup_approval_workflow_db(report, approver_emails)
        report.locked = locked
        report.approvals_json = json.dumps(approvals)

        # Create the upload directory for this submission
        upload_dir = os.path.join(current_app.config['UPLOAD_ROOT'], submission_id)
        os.makedirs(upload_dir, exist_ok=True)

        # Initialize image URLs lists from database
        scada_urls = json.loads(sat_report.scada_image_urls) if sat_report.scada_image_urls else []
        trends_urls = json.loads(sat_report.trends_image_urls) if sat_report.trends_image_urls else []
        alarm_urls = json.loads(sat_report.alarm_image_urls) if sat_report.alarm_image_urls else []

        # Initialize DocxTemplate
        from docxtpl import DocxTemplate, InlineImage
        from docx.shared import Mm
        from werkzeug.utils import secure_filename
        import base64
        import time
        import shutil

        doc = DocxTemplate(current_app.config['TEMPLATE_FILE'])

        # Process signature data
        sig_data_url = request.form.get("sig_prepared_data", "")
        SIG_PREPARED = ""

        if sig_data_url:
            # Parse and save the signature data
            try:
                # strip "data:image/png;base64,"
                if "," in sig_data_url:
                    header, encoded = sig_data_url.split(",", 1)
                    data = base64.b64decode(encoded)

                    # Ensure unique filename
                    fn = f"{submission_id}_prepared_{int(time.time())}.png"
                    sig_folder = current_app.config['SIGNATURES_FOLDER']
                    os.makedirs(sig_folder, exist_ok=True)  # Ensure folder exists
                    out_path = os.path.join(sig_folder, fn)

                    # Write signature file
                    with open(out_path, "wb") as f:
                        f.write(data)

                    # Verify the file was created successfully
                    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                        # Store signature filename in two places for redundancy
                        sub.setdefault("context", {})["prepared_signature"] = fn
                        sub["prepared_signature"] = fn  # Store in root of submission as well

                        # Add timestamp for the preparer
                        current_timestamp = dt.datetime.now().isoformat()
                        sub.setdefault("context", {})["prepared_timestamp"] = current_timestamp

                        # Log success with full path info
                        current_app.logger.info(f"Stored preparer signature as {fn}")
                        current_app.logger.info(f"Absolute signature path: {os.path.abspath(out_path)}")
                        current_app.logger.info(f"File exists: {os.path.exists(out_path)}")

                        # Create InlineImage for immediate use
                        try:
                            SIG_PREPARED = InlineImage(doc, out_path, width=Mm(40))
                            current_app.logger.info("Successfully created InlineImage for signature")
                        except Exception as e:
                            current_app.logger.error(f"Error creating preparer signature image: {e}")
                    else:
                        current_app.logger.error(f"Signature file not created or empty: {out_path}")
                else:
                    current_app.logger.error("Invalid signature data format")
            except Exception as e:
                current_app.logger.error(f"Error processing signature data: {e}", exc_info=True)

        # Initialize approval signatures
        SIG_APPROVER_1 = ""
        SIG_APPROVER_2 = ""
        SIG_APPROVER_3 = ""

        # Improved image file handling
        def save_new(field, url_list, inline_list):
            """Save new uploaded files with better error handling and path resolution"""
            for f in request.files.getlist(field):
                if not f or not f.filename:
                    continue

                try:
                    # Create a secure filename and ensure uniqueness
                    fn = secure_filename(f.filename)
                    uniq_fn = f"{uuid.uuid4().hex}_{fn}"

                    # Ensure the upload directory exists
                    os.makedirs(upload_dir, exist_ok=True)

                    # Create absolute path for file storage
                    disk_fp = os.path.join(upload_dir, uniq_fn)

                    # Save the file
                    f.save(disk_fp)
                    current_app.logger.info(f"Saved uploaded file to: {disk_fp}")

                    # Create proper URL and add image object
                    try:
                        # Process image and create scaled inline version
                        from PIL import Image
                        with Image.open(disk_fp) as img:
                            w, h = img.size

                        # Calculate scale to fit max width
                        max_w_mm = 150
                        scale = min(1, max_w_mm / (w * 0.264583))

                        # 1) Add public URL for edit-mode preview
                        # Use posix-style paths for URLs (forward slashes)
                        rel_path = os.path.join("uploads", submission_id, uniq_fn).replace("\\", "/")
                        url = url_for("static", filename=rel_path)
                        url_list.append(url)
                        current_app.logger.info(f"Added image URL: {url}")

                        # 2) Build InlineImage for DOCX
                        inline_list.append(
                            InlineImage(doc, disk_fp,
                                width=Mm(w * 0.264583 * scale),
                                height=Mm(h * 0.264583 * scale)
                            )
                        )
                        current_app.logger.info(f"Created InlineImage for: {uniq_fn}")
                    except Exception as e:
                        current_app.logger.error(f"Error processing image {fn}: {e}", exc_info=True)
                        # Add default size if image processing fails
                        rel_path = os.path.join("uploads", submission_id, uniq_fn).replace("\\", "/")
                        url = url_for("static", filename=rel_path)
                        url_list.append(url)
                        inline_list.append(
                            InlineImage(doc, disk_fp, width=Mm(100), height=Mm(80))
                        )
                        current_app.logger.info(f"Created fallback InlineImage for: {uniq_fn}")
                except Exception as e:
                    current_app.logger.error(f"Failed to save file {f.filename}: {e}", exc_info=True)

        # Remove images flagged for deletion
        handle_image_removals(request.form, "removed_scada_images", scada_urls)
        handle_image_removals(request.form, "removed_trends_images", trends_urls)
        handle_image_removals(request.form, "removed_alarm_images", alarm_urls)

        # Create image objects for template
        scada_image_objects = []
        trends_image_objects = []
        alarm_image_objects = []

        # Process new image uploads
        save_new("SCADA_IMAGES", scada_urls, scada_image_objects)
        save_new("TRENDS_IMAGES", trends_urls, trends_image_objects)
        save_new("ALARM_IMAGES", alarm_urls, alarm_image_objects)

        # Process related documents
        related_documents = process_table_rows(
            request.form,
            {
                'doc_ref[]': 'Document_Reference',
                'doc_title[]': 'Document_Title'
            }
        )

        # Skip Pre and Post Approvals processing since they're not used
        PRE_APPROVALS = []
        POST_APPROVALS = []

        # Remove signature image processing since we're not using them
        SIG_PREPARED_BY = ""
        SIG_REVIEW_TECH = ""
        SIG_REVIEW_PM = ""
        SIG_APPROVAL_CLIENT = ""

        # Process Pre-Test Requirements
        PRE_TEST_REQUIREMENTS = process_table_rows(
            request.form,
            {
                'pretest_item[]': 'Item',
                'pretest_test[]': 'Test',
                'pretest_method[]': 'Method_Test_Steps',
                'pretest_acceptance[]': 'Acceptance_Criteria',
                'pretest_result[]': 'Result',
                'pretest_punch[]': 'Punch_Item',
                'pretest_verified_by[]': 'Verified_by',
                'pretest_comment[]': 'Comment'
            }
        )

        # Process Key Components
        KEY_COMPONENTS = process_table_rows(
            request.form,
            {
                'keycomp_s_no[]': 'S.no',
                'keycomp_model[]': 'Model',
                'keycomp_description[]': 'Description',
                'keycomp_remarks[]': 'Remarks'
            }
        )

        # Process IP Records
        IP_RECORDS = process_table_rows(
            request.form,
            {
                'ip_device[]': 'Device_Name',
                'ip_address[]': 'IP_Address',
                'ip_comment[]': 'Comment'
            }
        )

        # Process Digital Signals
        SIGNAL_LISTS = process_table_rows(
            request.form,
            {
                'S. No.[]': 'S. No.',
                'Rack No.[]': 'Rack No.',
                'Module Position[]': 'Module Position',
                'Signal TAG[]': 'Signal TAG',
                'Signal Description[]': 'Signal Description',
                'Result[]': 'Result',
                'Punch Item[]': 'Punch Item',
                'Verified By[]': 'Verified By',
                'Comment[]': 'Comment'
            }
        )

        # Process Analogue Signals
        ANALOGUE_LISTS = process_table_rows(
            request.form,
            {
                'S. No. Analogue[]': 'S. No.',
                'Rack No. Analogue[]': 'Rack No.',
                'Module Position Analogue[]': 'Module Position',
                'Signal TAG Analogue[]': 'Signal TAG',
                'Signal Description Analogue[]': 'Signal Description',
                'Result Analogue[]': 'Result',
                'Punch Item Analogue[]': 'Punch Item',
                'Verified By Analogue[]': 'Verified By',
                'Comment Analogue[]': 'Comment'
            }
        )

        # Process Modbus Digital Signals
        MODBUS_DIGITAL_LISTS = process_table_rows(
            request.form,
            {
                'Address[]': 'Address',
                'Description[]': 'Description',
                'Remarks[]': 'Remarks',
                'Digital_Result[]': 'Result',
                'Digital_Punch Item[]': 'Punch Item',
                'Digital_Verified By[]': 'Verified By',
                'Digital_Comment[]': 'Comment'
            }
        )

        # Process Modbus Analogue Signals
        MODBUS_ANALOGUE_LISTS = process_table_rows(
            request.form,
            {
                'Address Analogue[]': ' Address',  # Note: space in name is intentional
                'Description Analogue[]': 'Description',
                'Range Analogue[]': 'Range',
                'Result Analogue[]': 'Result',
                'Punch Item Analogue[]': 'Punch Item',
                'Verified By Analogue[]': 'Verified By',
                'Comment Analogue[]': 'Comment'
            }
        )

        # Process Data Validation
        DATA_VALIDATION = process_table_rows(
            request.form,
            {
                'Validation_Tag[]': 'Tag',
                'Validation_Range[]': 'Range',
                'Validation_SCADA Value[]': 'SCADA Value',
                'Validation_HMI Value[]': 'HMI Value'
            }
        )

        # Process Process Test
        PROCESS_TEST = process_table_rows(
            request.form,
            {
                'Process_Item[]': 'Item',
                'Process_Action[]': 'Action',
                'Process_Expected / Required Result[]': 'Expected / Required Result',
                'Process_Pass/Fail[]': ' Pass/Fail ',  # Note: spaces in name are intentional
                'Process_Comments[]': ' Comments '     # Note: spaces in name are intentional
            }
        )

        # Process SCADA Verification
        SCADA_VERIFICATION = process_table_rows(
            request.form,
            {
                'SCADA_Task[]': 'Task',
                'SCADA_Expected_Result[]': 'Expected Result',
                'SCADA_Pass/Fail[]': 'Pass/Fail',
                'SCADA_Comments[]': 'Comments'
            }
        )

        # Process Trends Testing
        TRENDS_TESTING = process_table_rows(
            request.form,
            {
                'Trend[]': 'Trend',
                'Expected Behavior[]': 'Expected Behavior',
                'Pass/Fail Trend[]': 'Pass/Fail',
                'Comments Trend[]': 'Comments'
            }
        )

        # Process Alarm Signals
        ALARM_LIST = process_table_rows(
            request.form,
            {
                'Alarm_Type[]': 'Alarm Type',
                'Expected / Required Result[]': ' Expected / Required Result',
                'Pass/Fail []': ' Pass/Fail ',  # Note: spaces in name are intentional
                'Comments []': ' Comments '     # Note: spaces in name are intentional
            }
        )

        # Build final context for the DOCX
        context = {
            "DOCUMENT_TITLE": request.form.get('document_title', ''),
            "PROJECT_REFERENCE": request.form.get('project_reference', ''),
            "DOCUMENT_REFERENCE": request.form.get('document_reference', ''),
            "DATE": request.form.get('date', ''),
            "CLIENT_NAME": request.form.get('client_name', ''),
            "REVISION": request.form.get('revision', ''),
            "REVISION_DETAILS": request.form.get('revision_details', ''),
            "REVISION_DATE": request.form.get('revision_date', ''),
            "PREPARED_BY": request.form.get('prepared_by', ''),
            "SIG_PREPARED": SIG_PREPARED,
            "SIG_PREPARED_BY": SIG_PREPARED_BY,
            "REVIEWED_BY_TECH_LEAD": request.form.get('reviewed_by_tech_lead', ''),
            "SIG_REVIEW_TECH": SIG_REVIEW_TECH,
            "REVIEWED_BY_PM": request.form.get('reviewed_by_pm', ''),
            "SIG_REVIEW_PM": SIG_REVIEW_PM,
            "APPROVED_BY_CLIENT": request.form.get('approved_by_client', ''),
            "SIG_APPROVAL_CLIENT": SIG_APPROVAL_CLIENT,
            "PURPOSE": request.form.get("purpose", ""),
            "SCOPE": request.form.get("scope", ""),
            "PRE_TEST_REQUIREMENTS": PRE_TEST_REQUIREMENTS,
            "KEY_COMPONENTS": KEY_COMPONENTS,
            "IP_RECORDS": IP_RECORDS,
            "RELATED_DOCUMENTS": related_documents,
            "PRE_APPROVALS": PRE_APPROVALS,
            "POST_APPROVALS": POST_APPROVALS,
            "SIGNAL_LISTS": SIGNAL_LISTS,
            "ANALOGUE_LISTS": ANALOGUE_LISTS,
            "MODBUS_DIGITAL_LISTS": MODBUS_DIGITAL_LISTS,
            "MODBUS_ANALOGUE_LISTS": MODBUS_ANALOGUE_LISTS,
            "DATA_VALIDATION": DATA_VALIDATION,
            "PROCESS_TEST": PROCESS_TEST,
            "SCADA_VERIFICATION": SCADA_VERIFICATION,
            "TRENDS_TESTING": TRENDS_TESTING,
            "SCADA_IMAGES": scada_image_objects,
            "TRENDS_IMAGES": trends_image_objects,
            "ALARM_IMAGES": alarm_image_objects,
            "ALARM_LIST": ALARM_LIST,
            "SIG_APPROVER_1": SIG_APPROVER_1,
            "SIG_APPROVER_2": SIG_APPROVER_2,
            "SIG_APPROVER_3": SIG_APPROVER_3,
        }

        # For storage, remove the InlineImage objects recursively
        context_to_store = dict(context)
        def remove_inline_images(obj):
            """Recursively remove InlineImage objects from nested data structures"""
            if isinstance(obj, InlineImage):
                return None
            elif isinstance(obj, dict):
                return {k: remove_inline_images(v) for k, v in obj.items() if not isinstance(v, InlineImage)}
            elif isinstance(obj, list):
                return [remove_inline_images(item) for item in obj if not isinstance(item, InlineImage)]
            else:
                return obj

        # Apply the cleaning function to all context data
        for key in list(context_to_store.keys()):
            context_to_store[key] = remove_inline_images(context_to_store[key])

        # Store approver emails in context for later retrieval in edit form
        context_to_store["approver_1_email"] = approver_emails[0]
        context_to_store["approver_2_email"] = approver_emails[1]
        context_to_store["approver_3_email"] = approver_emails[2]

        # Update report metadata
        report.document_title = context_to_store.get('DOCUMENT_TITLE', '')
        report.document_reference = context_to_store.get('DOCUMENT_REFERENCE', '')
        report.project_reference = context_to_store.get('PROJECT_REFERENCE', '')
        report.client_name = context_to_store.get('CLIENT_NAME', '')
        report.revision = context_to_store.get('REVISION', '')
        report.prepared_by = context_to_store.get('PREPARED_BY', '')
        report.updated_at = dt.datetime.utcnow()
        
        # CRITICAL: Update status to PENDING when submitted for approval
        # Only change from DRAFT to PENDING if there are approvers
        if approvals and len(approvals) > 0:
            report.status = 'PENDING'
            current_app.logger.info(f"Report {submission_id} status changed to PENDING (submitted for approval)")
        else:
            # No approvers = stays as DRAFT
            if not report.status or report.status == '':
                report.status = 'DRAFT'
            current_app.logger.info(f"Report {submission_id} status remains {report.status} (no approvals)")

        # Prepare submission data for storage
        submission_data = {
            "context": context_to_store,
            "user_email": current_user.email if hasattr(current_user, 'email') else request.form.get("user_email", ""),
            "approvals": approvals,
            "locked": locked,
            "scada_image_urls": scada_urls,
            "trends_image_urls": trends_urls,
            "alarm_image_urls": alarm_urls,
            "created_at": existing_data.get("created_at", dt.datetime.now().isoformat()),
            "updated_at": dt.datetime.now().isoformat()
        }

        # Update SAT report data
        sat_report.data_json = json.dumps(submission_data)
        sat_report.date = context_to_store.get('DATE', '')
        sat_report.purpose = context_to_store.get('PURPOSE', '')
        sat_report.scope = context_to_store.get('SCOPE', '')
        sat_report.scada_image_urls = json.dumps(scada_urls)
        sat_report.trends_image_urls = json.dumps(trends_urls)
        sat_report.alarm_image_urls = json.dumps(alarm_urls)

        # Save to database
        db.session.commit()

        # Render the DOCX template
        doc.render(context)

        # Build a timestamped filename and save to the OS temp directory
        import tempfile
        timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"SAT_Report_{timestamp}.docx"
        temp_path = os.path.join(tempfile.gettempdir(), filename)

        doc.save(temp_path)
        current_app.logger.info(f"Document saved to temp path: {temp_path}")

        # Try to copy to permanent location
        try:
            permanent = os.path.abspath(current_app.config['OUTPUT_FILE'])
            shutil.copyfile(temp_path, permanent)
            current_app.logger.info(f"Also copied report to outputs: {permanent}")
        except Exception as e:
            current_app.logger.warning(f"Could not copy to outputs folder: {e}")

        # Notify first approver exactly once
        if not report.approval_notification_sent:
            first_stage = approvals[0] if approvals else None
            if first_stage:
                first_email = first_stage["approver_email"]
                # Corrected call to send_approval_link
                sent = send_approval_link(
                    first_email,
                    submission_id,
                    first_stage["stage"]
                )
                current_app.logger.info(f"Approval email to {first_email}: {sent}")

                # Create approval notification
                try:
                    document_title = context.get("DOCUMENT_TITLE", "SAT Report")
                    create_approval_notification(
                        approver_email=first_email,
                        submission_id=submission_id,
                        stage=first_stage["stage"],
                        document_title=document_title
                    )

                    # Also notify admins about new submission
                    from models import User
                    admin_emails = [u.email for u in User.query.filter_by(role='Admin').all()]
                    if admin_emails:
                        create_new_submission_notification(
                            admin_emails=admin_emails,
                            submission_id=submission_id,
                            document_title=document_title,
                            submitter_email=current_user.email
                        )
                except Exception as e:
                    current_app.logger.error(f"Error creating submission notifications: {e}")

                report.approval_notification_sent = True
                db.session.commit()

        # Send edit link email to user (with graceful failure)
        email_sent = False
        if current_app.config.get('ENABLE_EMAIL_NOTIFICATIONS', True):
            try:
                email_result = send_edit_link(report.user_email, submission_id)
                if email_result:
                    email_sent = True
                    current_app.logger.info(f"Email sent successfully to {report.user_email}")
                else:
                    current_app.logger.warning(f"Failed to send email to {report.user_email}")
            except Exception as e:
                current_app.logger.error(f"Email sending error: {e}")

        # Always show success message regardless of email status
        success_message = "Report generated successfully!"
        if email_sent:
            success_message += " An edit link has been sent to your email."
        else:
            success_message += " You can access your report using the status page."

        flash(success_message, "success")

        return jsonify({
            "success": True,
            "message": success_message,
            "submission_id": submission_id,
            "redirect_url": url_for('status.view_status', submission_id=submission_id),
            "download_url": url_for('status.download_report', submission_id=submission_id)
        })

    except Exception as e:
        current_app.logger.error(f"Error in generate: {e}", exc_info=True)
        flash(f"An error occurred while generating the report: {str(e)}", "error")
        return redirect(url_for('main.index'))

@main_bp.route('/save_progress', methods=['POST'])
@login_required
def save_progress():
    """Save form progress without generating report"""
    try:
        from models import db, Report, SATReport

        # Get submission ID or create new one
        submission_id = request.form.get("submission_id", "")
        if not submission_id:
            submission_id = str(uuid.uuid4())

        # Get or create report record
        report = Report.query.get(submission_id)
        if not report:
            report = Report(
                id=submission_id,
                type='SAT',
                status='DRAFT',  # Always start as DRAFT
                user_email=current_user.email if hasattr(current_user, 'email') else '',
                approvals_json='[]'
            )
            db.session.add(report)
        # IMPORTANT: Ensure status remains DRAFT for save progress (not submission)
        # Only preserve existing non-draft status if it's already PENDING/APPROVED
        if not report.status or report.status == '':
            report.status = 'DRAFT'
        current_app.logger.info(f"Save progress: Report {submission_id} status is {report.status}")

        # Get or create SAT report record
        sat_report = SATReport.query.filter_by(report_id=submission_id).first()
        if not sat_report:
            sat_report = SATReport(
                report_id=submission_id,
                data_json='{}',
                scada_image_urls='[]',
                trends_image_urls='[]',
                alarm_image_urls='[]'
            )
            db.session.add(sat_report)

        # Load existing data
        existing_data = json.loads(sat_report.data_json) if sat_report.data_json != '{}' else {}

        # Build context from current form data
        context = {
            "DOCUMENT_TITLE": request.form.get('document_title', ''),
            "PROJECT_REFERENCE": request.form.get('project_reference', ''),
            "DOCUMENT_REFERENCE": request.form.get('document_reference', ''),
            "DATE": request.form.get('date', ''),
            "CLIENT_NAME": request.form.get('client_name', ''),
            "REVISION": request.form.get('revision', ''),
            "REVISION_DETAILS": request.form.get('revision_details', ''),
            "REVISION_DATE": request.form.get('revision_date', ''),
            "PREPARED_BY": request.form.get('prepared_by', ''),
            "REVIEWED_BY_TECH_LEAD": request.form.get('reviewed_by_tech_lead', ''),
            "REVIEWED_BY_PM": request.form.get('reviewed_by_pm', ''),
            "APPROVED_BY_CLIENT": request.form.get('approved_by_client', ''),
            "PURPOSE": request.form.get("purpose", ""),
            "SCOPE": request.form.get("scope", ""),
            "approver_1_email": request.form.get("approver_1_email", ""),
            "approver_2_email": request.form.get("approver_2_email", ""),
            "approver_3_email": request.form.get("approver_3_email", ""),
        }

        # Update report metadata
        report.document_title = context.get('DOCUMENT_TITLE', '')
        report.document_reference = context.get('DOCUMENT_REFERENCE', '')
        report.project_reference = context.get('PROJECT_REFERENCE', '')
        report.client_name = context.get('CLIENT_NAME', '')
        report.revision = context.get('REVISION', '')
        report.prepared_by = context.get('PREPARED_BY', '')
        report.updated_at = dt.datetime.utcnow()

        # Prepare submission data for storage
        submission_data = {
            "context": context,
            "user_email": current_user.email if hasattr(current_user, 'email') else request.form.get("user_email", ""),
            "approvals": existing_data.get("approvals", []),
            "locked": existing_data.get("locked", False),
            "scada_image_urls": existing_data.get("scada_image_urls", []),
            "trends_image_urls": existing_data.get("trends_image_urls", []),
            "alarm_image_urls": existing_data.get("alarm_image_urls", []),
            "created_at": existing_data.get("created_at", dt.datetime.now().isoformat()),
            "updated_at": dt.datetime.now().isoformat()
        }

        # Update SAT report data
        sat_report.data_json = json.dumps(submission_data)
        sat_report.date = context.get('DATE', '')
        sat_report.purpose = context.get('PURPOSE', '')
        sat_report.scope = context.get('SCOPE', '')

        # Save to database
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Progress saved successfully',
            'submission_id': submission_id
        })

    except Exception as e:
        current_app.logger.error(f"Error saving progress: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Error saving progress: {str(e)}'
        }), 500

@main_bp.route('/generate_site_survey', methods=['POST'])
@login_required
def generate_site_survey():
    """Generate a Site Survey report from form data"""
    try:
        from models import db, Report, SiteSurveyReport
        import datetime as dt

        # Get submission ID
        submission_id = request.form.get("submission_id", "")
        if not submission_id:
            submission_id = str(uuid.uuid4())

        # Get or create report record
        report = Report.query.get(submission_id)
        if not report:
            report = Report(
                id=submission_id,
                type='SITE_SURVEY',
                status='DRAFT',
                user_email=current_user.email if hasattr(current_user, 'email') else '',
                approvals_json='[]',
                version='R0'
            )
            db.session.add(report)

        # Get or create Site Survey report record
        site_survey_report = SiteSurveyReport.query.filter_by(report_id=submission_id).first()
        if not site_survey_report:
            site_survey_report = SiteSurveyReport(
                report_id=submission_id,
                data_json='{}'
            )
            db.session.add(site_survey_report)

        # Build context from form data
        context = {
            "SITE_NAME": request.form.get('site_name', ''),
            "SITE_LOCATION": request.form.get('site_location', ''),
            "SITE_ACCESS_DETAILS": request.form.get('site_access_details', ''),
            "ON_SITE_PARKING": request.form.get('on_site_parking', ''),
            "AREA_ENGINEER": request.form.get('area_engineer', ''),
            "SITE_CARETAKER": request.form.get('site_caretaker', ''),
            "SURVEY_COMPLETED_BY": request.form.get('survey_completed_by', ''),
            "SIGNATURE_DATA": request.form.get('sig_prepared_data', '')
        }

        # Update report fields
        report.document_title = f"Site Survey - {context.get('SITE_NAME', submission_id)}"
        report.project_reference = f"SURVEY-{submission_id[:8]}"
        report.client_name = "Irish Water"
        report.revision = "R0"
        report.prepared_by = context.get('SURVEY_COMPLETED_BY', current_user.full_name if current_user.is_authenticated else '')
        report.updated_at = dt.datetime.utcnow()
        report.status = 'PENDING'  # Submit for approval

        # Prepare submission data for storage
        submission_data = {
            "context": context,
            "user_email": current_user.email if hasattr(current_user, 'email') else '',
            "created_at": dt.datetime.now().isoformat(),
            "updated_at": dt.datetime.now().isoformat(),
            "report_type": "SITE_SURVEY"
        }

        # Update Site Survey report data
        site_survey_report.data_json = json.dumps(submission_data)
        site_survey_report.site_name = context.get('SITE_NAME', '')
        site_survey_report.site_location = context.get('SITE_LOCATION', '')
        site_survey_report.survey_completed_by = context.get('SURVEY_COMPLETED_BY', '')

        # Save to database
        db.session.commit()

        flash("Site Survey submitted successfully!", "success")
        
        return jsonify({
            "success": True,
            "message": "Site Survey submitted successfully!",
            "submission_id": submission_id,
            "redirect_url": url_for('status.view_status', submission_id=submission_id)
        })

    except Exception as e:
        current_app.logger.error(f"Error in generate_site_survey: {e}", exc_info=True)
        flash(f"An error occurred while submitting the survey: {str(e)}", "error")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500

@main_bp.route('/generate_scada_migration', methods=['POST'])
@login_required
def generate_scada_migration():
    """Generate a SCADA Migration Site Survey report from form data"""
    try:
        from models import db, Report, SiteSurveyReport
        import datetime as dt

        # Get submission ID
        submission_id = request.form.get("submission_id", "")
        if not submission_id:
            submission_id = str(uuid.uuid4())

        # Get or create report record
        report = Report.query.get(submission_id)
        if not report:
            report = Report(
                id=submission_id,
                type='SCADA_MIGRATION',
                status='DRAFT',
                user_email=current_user.email if hasattr(current_user, 'email') else '',
                approvals_json='[]',
                version='R0'
            )
            db.session.add(report)

        # Get or create Site Survey report record
        site_survey_report = SiteSurveyReport.query.filter_by(report_id=submission_id).first()
        if not site_survey_report:
            site_survey_report = SiteSurveyReport(
                report_id=submission_id,
                data_json='{}'
            )
            db.session.add(site_survey_report)

        # Build context from form data
        context = {
            "SITE_NAME": request.form.get('site_name', ''),
            "SITE_LOCATION": request.form.get('site_location', ''),
            "SITE_ACCESS_DETAILS": request.form.get('site_access_details', ''),
            "ON_SITE_PARKING": request.form.get('on_site_parking', ''),
            "AREA_ENGINEER": request.form.get('area_engineer', ''),
            "SITE_CARETAKER": request.form.get('site_caretaker', ''),
            "SURVEY_COMPLETED_BY": request.form.get('survey_completed_by', ''),
            "CONTROL_APPROACH_DISCUSSED": request.form.get('control_approach_discussed', ''),
            "VISUAL_INSPECTION": request.form.get('visual_inspection', ''),
            "SITE_TYPE": request.form.get('site_type', ''),
            "ELECTRICAL_SUPPLY": request.form.get('electrical_supply', ''),
            "PLANT_PHOTOS_COMPLETED": request.form.get('plant_photos_completed', ''),
            "SITE_UNDERGOING_CONSTRUCTION": request.form.get('site_undergoing_construction', ''),
            "CONSTRUCTION_DESCRIPTION": request.form.get('construction_description', ''),
            "PLC_MANUFACTURER": request.form.get('plc_manufacturer', ''),
            "PLC_VERSION": request.form.get('plc_version', ''),
            "PLC_COMMENTS": request.form.get('plc_comments', ''),
            "HMI_MANUFACTURER": request.form.get('hmi_manufacturer', ''),
            "HMI_VERSION": request.form.get('hmi_version', ''),
            "HMI_COMMENTS": request.form.get('hmi_comments', ''),
            "ROUTER_MANUFACTURER": request.form.get('router_manufacturer', ''),
            "ROUTER_VERSION": request.form.get('router_version', ''),
            "ROUTER_COMMENTS": request.form.get('router_comments', ''),
            "PLC_IP": request.form.get('plc_ip', ''),
            "HMI_IP": request.form.get('hmi_ip', ''),
            "ROUTER_IP": request.form.get('router_ip', ''),
            "SIGNAL_STRENGTH": request.form.get('signal_strength', ''),
            "SIGNATURE_DATA": request.form.get('sig_prepared_data', '')
        }

        # Update report fields
        report.document_title = f"SCADA Migration Site Survey - {context.get('SITE_NAME', submission_id)}"
        report.project_reference = f"SCADA-{submission_id[:8]}"
        report.client_name = "Irish Water"
        report.revision = "R0"
        report.prepared_by = context.get('SURVEY_COMPLETED_BY', current_user.full_name if current_user.is_authenticated else '')
        report.updated_at = dt.datetime.utcnow()
        report.status = 'PENDING'  # Submit for approval

        # Prepare submission data for storage
        submission_data = {
            "context": context,
            "user_email": current_user.email if hasattr(current_user, 'email') else '',
            "created_at": dt.datetime.now().isoformat(),
            "updated_at": dt.datetime.now().isoformat(),
            "report_type": "SCADA_MIGRATION"
        }

        # Update Site Survey report data
        site_survey_report.data_json = json.dumps(submission_data)
        site_survey_report.site_name = context.get('SITE_NAME', '')
        site_survey_report.site_location = context.get('SITE_LOCATION', '')
        site_survey_report.survey_completed_by = context.get('SURVEY_COMPLETED_BY', '')

        # Save to database
        db.session.commit()

        flash("SCADA Migration Site Survey submitted successfully!", "success")
        
        return jsonify({
            "success": True,
            "message": "SCADA Migration Site Survey submitted successfully!",
            "submission_id": submission_id,
            "redirect_url": url_for('status.view_status', submission_id=submission_id)
        })

    except Exception as e:
        current_app.logger.error(f"Error in generate_scada_migration: {e}", exc_info=True)
        flash(f"An error occurred while submitting the survey: {str(e)}", "error")
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        }), 500

@main_bp.route('/auto_save_progress', methods=['POST'])
@login_required
def auto_save_progress():
    """Auto-save form progress with CSRF validation"""
    try:
        from models import db, Report, SATReport

        # Get submission ID or create new one
        submission_id = request.form.get("submission_id", "")
        if not submission_id:
            submission_id = str(uuid.uuid4())

        # Get form data
        form_data = request.form.to_dict()

        # Get or create report record
        report = Report.query.get(submission_id)
        if not report:
            report = Report(
                id=submission_id,
                type='SAT',
                status='DRAFT',  # Always start as DRAFT
                user_email=current_user.email if hasattr(current_user, 'email') else '',
                approvals_json='[]'
            )
            db.session.add(report)
        # IMPORTANT: Ensure status remains DRAFT for auto-save (not submission)
        # Only preserve existing non-draft status if it's already PENDING/APPROVED
        if not report.status or report.status == '':
            report.status = 'DRAFT'
        current_app.logger.debug(f"Auto-save: Report {submission_id} status is {report.status}")

        # Get or create SAT report record
        sat_report = SATReport.query.filter_by(report_id=submission_id).first()
        if not sat_report:
            sat_report = SATReport(
                report_id=submission_id,
                data_json='{}',
                scada_image_urls='[]',
                trends_image_urls='[]',
                alarm_image_urls='[]'
            )
            db.session.add(sat_report)

        # Load existing data
        existing_data = json.loads(sat_report.data_json) if sat_report.data_json != '{}' else {}

        # Build context from current form data
        context = {
            "DOCUMENT_TITLE": form_data.get('document_title', ''),
            "PROJECT_REFERENCE": form_data.get('project_reference', ''),
            "DOCUMENT_REFERENCE": form_data.get('document_reference', ''),
            "DATE": form_data.get('date', ''),
            "CLIENT_NAME": form_data.get('client_name', ''),
            "REVISION": form_data.get('revision', ''),
            "REVISION_DETAILS": form_data.get('revision_details', ''),
            "REVISION_DATE": form_data.get('revision_date', ''),
            "PREPARED_BY": form_data.get('prepared_by', ''),
            "REVIEWED_BY_TECH_LEAD": form_data.get('reviewed_by_tech_lead', ''),
            "REVIEWED_BY_PM": form_data.get('reviewed_by_pm', ''),
            "APPROVED_BY_CLIENT": form_data.get('approved_by_client', ''),
            "PURPOSE": form_data.get("purpose", ""),
            "SCOPE": form_data.get("scope", ""),
            "approver_1_email": form_data.get("approver_1_email", ""),
            "approver_2_email": form_data.get("approver_2_email", ""),
            "approver_3_email": form_data.get("approver_3_email", ""),
        }

        # Update report metadata
        report.document_title = context.get('DOCUMENT_TITLE', '')
        report.updated_at = dt.datetime.utcnow()

        # Prepare submission data for storage
        submission_data = {
            "context": context,
            "user_email": current_user.email if hasattr(current_user, 'email') else form_data.get("user_email", ""),
            "approvals": existing_data.get("approvals", []),
            "locked": existing_data.get("locked", False),
            "scada_image_urls": existing_data.get("scada_image_urls", []),
            "trends_image_urls": existing_data.get("trends_image_urls", []),
            "alarm_image_urls": existing_data.get("alarm_image_urls", []),
            "created_at": existing_data.get("created_at", dt.datetime.now().isoformat()),
            "updated_at": dt.datetime.now().isoformat(),
            "auto_saved": True  # Mark as auto-saved
        }

        # Update SAT report data
        sat_report.data_json = json.dumps(submission_data)
        sat_report.date = context.get('DATE', '')
        sat_report.purpose = context.get('PURPOSE', '')
        sat_report.scope = context.get('SCOPE', '')

        # Save to database
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Auto-save completed',
            'submission_id': submission_id,
            'timestamp': dt.datetime.now().isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error in auto-save: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Auto-save failed: {str(e)}'
        }), 500