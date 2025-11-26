import os
import json
import logging
import smtplib
from email.message import EmailMessage
from docx import Document
from docx.oxml import parse_xml
from flask import current_app, url_for
import time
from werkzeug.utils import secure_filename
import uuid
import platform
import tempfile
from contextlib import contextmanager
from datetime import datetime
from models import Notification

# Added get_unread_count from app.py to resolve circular import
def get_unread_count(user_email=None):
    """Get unread notifications count for a user"""
    try:
        from flask_login import current_user

        if not user_email and current_user.is_authenticated:
            user_email = current_user.email

        if not user_email:
            return 0

        return Notification.query.filter_by(
            user_email=user_email,
            read=False
        ).count()
    except Exception as e:
        if current_app:
            current_app.logger.warning(f"Could not get unread count: {e}")
        return 0

# Windows-specific imports (only available on Windows)
try:
    import pythoncom
    import win32com.client
    windows_com_available = True
except ImportError:
    windows_com_available = False
    pythoncom = None
    win32com = None

logger = logging.getLogger(__name__)

# Cross-platform file locking
@contextmanager
def file_lock(filename, mode='r', timeout=30, delay=0.05):
    """
    A cross-platform file locking context manager that works on both Windows and Unix

    Args:
        filename: The file to lock
        mode: File open mode ('r' for read, 'w' for write)
        timeout: Maximum time to wait for lock (seconds)
        delay: Time between retry attempts (seconds)

    Yields:
        The opened file object
    """
    if platform.system() == 'Windows':
        import msvcrt

        is_exclusive = 'w' in mode
        file_mode = 'r+' if is_exclusive else 'r'

        # Make sure the file exists
        if not os.path.exists(filename) and is_exclusive:
            with open(filename, 'w') as f:
                f.write('{}')

        # Open and try to lock the file
        f = open(filename, file_mode)


        start_time = time.time()

        while True:
            try:
                # Lock from current position to end of file
                lock_mode = msvcrt.LK_NBLCK
                if is_exclusive:
                    lock_mode |= msvcrt.LK_LOCK
                else:
                    lock_mode |= msvcrt.LK_RLCK

                msvcrt.locking(f.fileno(), lock_mode, 0x7fffffff)
                break  # Lock acquired
            except IOError:
                # Could not acquire lock, wait and retry
                if time.time() - start_time > timeout:
                    f.close()
                    raise TimeoutError(f"Could not acquire lock on {filename} within {timeout} seconds")

                time.sleep(delay)

        try:
            yield f
        finally:
            # Unlock and close the file
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 0x7fffffff)
            except IOError:
                # Not locked
                pass
            f.close()

    else:
        # Unix-like systems
        import fcntl

        is_exclusive = 'w' in mode
        file_mode = 'r+' if is_exclusive else 'r'

        # Make sure the file exists
        if not os.path.exists(filename) and is_exclusive:
            with open(filename, 'w') as f:
                f.write('{}')

        # Open and try to lock the file
        f = open(filename, file_mode)


        start_time = time.time()

        while True:
            try:
                if is_exclusive:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore
                else:
                    fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)  # type: ignore
                break  # Lock acquired
            except IOError:
                # Could not acquire lock, wait and retry
                if time.time() - start_time > timeout:
                    f.close()
                    raise TimeoutError(f"Could not acquire lock on {filename} within {timeout} seconds")

                time.sleep(delay)

        try:
            yield f
        finally:
            # Unlock and close the file
            fcntl.flock(f, fcntl.LOCK_UN)  # type: ignore
            f.close()


def create_approval_notification(approver_email, submission_id, stage, document_title):
    """Create notification for approval request"""
    from flask import url_for

    title = f"Approval Required - Stage {stage}"
    message = f"SAT Report '{document_title}' requires your approval."
    action_url = url_for('approval.approve_submission', submission_id=submission_id, stage=stage, _external=True)

    return Notification.create_notification(
        user_email=approver_email,
        title=title,
        message=message,
        notification_type='approval_request',
        submission_id=submission_id,
        action_url=action_url
    )

