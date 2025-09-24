"""
Email-related background tasks.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Any, Optional
from celery import current_task
from flask import current_app, render_template_string
from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, to_email: str, subject: str, body: str, 
                   html_body: Optional[str] = None, 
                   attachments: Optional[List[Dict[str, Any]]] = None,
                   template: Optional[str] = None,
                   template_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Send email asynchronously.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Plain text body
        html_body: HTML body (optional)
        attachments: List of attachment dictionaries with 'filename' and 'content'
        template: Email template name (optional)
        template_data: Data for template rendering (optional)
    
    Returns:
        Dict with task result information
    """
    try:
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Preparing email', 'progress': 25}
        )
        
        # Get email configuration
        smtp_server = current_app.config.get('SMTP_SERVER', 'localhost')
        smtp_port = current_app.config.get('SMTP_PORT', 587)
        smtp_username = current_app.config.get('SMTP_USERNAME')
        smtp_password = current_app.config.get('SMTP_PASSWORD')
        smtp_use_tls = current_app.config.get('SMTP_USE_TLS', True)
        from_email = current_app.config.get('MAIL_FROM', 'noreply@example.com')
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        
        # Render template if provided
        if template and template_data:
            try:
                # Simple template rendering (in production, use Jinja2 templates)
                rendered_body = render_template_string(body, **template_data)
                if html_body:
                    rendered_html = render_template_string(html_body, **template_data)
                else:
                    rendered_html = None
            except Exception as e:
                logger.warning(f"Template rendering failed: {e}, using original content")
                rendered_body = body
                rendered_html = html_body
        else:
            rendered_body = body
            rendered_html = html_body
        
        # Add text part
        text_part = MIMEText(rendered_body, 'plain', 'utf-8')
        msg.attach(text_part)
        
        # Add HTML part if provided
        if rendered_html:
            html_part = MIMEText(rendered_html, 'html', 'utf-8')
            msg.attach(html_part)
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Adding attachments', 'progress': 50}
        )
        
        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                try:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['content'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    msg.attach(part)
                except Exception as e:
                    logger.error(f"Failed to attach file {attachment.get('filename', 'unknown')}: {e}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Sending email', 'progress': 75}
        )
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_use_tls:
                server.starttls()
            
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        
        return {
            'status': 'success',
            'message': f'Email sent to {to_email}',
            'to_email': to_email,
            'subject': subject,
            'sent_at': current_task.request.eta or 'now'
        }
        
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {to_email}: {e}")
        
        # Retry on SMTP errors
        try:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        except self.MaxRetriesExceededError:
            return {
                'status': 'failed',
                'error': f'SMTP error after {self.max_retries} retries: {str(e)}',
                'to_email': to_email
            }
    
    except Exception as e:
        logger.error(f"Unexpected error sending email to {to_email}: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'to_email': to_email
        }


@celery_app.task(bind=True, max_retries=2)
def send_bulk_email_task(self, email_list: List[Dict[str, Any]], 
                        subject: str, body: str,
                        html_body: Optional[str] = None,
                        batch_size: int = 50) -> Dict[str, Any]:
    """
    Send bulk emails asynchronously.
    
    Args:
        email_list: List of email dictionaries with 'email' and optional 'data' for personalization
        subject: Email subject
        body: Plain text body
        html_body: HTML body (optional)
        batch_size: Number of emails to send per batch
    
    Returns:
        Dict with bulk email results
    """
    try:
        total_emails = len(email_list)
        sent_count = 0
        failed_count = 0
        failed_emails = []
        
        # Process emails in batches
        for i in range(0, total_emails, batch_size):
            batch = email_list[i:i + batch_size]
            
            # Update progress
            progress = int((i / total_emails) * 100)
            current_task.update_state(
                state='PROGRESS',
                meta={
                    'status': f'Processing batch {i//batch_size + 1}',
                    'progress': progress,
                    'sent': sent_count,
                    'failed': failed_count
                }
            )
            
            # Send emails in current batch
            for email_data in batch:
                try:
                    email_address = email_data['email']
                    personalization_data = email_data.get('data', {})
                    
                    # Personalize subject and body if data provided
                    personalized_subject = subject
                    personalized_body = body
                    personalized_html = html_body
                    
                    if personalization_data:
                        try:
                            personalized_subject = render_template_string(subject, **personalization_data)
                            personalized_body = render_template_string(body, **personalization_data)
                            if html_body:
                                personalized_html = render_template_string(html_body, **personalization_data)
                        except Exception as e:
                            logger.warning(f"Personalization failed for {email_address}: {e}")
                    
                    # Send individual email
                    result = send_email_task.apply_async(
                        args=[email_address, personalized_subject, personalized_body],
                        kwargs={'html_body': personalized_html}
                    )
                    
                    # Wait for result (with timeout)
                    email_result = result.get(timeout=30)
                    
                    if email_result.get('status') == 'success':
                        sent_count += 1
                    else:
                        failed_count += 1
                        failed_emails.append({
                            'email': email_address,
                            'error': email_result.get('error', 'Unknown error')
                        })
                        
                except Exception as e:
                    failed_count += 1
                    failed_emails.append({
                        'email': email_data.get('email', 'unknown'),
                        'error': str(e)
                    })
                    logger.error(f"Failed to send email to {email_data.get('email', 'unknown')}: {e}")
        
        logger.info(f"Bulk email completed: {sent_count} sent, {failed_count} failed")
        
        return {
            'status': 'completed',
            'total_emails': total_emails,
            'sent_count': sent_count,
            'failed_count': failed_count,
            'failed_emails': failed_emails[:10],  # Return first 10 failures
            'success_rate': (sent_count / total_emails * 100) if total_emails > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Bulk email task failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'total_emails': len(email_list),
            'sent_count': sent_count,
            'failed_count': failed_count
        }


@celery_app.task(bind=True)
def send_notification_email_task(self, user_email: str, notification_type: str, 
                                data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send notification email based on type.
    
    Args:
        user_email: Recipient email
        notification_type: Type of notification (report_approved, report_rejected, etc.)
        data: Notification data
    
    Returns:
        Dict with task result
    """
    try:
        # Define notification templates
        templates = {
            'report_approved': {
                'subject': 'Report Approved: {{ report_title }}',
                'body': '''
Hello {{ user_name }},

Your report "{{ report_title }}" has been approved.

Report Details:
- Document Reference: {{ document_reference }}
- Approved by: {{ approved_by }}
- Approved at: {{ approved_at }}

You can view the approved report at: {{ report_url }}

Best regards,
SAT Report Generator Team
                ''',
                'html_body': '''
<h2>Report Approved</h2>
<p>Hello {{ user_name }},</p>
<p>Your report "<strong>{{ report_title }}</strong>" has been approved.</p>
<h3>Report Details:</h3>
<ul>
    <li><strong>Document Reference:</strong> {{ document_reference }}</li>
    <li><strong>Approved by:</strong> {{ approved_by }}</li>
    <li><strong>Approved at:</strong> {{ approved_at }}</li>
</ul>
<p><a href="{{ report_url }}">View Approved Report</a></p>
<p>Best regards,<br>SAT Report Generator Team</p>
                '''
            },
            'report_rejected': {
                'subject': 'Report Rejected: {{ report_title }}',
                'body': '''
Hello {{ user_name }},

Your report "{{ report_title }}" has been rejected.

Report Details:
- Document Reference: {{ document_reference }}
- Rejected by: {{ rejected_by }}
- Rejected at: {{ rejected_at }}
- Reason: {{ rejection_reason }}

Please review the feedback and resubmit your report.

Best regards,
SAT Report Generator Team
                ''',
                'html_body': '''
<h2>Report Rejected</h2>
<p>Hello {{ user_name }},</p>
<p>Your report "<strong>{{ report_title }}</strong>" has been rejected.</p>
<h3>Report Details:</h3>
<ul>
    <li><strong>Document Reference:</strong> {{ document_reference }}</li>
    <li><strong>Rejected by:</strong> {{ rejected_by }}</li>
    <li><strong>Rejected at:</strong> {{ rejected_at }}</li>
    <li><strong>Reason:</strong> {{ rejection_reason }}</li>
</ul>
<p>Please review the feedback and resubmit your report.</p>
<p>Best regards,<br>SAT Report Generator Team</p>
                '''
            },
            'approval_request': {
                'subject': 'Approval Request: {{ report_title }}',
                'body': '''
Hello {{ approver_name }},

A new report is awaiting your approval.

Report Details:
- Title: {{ report_title }}
- Document Reference: {{ document_reference }}
- Created by: {{ created_by }}
- Created at: {{ created_at }}

Please review and approve/reject the report at: {{ approval_url }}

Best regards,
SAT Report Generator Team
                ''',
                'html_body': '''
<h2>Approval Request</h2>
<p>Hello {{ approver_name }},</p>
<p>A new report is awaiting your approval.</p>
<h3>Report Details:</h3>
<ul>
    <li><strong>Title:</strong> {{ report_title }}</li>
    <li><strong>Document Reference:</strong> {{ document_reference }}</li>
    <li><strong>Created by:</strong> {{ created_by }}</li>
    <li><strong>Created at:</strong> {{ created_at }}</li>
</ul>
<p><a href="{{ approval_url }}">Review and Approve/Reject</a></p>
<p>Best regards,<br>SAT Report Generator Team</p>
                '''
            }
        }
        
        # Get template for notification type
        template = templates.get(notification_type)
        if not template:
            raise ValueError(f"Unknown notification type: {notification_type}")
        
        # Send email using template
        result = send_email_task.apply_async(
            args=[user_email, template['subject'], template['body']],
            kwargs={
                'html_body': template['html_body'],
                'template_data': data
            }
        )
        
        return result.get(timeout=60)
        
    except Exception as e:
        logger.error(f"Failed to send notification email: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'notification_type': notification_type,
            'user_email': user_email
        }