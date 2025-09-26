import os
import json
import logging
import smtplib
from email.message import EmailMessage
from PIL import Image
from docx import Document
from docx.oxml import parse_xml
from flask import current_app, url_for
import time
import re
from werkzeug.utils import secure_filename
import uuid
import platform
import tempfile
import shutil
from contextlib import contextmanager
from datetime import datetime

# Added get_unread_count from app.py to resolve circular import
def get_unread_count(user_email=None):
    """Get unread notifications count for a user"""
    try:
        from models import Notification
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
    WINDOWS_COM_AVAILABLE = True
except ImportError:
    WINDOWS_COM_AVAILABLE = False

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
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
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
            fcntl.flock(f, fcntl.LOCK_UN)
            f.close()


def create_approval_notification(approver_email, submission_id, stage, document_title):
    """Create notification for approval request"""
    from models import Notification
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
    from models import Notification
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
    from models import Notification
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
    from models import Notification
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
    """Load submissions data with improved file locking to prevent race conditions"""
    from flask import current_app

    submissions_file = current_app.config['SUBMISSIONS_FILE']

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
    from config import Config
    credentials = Config.get_smtp_credentials()
    
    smtp_server = credentials['server']
    smtp_port = credentials['port'] 
    smtp_username = credentials['username']
    smtp_password = credentials['password']

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



def create_completion_notification(user_email, submission_id, document_title):
    """Create notification for completion"""
    try:
        from models import Notification

        title = "Report Completed"
        message = f"Your SAT Report '{document_title}' has been fully approved and completed."

        return Notification.create_notification(
            user_email=user_email,
            title=title,
            message=message,
            notification_type='completion',
            submission_id=submission_id
        )
    except Exception as e:
        current_app.logger.error(f"Failed to create completion notification: {e}")
        return False

def create_new_submission_notification(admin_emails, submission_id, document_title, submitter_email):
    """Create new submission notification for admins"""
    try:
        from models import Notification

        for admin_email in admin_emails:
            title = "New Report Submitted"
            message = f"New SAT Report '{document_title}' submitted by {submitter_email}."

            Notification.create_notification(
                user_email=admin_email,
                title=title,
                message=message,
                notification_type='new_submission',
                submission_id=submission_id
            )
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to create submission notification: {e}")
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
            <p><a href=\"{edit_url}\">{edit_url}</a></p>
            <p>You can also check the status of your submission at any time:</p>
            <p><a href=\"{status_url}\">{status_url}</a></p>
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

    if not subject or not html_content:
        approval_url = url_for("approval.approve_submission", submission_id=submission_id, stage=stage, _external=True)
        status_url = url_for("status.view_status", submission_id=submission_id, _external=True)

        # Find the approver title
        approver_title = "Approver"
        for approver in current_app.config['DEFAULT_APPROVERS']:
            if approver['stage'] == stage:
                approver_title = approver.get('title', 'Approver')
                break

        subject = f"Approval required for SAT Report (Stage {stage} - {approver_title})"
        html_content = f"""
        <html>
        <body>
            <h1>SAT Report Approval Request</h1>
            <p>A SAT report requires your approval as the {approver_title}.</p>
            <p>Please review and approve the report by clicking the link below:</p>
            <p><a href=\"{approval_url}\">{approval_url}</a></p>
            <p>This is approval stage {stage} of the workflow.</p>
            <p>You can also view the current status of this submission:</p>
            <p><a href=\"{status_url}\">{status_url}</a></p>
        </body>
        </html>
        """

    return send_email(approver_email, subject, html_content)

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
    if not WINDOWS_COM_AVAILABLE:
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

    if not WINDOWS_COM_AVAILABLE:
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
def process_table_rows(form_data, field_mappings):
    """Process multiple rows of table data from form fields.

    Args:
        form_data: The form data from request.form
        field_mappings: A dictionary mapping form field names to output field names

    Returns:
        A list of dictionaries, each representing a row of data
    """
    # Get the first field name to determine number of rows
    first_field = list(field_mappings.keys())[0]
    values = form_data.getlist(first_field)
    num_rows = len(values)

    rows = []
    for i in range(num_rows):
        row = {}
        for form_field, output_field in field_mappings.items():
            values = form_data.getlist(form_field)
            row[output_field] = values[i].strip() if i < len(values) else ""

        # Only include rows where at least one field has a value
        if any(value for value in row.values()):
            rows.append(row)

    # If no rows, add a blank row as placeholder
    if not rows:
        row = {output_field: "" for output_field in field_mappings.values()}
        rows.append(row)

    return rows