def create_status_update_notification(user_email, submission_id, status, document_title, approver_name=""):
    """Create notification for status update"""
    from flask import url_for

    if status == "approved":
        title = "Report Approved"
        message = f"Your SAT Report '{document_title}' has been approved"
        if approver_name:
            message += f" by {approver_name}"
    elif status == "rejected":
        title = "Report Rejected"
        message = f"Your SAT Report '{document_title}' has been rejected"
        if approver_name:
            message += f" by {approver_name}"
    else:
        title = "Status Update"
        message = f"Your SAT Report '{document_title}' status has been updated to {status}"

    action_url = url_for('status.view_status', submission_id=submission_id, _external=True)

    return Notification.create_notification(
        user_email=user_email,
        title=title,
        message=message,
        notification_type='status_update',
        submission_id=submission_id,
        action_url=action_url
    )

def create_completion_notification(user_email, submission_id, document_title):
    """Create notification for report completion"""
    from flask import url_for

    title = "Report Completed"
    message = f"Your SAT Report '{document_title}' has been fully approved and is ready for download."
    action_url = url_for('status.download_report', submission_id=submission_id, _external=True)

    return Notification.create_notification(
        user_email=user_email,
        title=title,
        message=message,
        notification_type='completion',
        submission_id=submission_id,
        action_url=action_url
    )

def create_new_submission_notification(admin_emails, submission_id, document_title, submitter_email):
    """Create notification for new submission (for admins)"""
    from flask import url_for

    title = "New Report Submitted"
    message = f"New SAT Report '{document_title}' submitted by {submitter_email}"
    action_url = url_for('status.view_status', submission_id=submission_id, _external=True)

    notifications = []
    for admin_email in admin_emails:
        notification = Notification.create_notification(
            user_email=admin_email,
            title=title,
            message=message,
            notification_type='new_submission',
            submission_id=submission_id,
            action_url=action_url
        )
        notifications.append(notification)

    return notifications

# Updated function to use the new file lock
def load_submissions():
    submissions_file = current_app.config.get('SUBMISSIONS_FILE', os.path.join(current_app.root_path, 'data', 'submissions.json'))

    # If file doesn't exist, return empty dict
    if not os.path.exists(submissions_file):
        return {}

    try:
        with file_lock(submissions_file, mode='r') as f:
            try:
                data = json.load(f)
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON in {submissions_file}: {e}")
                # Return empty dict on decode error rather than potentially corrupting data
                return {}
    except TimeoutError as e:
        logger.error(f"Timeout acquiring read lock on submissions file: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error loading submissions: {e}", exc_info=True)
        return {}
def save_submissions(submissions):
    """Save submissions data with improved file locking"""
    from flask import current_app

    submissions_file = current_app.config['SUBMISSIONS_FILE']

    try:
        # Create parent directory if needed
        os.makedirs(os.path.dirname(submissions_file), exist_ok=True)

        # Use a temporary file for atomic write
        temp_dir = os.path.dirname(submissions_file)
        fd, temp_path = tempfile.mkstemp(dir=temp_dir, prefix=os.path.basename(submissions_file) + '.')

        # Write to temp file first
        with os.fdopen(fd, 'w') as f:
            json.dump(submissions, f, indent=2)

        # Now use file lock to replace the original file atomically
        with file_lock(submissions_file, mode='w') as f:
            # Read the existing content to back up if needed
            try:
                f.seek(0)
                old_data = f.read()
            except:
                old_data = "{}"

            try:
                # Replace file content with our temp file content
                with open(temp_path, 'r') as temp_f:
                    new_data = temp_f.read()

                # Truncate and write
                f.seek(0)
                f.truncate()
                f.write(new_data)
                f.flush()
                os.fsync(f.fileno())

            except Exception as e:
                # On error, try to restore old content
                logger.error(f"Error during file write, attempting to restore: {e}")
                f.seek(0)
                f.truncate()
                f.write(old_data)
                f.flush()
                raise

        # Remove the temp file
        try:
            os.unlink(temp_path)
        except:
            pass

        return True

    except TimeoutError as e:
        logger.error(f"Timeout acquiring write lock on submissions file: {e}")
        return False
    except Exception as e:
        logger.error(f"Error saving submissions: {e}", exc_info=True)
        return False

# --------------------
# Email functions
def send_email(to_email, subject, html_content, text_content=None):
    """Send an HTML email with plain text fallback"""
    if not to_email:
        logger.warning("No recipient email provided")
        return False

    # Log attempt
    logger.info(f"Attempting to send email to {to_email}")

    # Get fresh email configuration (prevents password caching)
    import importlib.util
    import os
    config_file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config.py')
    spec = importlib.util.spec_from_file_location("config_module", config_file_path)
    if not (spec and spec.loader):
        logger.error("Could not load config.py from root to get SMTP credentials.")
        return False
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    Config = config_module.Config
    credentials = Config.get_smtp_credentials()
    
    smtp_server = (credentials.get('server') or '').strip()
    smtp_port = credentials.get('port') 
    smtp_username = (credentials.get('username') or '').strip()
    smtp_password = (credentials.get('password') or '').strip()

    if not smtp_username or not smtp_password:
        logger.error("SMTP credentials are not configured")
        return False
    
    # Enhanced Gmail debugging
    if 'gmail.com' in smtp_server.lower():
        logger.info(f"Gmail detected. Username: {smtp_username}")
        logger.info(f"Password length: {len(smtp_password)} characters")
        logger.info(f"Password starts with: {smtp_password[:4]}... (masked)")
        logger.info(f"Password format check: {'✓' if len(smtp_password) == 16 else '✗'}")
        if len(smtp_password) != 16:
            logger.warning("Gmail App Password should be exactly 16 characters")
            logger.warning("Visit https://support.google.com/accounts/answer/185833 to generate an App Password")

    # Create message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = credentials['sender'] or smtp_username
    msg["To"] = to_email
    msg.set_content(text_content or html_content.replace("<br>", "\n").replace("<p>", "").replace("</p>", "\n\n"))
    msg.add_alternative(html_content, subtype="html")

    retries = 3
    for i in range(retries):
        try:
            logger.info(f"Email send attempt {i+1}/{retries}")
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.set_debuglevel(1)  # Enable detailed debugging
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            logger.info(f"Email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Email attempt {i+1}/{retries} failed: {str(e)}", exc_info=True)
            if i == retries - 1:
                return False
            time.sleep(2)
    return False



def send_edit_link(user_email, submission_id, subject=None, html_content=None):
    """Send an email with the edit link for a submission"""
    if not user_email:
        return False

    if not subject or not html_content:
        edit_url = url_for("main.edit_submission", submission_id=submission_id, _external=True)
        status_url = url_for("status.view_status", submission_id=submission_id, _external=True)

        subject = "Your SAT Report Edit Link"
        html_content = f"""
        <html>
        <body>
            <h1>SAT Report System</h1>
            <p>Thank you for submitting your SAT report. You can edit your submission by clicking the link below:</p>
            <p><a href=\"{edit_url}\"> {edit_url}</a></p>
            <p>You can also check the status of your submission at any time:</p>
            <p><a href="{status_url}">{status_url}</a></p>
            <p>This edit link will remain active until the first approval stage is complete.</p>
        </body>
        </html>
        """

    return send_email(user_email, subject, html_content)

def send_approval_link(approver_email, submission_id, stage, subject=None, html_content=None):
    """Send an email with the approval link for a submission"""
    if not approver_email:
        logger.warning("No approver email provided")
        return False

    approval_url = url_for("approval.approve_submission", submission_id=submission_id, stage=stage, _external=True)
    status_url = url_for("status.view_status", submission_id=submission_id, _external=True)

    # Find the approver title
    approver_title = "Approver"
    for approver in current_app.config['DEFAULT_APPROVERS']:
        if approver['stage'] == stage:
            approver_title = approver.get('title', 'Approver')
            break

    # Attempt AI-enhanced email if details were not provided
    if (not subject or not html_content) and current_app.config.get('GEMINI_API_KEY'):
        try:
            from models import Report, SATReport
            from services.email_generator import generate_email_content

            report_obj = Report.query.get(submission_id)
            if report_obj and report_obj.type == 'SAT':
                sat_report = SATReport.query.filter_by(report_id=submission_id).first()
                if sat_report:
                    sat_payload = json.loads(sat_report.data_json or '{}')
                    report_context = sat_payload.get('context', {})
                    report_context['type'] = report_obj.type
                    if report_obj.document_title:
                        report_context.setdefault('DOCUMENT_TITLE', report_obj.document_title)
                        report_context['document_title'] = report_obj.document_title
                    if report_obj.project_reference:
                        report_context.setdefault('PROJECT_REFERENCE', report_obj.project_reference)
                        report_context['project_reference'] = report_obj.project_reference
                    if report_obj.client_name:
                        report_context.setdefault('CLIENT_NAME', report_obj.client_name)
                        report_context['client_name'] = report_obj.client_name

                    extra = {
                        'stage': stage,
                        'approver_title': approver_title,
                        'approval_url': approval_url,
                        'status_url': status_url,
                    }
                    ai_email = generate_email_content(report_context, audience='approver', extra=extra)
                    subject = subject or ai_email.get('subject')
                    html_content = html_content or ai_email.get('body')
        except Exception as ai_error:
            logger.warning(f"AI-enhanced approval email failed: {ai_error}")

    if not subject or not html_content:
        subject = f"Approval required for SAT Report (Stage {stage} - {approver_title})"
        html_content = f"""
        <html>
        <body>
            <h1>SAT Report Approval Request</h1>
            <p>A SAT report requires your approval as the {approver_title}.</p>
            <p>Please review and approve the report by clicking the link below:</p>
            <p><a href="{approval_url}">{approval_url}</a></p>
            <p>This is approval stage {stage} of the workflow.</p>
            <p>You can also view the current status of this submission:</p>
            <p><a href="{status_url}">{status_url}</a></p>
        </body>
        </html>
        """

    return send_email(approver_email, subject, html_content)