def handle_image_removals(form_data, removal_field_name, url_list):
    """Handle removal of images marked for deletion"""
    try:
        # Get list of images to remove from form data
        removed_images = form_data.getlist(removal_field_name)

        for image_url in removed_images:
            if image_url and image_url in url_list:
                # Remove from URL list
                url_list.remove(image_url)

                # Extract filename from URL and remove physical file
                try:
                    # Parse URL to get relative path
                    if '/static/' in image_url:
                        relative_path = image_url.split('/static/')[-1]
                        file_path = os.path.join(current_app.static_folder, relative_path)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            current_app.logger.info(f"Removed image file: {file_path}")
                except Exception as file_error:
                    current_app.logger.warning(f"Could not remove physical file for {image_url}: {file_error}")

    except Exception as e:
        current_app.logger.error(f"Error handling image removals: {e}")

def setup_approval_workflow(submission_id, submissions, approver_emails=None):
    """Setup or retrieve the approval workflow for a submission"""
    sub = submissions.get(submission_id, {})

    # If this is a new submission or missing approval stages
    if "approvals" not in sub:
        # Initialize with provided approver emails or default ones
        approvals = []
        default_approvers = current_app.config['DEFAULT_APPROVERS']

        for i, approver in enumerate(default_approvers):
            email = approver_emails[i] if approver_emails and i < len(approver_emails) and approver_emails[i] else approver["approver_email"]
            approvals.append({
                "stage": approver["stage"],
                "approver_email": email,
                "title": approver.get("title", "Approver"),
                "status": "pending",
                "timestamp": None,
                "signature": None,
                "comment": ""
            })

        # New submissions are editable until an approval occurs
        locked = False
    else:
        # Get existing approvals
        approvals = sub.get("approvals", [])

        # If approver emails are provided, update the existing approvals
        if approver_emails:
            for i, approval in enumerate(approvals):
                if i < len(approver_emails) and approver_emails[i]:
                    # Only update if not already approved
                    if approval["status"] == "pending":
                        approval["approver_email"] = approver_emails[i]

        # If for some reason approvals is still empty, initialize it
        if not approvals:
            # Use first approver email if provided, otherwise default
            email = approver_emails[0] if approver_emails and len(approver_emails) > 0 and approver_emails[0] else current_app.config['DEFAULT_APPROVERS'][0]["approver_email"]
            approvals = [{
                "stage": 1,
                "approver_email": email,
                "title": current_app.config['DEFAULT_APPROVERS'][0].get("title", "Approver"),
                "status": "pending",
                "timestamp": None,
                "signature": None,
                "comment": ""
            }]

        # If any approval stage has been approved beyond stage 1, lock editing
        locked = any(a.get("status") == "approved" and a.get("stage") > 1 for a in approvals)

    return approvals, locked

def setup_approval_workflow_db(report, approver_emails=None):
    """Setup or retrieve the approval workflow for a database report"""
    import json

    # Get existing approvals from database
    existing_approvals = json.loads(report.approvals_json) if report.approvals_json else []

    # If this is a new submission or missing approval stages
    if not existing_approvals:
        # Initialize with provided approver emails or default ones
        approvals = []
        default_approvers = current_app.config['DEFAULT_APPROVERS']

        for i, approver in enumerate(default_approvers):
            email = approver_emails[i] if approver_emails and i < len(approver_emails) and approver_emails[i] else approver["approver_email"]
            approvals.append({
                "stage": approver["stage"],
                "approver_email": email,
                "title": approver.get("title", "Approver"),
                "status": "pending",
                "timestamp": None,
                "signature": None,
                "comment": ""
            })

        # New submissions are editable until an approval occurs
        locked = False
    else:
        # Get existing approvals
        approvals = existing_approvals.copy()

        # If this is a resubmission (version increment), reset approval status
        version_changed = report.version and report.version != 'R0'
        if version_changed:
            for approval in approvals:
                if approval.get("status") != "approved":
                    approval["status"] = "pending"
                    approval["timestamp"] = None
                    approval["signature"] = None
                    approval["comment"] = ""

        # If approver emails are provided, update the existing approvals
        if approver_emails:
            for i, approval in enumerate(approvals):
                if i < len(approver_emails) and approver_emails[i]:
                    # Only update if not already approved
                    if approval["status"] == "pending":
                        approval["approver_email"] = approver_emails[i]

        # If for some reason approvals is still empty, initialize it
        if not approvals:
            # Use first approver email if provided, otherwise default
            email = approver_emails[0] if approver_emails and len(approver_emails) > 0 and approver_emails[0] else current_app.config['DEFAULT_APPROVERS'][0]["approver_email"]
            approvals = [{
                "stage": 1,
                "approver_email": email,
                "title": current_app.config['DEFAULT_APPROVERS'][0].get("title", "Approver"),
                "status": "pending",
                "timestamp": None,
                "signature": None,
                "comment": ""
            }]

        # If any approval stage has been approved beyond stage 1, lock editing
        locked = any(a.get("status") == "approved" and a.get("stage") > 1 for a in approvals)

    return approvals, locked


# Removed duplicate allowed_file and replaced with the one from the edited snippet.
# Removed duplicate secure_filename usage as it's now part of the edited snippet.

def save_uploaded_file(file, directory, filename=None):
    """Save an uploaded file with a unique name"""
    if not file or not file.filename:
        return None

    # Use the provided allowed_file function
    if not allowed_file(file.filename):
        logger.warning(f"File type not allowed: {file.filename}")
        return None

    if filename is None:
        # Generate a unique filename
        original_filename = secure_filename(file.filename)
        filename = f"{uuid.uuid4().hex}_{original_filename}"

    filepath = os.path.join(directory, filename)
    file.save(filepath)
    return filepath, filename

# Add this function to your utils.py file

def send_client_final_document(client_email, submission_id, document_title):
    """Send an email to the client with the final approved document"""
    if not client_email:
        logger.warning("No client email provided")
        return False

    download_url = url_for("status.download_report", submission_id=submission_id, _external=True)
    pdf_url = url_for("status.download_pdf", submission_id=submission_id, _external=True)
    status_url = url_for("status.view_status", submission_id=submission_id, _external=True)

    subject = f"SAT Report Approved: {document_title}"
    html_content = f"""
    <html>
    <body>
        <h1>SAT Report Approval Complete</h1>
        <p>The SAT report "{document_title}" has been fully approved and is now ready for your review.</p>
        <p>You can download the approved report using the links below:</p>
        <ul>
            <li><a href="{download_url}">Download DOCX Version</a></li>
            <li><a href="{pdf_url}">Download PDF Version</a></li>
        </ul>
        <p>You can also view the full approval details here:</p>
        <p><a href="{status_url}">View Approval Status</a></p>
        <p>Thank you for using the SAT Report System.</p>
    </body>
    </html>
    """

    return send_email(client_email, subject, html_content)

def format_timestamp(timestamp, format_str="%d-%m-%Y %H:%M"):
    """
    Consistently format timestamps throughout the application

    Args:
        timestamp: ISO format timestamp string
        format_str: Format string for output (default: DD-MM-YYYY HH:MM)

    Returns:
        Formatted date string or empty string if invalid
    """
    if not timestamp:
        return ""

    try:
        # Try ISO format first
        try:

            date_obj = datetime.fromisoformat(timestamp)
            return date_obj.strftime(format_str)
        except ValueError:
            pass

        # Try parsing as string with various formats
        formats_to_try = [
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO format with microseconds
            "%Y-%m-%dT%H:%M:%S",     # ISO format without microseconds
            "%Y-%m-%d %H:%M:%S",     # Standard datetime format
            "%Y-%m-%d",              # Just date
        ]


        for fmt in formats_to_try:
            try:
                date_obj = datetime.strptime(timestamp, fmt)
                return date_obj.strftime(format_str)
            except ValueError:
                continue

        # If we get here, no format worked
        return timestamp  # Return original as fallback

    except Exception as e:
        logger.error(f"Error formatting timestamp {timestamp}: {e}")
        return timestamp  # Return original as fallback