def send_client_final_document(client_email, submission_id, document_title, extra_message=None):
    """Notify the client that the final document is ready."""
    if not client_email:
        logger.warning("No client email provided for final document notification")
        return False

    document_title = document_title or 'SAT Report'
    download_url = url_for('status.download_report', submission_id=submission_id, _external=True)
    modern_url = url_for('status.download_report_modern', submission_id=submission_id, _external=True)
    status_url = url_for('status.view_status', submission_id=submission_id, _external=True)

    subject = f"Final {document_title} is ready"

    extra_html = f"<p>{extra_message}</p>" if extra_message else ""

    html_content = f"""
    <html>
    <body>
        <h1>{document_title} Approved</h1>
        <p>The final version of the report has been approved and is ready for your records.</p>
        {extra_html}
        <p>You can download the final document using the links below:</p>
        <ul>
            <li><a href="{download_url}">Download Word Document</a></li>
            <li><a href="{modern_url}">Download Modern Format</a></li>
            <li><a href="{status_url}">View approval history</a></li>
        </ul>
        <p>If you have any questions, please reply to this message.</p>
    </body>
    </html>
    """

    return send_email(client_email, subject, html_content)

def notify_completion(user_email, submission_id):
    """Notify the submitter that all approvals are complete"""
    if not user_email:
        return False

    download_url = url_for("status.download_report", submission_id=submission_id, _external=True)
    status_url = url_for("status.view_status", submission_id=submission_id, _external=True)

    subject = "Your SAT Report has been fully approved"
    html_content = f"""
    <html>
    <body>
        <h1>SAT Report Fully Approved</h1>
        <p>Great news! Your SAT report has been fully approved by all required parties.</p>
        <p>You can download the final approved report here:</p>
        <p><a href="{download_url}">{download_url}</a></p>
        <p>View the approval details:</p>
        <p><a href="{status_url}">{status_url}</a></p>
        <p>Thank you for using the SAT Report System.</p>
    </body>
    </html>
    """

    return send_email(user_email, subject, html_content)

# --------------------
# DOCX processing functions
def enable_autofit_tables(docx_path, target_keywords):
    """Make tables auto-fit their content based on keyword matching in the first row"""
    try:
        doc = Document(docx_path)
        modified = False

        for table in doc.tables:
            if not table.rows:
                continue

            first_row_text = " ".join(cell.text.lower() for cell in table.rows[0].cells)
            if any(keyword in first_row_text for keyword in target_keywords):
                for row in table.rows:
                    for cell in row.cells:
                        tc = cell._tc
                        tcPr = tc.get_or_add_tcPr()
                        auto_width = parse_xml(
                            r'<w:tcW w:w="0" w:w="0" w:type="auto" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
                        )
                        tcPr.append(auto_width)
                        tr = row._tr
                        trPr = tr.get_or_add_trPr()
                        trHeight = parse_xml(
                            r'<w:trHeight w:val="0" w:hRule="auto" xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
                        )
                        trPr.append(trHeight)
                modified = True

        if modified:
            doc.save(docx_path)
            logger.info(f"Table auto-fit applied to {docx_path}")

    except Exception as e:
        logger.error(f"Error applying table auto-fit: {e}", exc_info=True)
        raise