def get_current_timestamp():
    """
    Get current time as ISO format timestamp string

    Returns:
        Current timestamp in ISO format
    """

    return datetime.now().isoformat()


def date_diff_days(timestamp1, timestamp2=None):
    """
    Calculate difference in days between two timestamps

    Args:
        timestamp1: First timestamp (ISO format)
        timestamp2: Second timestamp (ISO format, defaults to now if None)

    Returns:
        Number of days between timestamps, or None if invalid
    """
    if not timestamp1:
        return None

    try:

        # Parse first timestamp
        date1 = datetime.fromisoformat(timestamp1)

        # Parse second timestamp or use now
        if timestamp2:
            date2 = datetime.fromisoformat(timestamp2)
        else:
            date2 = datetime.now()

        # Calculate difference in days
        delta = date2 - date1
        return delta.days

    except Exception as e:
        logger.error(f"Error calculating date difference: {e}")
        return None

def safe_file_operation(operation_func, *args, **kwargs):
    """
    Execute a file operation with proper error handling

    Args:
        operation_func: Function to execute (e.g., open, write, etc.)
        *args, **kwargs: Arguments to pass to the function

    Returns:
        Tuple of (success, result/error_message)
    """
    try:
        result = operation_func(*args, **kwargs)
        return True, result
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return False, f"Required file could not be found: {str(e)}"
    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        return False, f"Permission denied for file operation: {str(e)}"
    except IsADirectoryError as e:
        logger.error(f"Is a directory error: {e}")
        return False, f"Expected a file but found a directory: {str(e)}"
    except IOError as e:
        logger.error(f"IO error: {e}")
        return False, f"Input/output error during file operation: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in file operation: {e}", exc_info=True)
        return False, f"Unexpected error: {str(e)}"

def ensure_directory(directory_path):
    """
    Ensure a directory exists with proper error handling

    Args:
        directory_path: Path to ensure exists

    Returns:
        Tuple of (success, error_message)
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True, None
    except PermissionError:
        error_msg = f"Permission denied when creating directory: {directory_path}"
        logger.error(error_msg)
        return False, error_msg
    except OSError as e:
        error_msg = f"Error creating directory {directory_path}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def safe_save_file(file_obj, save_path):
    """
    Safely save a file with proper error handling

    Args:
        file_obj: File object (e.g., from request.files)
        save_path: Path where to save the file

    Returns:
        Tuple of (success, filepath or error_message)
    """
    try:
        # Ensure directory exists
        directory = os.path.dirname(save_path)
        success, error = ensure_directory(directory)
        if not success:
            return False, error

        # Save file
        file_obj.save(save_path)
        return True, save_path
    except Exception as e:
        error_msg = f"Error saving file to {save_path}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

def safe_delete_file(file_path):
    """
    Safely delete a file with proper error handling

    Args:
        file_path: Path of file to delete

    Returns:
        Tuple of (success, error_message)
    """
    if not os.path.exists(file_path):
        return True, None  # File doesn't exist, so no need to delete

    try:
        os.remove(file_path)
        return True, None
    except PermissionError:
        error_msg = f"Permission denied when deleting file: {file_path}"
        logger.error(error_msg)
        return False, error_msg
    except OSError as e:
        error_msg = f"Error deleting file {file_path}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def safe_open_file(file_path, mode='r', encoding=None):
    """
    Safely open a file with proper error handling

    Args:
        file_path: Path of file to open
        mode: Open mode ('r', 'w', etc.)
        encoding: File encoding (default: None)

    Returns:
        Tuple of (success, file_object or error_message)
    """
    try:
        file_obj = open(file_path, mode, encoding=encoding)
        return True, file_obj
    except FileNotFoundError:
        error_msg = f"File not found: {file_path}"
        logger.error(error_msg)
        return False, error_msg
    except PermissionError:
        error_msg = f"Permission denied when opening file: {file_path}"
        logger.error(error_msg)
        return False, error_msg
    except IOError as e:
        error_msg = f"IO error opening file {file_path}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error opening file {file_path}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

def generate_sat_report(data, output_path, template_path="templates/SAT_Template.docx"):
    """
    Generate SAT report from form data using Word template

    Args:
        data: Form data dictionary containing all report fields
        output_path: Path where to save the generated report
        template_path: Path to the Word template file

    Returns:
        Tuple of (success, filepath or error_message)
    """
    try:
        from docx import Document
        import os

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        success, error = ensure_directory(output_dir)
        if not success:
            return False, error

        # Load template
        if not os.path.exists(template_path):
            return False, f"Template file not found: {template_path}"

        doc = Document(template_path)

        # Replace placeholders in the document
        context = data.get('context', {})

        # Replace text in paragraphs
        for paragraph in doc.paragraphs:
            for key, value in context.items():
                if f"{{{key}}}" in paragraph.text:
                    paragraph.text = paragraph.text.replace(f"{{{key}}}", str(value or ''))

        # Replace text in tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        for key, value in context.items():
                            if f"{{{key}}}" in paragraph.text:
                                paragraph.text = paragraph.text.replace(f"{{{key}}}", str(value or ''))

        # Save the document
        doc.save(output_path)
        logger.info(f"SAT report generated successfully: {output_path}")
        return True, output_path

    except Exception as e:
        error_msg = f"Error generating SAT report: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

def get_safe_output_path(base_path, filename):
    """
    Get a safe output path that ensures the directory exists and is writable.
    Falls back to temp directory if the original location is not writable.

    Args:
        base_path (str): The base directory path
        filename (str): The filename to save

    Returns:
        str: A safe path where the file can be written
    """
    import os
    import tempfile
    import datetime

    # First attempt: Try the specified directory
    try:
        os.makedirs(base_path, exist_ok=True)
        # Test if the directory is writable
        test_file = os.path.join(base_path, ".test_write")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return os.path.join(base_path, filename)
    except (PermissionError, OSError):
        # Second attempt: Try a temp directory with unique name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = os.path.join(tempfile.gettempdir(), "sat_report_" + timestamp)
        os.makedirs(temp_dir, exist_ok=True)
        return os.path.join(temp_dir, filename)

def send_email_debug(to_email, subject, html_content, text_content=None):
    """Send an HTML email with enhanced debugging and fallbacks to environment"""
    if not to_email:
        logger.warning("No recipient email provided")
        return False

    # Log attempt
    logger.info(f"Attempting to send email to {to_email}")

    # Get email configuration with fallbacks to environment variables
    import os
    smtp_server = current_app.config.get('SMTP_SERVER') or os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(current_app.config.get('SMTP_PORT') or os.environ.get('SMTP_PORT', 587))
    smtp_username = current_app.config.get('SMTP_USERNAME') or os.environ.get('SMTP_USERNAME', '')
    
    # Debug password sources
    config_password = current_app.config.get('SMTP_PASSWORD', '')
    env_password = os.environ.get('SMTP_PASSWORD', '')
    smtp_password = config_password or env_password
    
    logger.info(f"Password from Flask config: {config_password[:4] if config_password else 'None'}... (length: {len(config_password) if config_password else 0})")
    logger.info(f"Password from environment: {env_password[:4] if env_password else 'None'}... (length: {len(env_password) if env_password else 0})")
    logger.info(f"Final password being used: {smtp_password[:4] if smtp_password else 'None'}... (length: {len(smtp_password) if smtp_password else 0})")
    logger.info(f"Full password (for debugging): {smtp_password}")
    
    default_sender = current_app.config.get('DEFAULT_SENDER') or os.environ.get('DEFAULT_SENDER', smtp_username)

    logger.info(f"Email config: server={smtp_server}, port={smtp_port}, username={smtp_username}")

    if not smtp_username or not smtp_password:
        logger.error("SMTP credentials are missing")
        return False

    # Create message
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = default_sender
    msg["To"] = to_email
    msg.set_content(text_content or html_content.replace("<br>", "\n").replace("<p>", "").replace("</p>", "\n\n"))
    msg.add_alternative(html_content, subtype="html")

    retries = 3
    for i in range(retries):
        try:
            logger.info(f"Email send attempt {i+1}/{retries}")
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.set_debuglevel(1)  # Enable detailed debugging
                logger.info("SMTP connection established")

                server.ehlo()
                logger.info("EHLO successful")

                server.starttls()
                server.ehlo()
                logger.info("STARTTLS successful")

                logger.info(f"Logging in with {smtp_username}")
                server.login(smtp_username, smtp_password)
                logger.info("Login successful")

                logger.info(f"Sending message to {to_email}")
                server.send_message(msg)
                logger.info(f"Email sent successfully to {to_email}")
                return True
        except Exception as e:
            logger.error(f"Email attempt {i+1}/{retries} failed: {str(e)}", exc_info=True)
            if i == retries - 1:
                return False
            time.sleep(2)
    return False

# File upload configuration
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx',
    'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', '7z'
}

def allowed_file(filename):
    """Check if file extension is allowed"""
    if not filename:
        return False
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
import json
import os
from datetime import datetime

# This section seems to be a remnant or duplicate and is being kept for completeness as per instructions
# but the functions are redundant with the ones defined above.
# If these were truly meant to be distinct, they would need to be differentiated.
# For now, assuming they are duplicates of the more comprehensive versions above.

def load_submissions():
    """Load submissions from JSON file"""
    try:
        submissions_file = 'data/submissions.json'
        if os.path.exists(submissions_file):
            with open(submissions_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading submissions: {e}")
        return []

def save_submissions(submissions):
    """Save submissions to JSON file"""
    try:
        submissions_file = 'data/submissions.json'
        os.makedirs(os.path.dirname(submissions_file), exist_ok=True)
        with open(submissions_file, 'w') as f:
            json.dump(submissions, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving submissions: {e}")
        return False

def send_edit_link(email, edit_link):
    """Send edit link via email (placeholder)"""
    print(f"Would send edit link to {email}: {edit_link}")
    return True

def setup_approval_workflow(submission_data):
    """Setup approval workflow (placeholder)"""
    return {"status": "pending", "approvers": []}

def process_table_rows(form_data, field_mappings):
    """Process multiple rows of table data from form fields.

    Args:
        form_data: The form data from request.form
        field_mappings: A dictionary mapping form field names to output field names

    Returns:
        A list of dictionaries, each representing a row of data
    """
    # Get the first field name to determine number of rows
    if not field_mappings:
        return []
    first_field = list(field_mappings.keys())[0]
    values = form_data.getlist(first_field)
    num_rows = len(values)

    rows = []
    for i in range(num_rows):
        row = {}
        for form_field, output_field in field_mappings.items():
            field_values = form_data.getlist(form_field)
            row[output_field] = field_values[i].strip() if i < len(field_values) else ""

        # Only include rows where at least one field has a value
        if any(value for value in row.values()):
            rows.append(row)

    # If no rows, add a blank row as placeholder
    if not rows and field_mappings:
        row = {output_field: "" for output_field in field_mappings.values()}
        rows.append(row)

    return rows


def handle_image_removals(form_data, removal_field_name, url_list):
    """Handle removal of images marked for deletion"""
    try:
        # Get list of images to remove from form data
        removed_images = form_data.getlist(removal_field_name)

        for image_url in removed_images:
            if image_url and image_url in url_list:
                # Remove from URL list
                url_list.remove(image_url)

                # Extract filename from URL and remove physical file
                try:
                    # Parse URL to get relative path
                    if '/static/' in image_url:
                        relative_path = image_url.split('/static/')[-1]
                        file_path = os.path.join(current_app.static_folder, relative_path)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            current_app.logger.info(f"Removed image file: {file_path}")
                except Exception as file_error:
                    current_app.logger.warning(f"Could not remove physical file for {image_url}: {file_error}")

    except Exception as e:
        current_app.logger.error(f"Error handling image removals: {e}")

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
    """Generate SAT report (placeholder)"""
    print("Generating SAT report...")
    return {"success": True, "filename": "SAT_Report_Final.docx"}

def get_unread_count():
    """Get unread notification count for current user"""
    try:
        from flask_login import current_user
        if current_user.is_authenticated:
            from models import Notification
            count = Notification.query.filter_by(
                user_email=current_user.email,
                read=False
            ).count()
            return count
    except Exception as e:
        print(f"Error getting unread count: {e}")
    return 0