def update_toc(doc_path):
    """Update the table of contents in a Word document using COM automation"""
    if not windows_com_available:
        logger.warning("Windows COM automation not available - skipping TOC update")
        return

    pythoncom.CoInitialize()  # Initialize COM for the thread
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        abs_doc_path = os.path.abspath(doc_path)
        doc_word = word.Documents.Open(abs_doc_path)
        doc_word.Fields.Update()
        doc_word.Save()
        doc_word.Close()
        word.Quit()
        logger.info(f"TOC updated in {doc_path}")
    except Exception as e:
        logger.error(f"Error updating TOC: {e}", exc_info=True)
        raise
    finally:
        pythoncom.CoUninitialize()

def convert_to_pdf(docx_path):
    """Convert a DOCX file to PDF using Word automation"""
    if not current_app.config.get('ENABLE_PDF_EXPORT', False):
        logger.warning("PDF export is disabled in configuration")
        return None

    if not windows_com_available:
        logger.warning("Windows COM automation not available - PDF conversion not supported on this platform")
        return None

    pythoncom.CoInitialize()  # Initialize COM for the thread
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        abs_doc_path = os.path.abspath(docx_path)
        pdf_path = abs_doc_path.replace('.docx', '.pdf')

        doc = word.Documents.Open(abs_doc_path)
        doc.SaveAs(pdf_path, FileFormat=17)  # 17 = PDF format
        doc.Close()
        word.Quit()

        logger.info(f"PDF created: {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.error(f"Error converting to PDF: {e}", exc_info=True)
        return None
    finally:
        pythoncom.CoUninitialize()

# --------------------
# Form processing helpers
def setup_approval_workflow(submission_id, submissions, approver_emails=None):
    """Create or update approval workflow stored in submissions.json."""
    approver_emails = approver_emails or []
    valid_emails = [email for email in approver_emails if email]

    submission = submissions.get(submission_id, {}) or {}
    approvals = submission.get('approvals') or []

    if approvals:
        for idx, approval in enumerate(approvals):
            if idx < len(valid_emails) and valid_emails[idx]:
                if approval.get('status', 'pending') == 'pending':
                    approval['approver_email'] = valid_emails[idx]
        locked = any(a.get('status') == 'approved' for a in approvals)
        submission['approvals'] = approvals
        submissions[submission_id] = submission
        return approvals, locked

    default_approvers = current_app.config.get('DEFAULT_APPROVERS', [])
    if not valid_emails and default_approvers:
        valid_emails = [
            approver.get('approver_email')
            for approver in default_approvers
            if approver.get('approver_email')
        ]
        stages = [
            approver.get('stage') or idx + 1
            for idx, approver in enumerate(default_approvers)
        ]
        titles = [
            approver.get('title', 'Approver')
            for approver in default_approvers
        ]
    else:
        stages = list(range(1, len(valid_emails) + 1))
        titles = ['Approver' for _ in valid_emails]

    if not valid_emails:
        submission['approvals'] = approvals
        submissions[submission_id] = submission
        return approvals, False

    approvals = []
    for idx, email in enumerate(valid_emails):
        stage = stages[idx] if idx < len(stages) else idx + 1
        title = titles[idx] if idx < len(titles) else 'Approver'
        approvals.append({
            'stage': stage,
            'approver_email': email,
            'title': title,
            'status': 'pending',
            'timestamp': None,
            'signature': None,
            'comment': ''
        })

    submission['approvals'] = approvals
    submissions[submission_id] = submission
    return approvals, False

def process_table_rows(form_data, field_mappings, *, add_placeholder=True):
    """Process multiple rows of table data from form fields.

    Args:
        form_data: The form data from request.form
        field_mappings: A dictionary mapping form field names to output field names
        add_placeholder: If True, include a blank row when no values are provided

    Returns:
        A list of dictionaries, each representing a row of data
    """
    if not field_mappings:
        return []

    first_field = next(iter(field_mappings))
    values = form_data.getlist(first_field)
    num_rows = len(values)

    rows = []
    for i in range(num_rows):
        row = {}
        for form_field, output_field in field_mappings.items():
            field_values = form_data.getlist(form_field)
            value = field_values[i] if i < len(field_values) else ""
            row[output_field] = value.strip()

        if any(row.values()):
            rows.append(row)

    if add_placeholder and not rows:
        rows.append({output_field: "" for output_field in field_mappings.values()})

    return rows

def setup_approval_workflow_db(report, approver_emails=None):
    """Create or refresh the approval workflow rows for a database-backed report."""
    approver_emails = approver_emails or []
    valid_emails = [email for email in approver_emails if email]

    approvals = []
    locked = False

    existing = []
    if getattr(report, 'approvals_json', None):
        try:
            existing = json.loads(report.approvals_json) or []
        except (TypeError, ValueError, json.JSONDecodeError):
            existing = []

    if existing:
        approvals = existing
        for idx, approval in enumerate(approvals):
            if idx < len(valid_emails) and valid_emails[idx]:
                if approval.get('status') == 'pending':
                    approval['approver_email'] = valid_emails[idx]
        locked = any(
            approval.get('status') == 'approved' and approval.get('stage', 0) > 1
            for approval in approvals
        )
        return approvals, locked

    default_approvers = current_app.config.get('DEFAULT_APPROVERS', [])
    if not valid_emails and default_approvers:
        valid_emails = [
            approver.get('approver_email')
            for approver in default_approvers
            if approver.get('approver_email')
        ]
        stages = [
            approver.get('stage') or idx + 1
            for idx, approver in enumerate(default_approvers)
        ]
    else:
        stages = list(range(1, len(valid_emails) + 1))

    if not valid_emails:
        return approvals, locked

    for idx, email in enumerate(valid_emails):
        stage = stages[idx] if idx < len(stages) else idx + 1
        approvals.append({
            'stage': stage,
            'approver_email': email,
            'status': 'pending',
            'approved_at': None,
            'signature': None,
            'comment': ''
        })

    return approvals, locked

def handle_image_removals(form_data, removal_field_name, url_list):
    """Handle removal of images marked for deletion and their physical files."""
    try:
        removed_images_str = form_data.get(removal_field_name)
        if not removed_images_str:
            return

        removed_urls = [url.strip() for url in removed_images_str.split(',') if url.strip()]
        
        # Create a copy of url_list to iterate over while modifying the original
        for url in list(url_list):
            if url in removed_urls:
                url_list.remove(url)
                try:
                    # Correctly derive the filesystem path from the URL
                    # URL is like: /static/uploads/<submission_id>/<filename>
                    if '/static/uploads/' in url:
                        # Path relative to the 'static' directory
                        relative_path = url.split('/static/')[1]
                        
                        # Build the absolute path
                        file_path = os.path.join(current_app.config['BASE_DIR'], 'static', relative_path)
                        
                        # Normalize the path to handle different OS separators
                        file_path = os.path.normpath(file_path)
                        
                        # Security check: ensure the path is within the UPLOAD_ROOT
                        upload_root = current_app.config['UPLOAD_ROOT']
                        if os.path.abspath(file_path).startswith(os.path.abspath(upload_root)):
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                current_app.logger.info(f"Successfully deleted image: {file_path}")
                            else:
                                current_app.logger.warning(f"Image file not found for deletion: {file_path}")
                        else:
                            current_app.logger.error(f"Security alert: Attempted to delete file outside of upload root: {file_path}")
                except Exception as e:
                    current_app.logger.error(f"Error deleting file for URL {url}: {e}", exc_info=True)

    except Exception as e:
        current_app.logger.error(f"Error in handle_image_removals: {e}", exc_info=True)

def get_safe_output_path(filename_hint=None, extension='docx'):
    """Return a unique, writable path inside the configured output directory."""
    output_dir = current_app.config.get('OUTPUT_DIR', 'outputs')
    os.makedirs(output_dir, exist_ok=True)

    if not filename_hint:
        filename_hint = f"SAT_Report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    base_name = secure_filename(filename_hint) or f"SAT_Report_{uuid.uuid4().hex}"
    if not base_name.lower().endswith(f".{extension.lower()}"):
        base_name = f"{base_name}.{extension}"

    candidate = os.path.join(output_dir, base_name)
    counter = 1
    while os.path.exists(candidate):
        name, ext = os.path.splitext(base_name)
        candidate = os.path.join(output_dir, f"{name}_{counter}{ext}")
        counter += 1

    return candidate

def allowed_file(filename):
    """Check if file extension is allowed"""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, upload_folder):
    """Save uploaded file"""
    try:
        os.makedirs(upload_folder, exist_ok=True)
        filename = file.filename
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        return filepath
    except Exception as e:
        print(f"Error saving file: {e}")
        return None

def generate_sat_report(data):
    """Generate SAT report (placeholder legacy helper)."""
    current_app.logger.info('generate_sat_report placeholder invoked')
    return {"success": True, "filename": "SAT_Report_Final.docx"}
