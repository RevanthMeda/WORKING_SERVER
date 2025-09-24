"""
Report generation and processing background tasks.
"""
import logging
import os
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime
from celery import current_task
from flask import current_app
from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def generate_report_task(self, report_id: str, report_type: str, 
                        report_data: Dict[str, Any],
                        output_format: str = 'pdf') -> Dict[str, Any]:
    """
    Generate report document asynchronously.
    
    Args:
        report_id: Unique report identifier
        report_type: Type of report (SAT, FDS, HDS, etc.)
        report_data: Report data for generation
        output_format: Output format (pdf, docx, html)
    
    Returns:
        Dict with generation result and file path
    """
    try:
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing report generation', 'progress': 10}
        )
        
        logger.info(f"Starting report generation for {report_id} ({report_type})")
        
        # Import report generation modules
        from models import db, Report
        from utils.report_generator import ReportGenerator
        
        # Get report from database
        report = Report.query.get(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Loading report data', 'progress': 25}
        )
        
        # Initialize report generator
        generator = ReportGenerator(report_type)
        
        # Prepare output directory
        output_dir = current_app.config.get('REPORT_OUTPUT_DIR', '/tmp/reports')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{report_type}_{report_id}_{timestamp}.{output_format}"
        output_path = os.path.join(output_dir, filename)
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Generating document', 'progress': 50}
        )
        
        # Generate report based on type
        if report_type.upper() == 'SAT':
            result = generator.generate_sat_report(report_data, output_path, output_format)
        elif report_type.upper() == 'FDS':
            result = generator.generate_fds_report(report_data, output_path, output_format)
        elif report_type.upper() == 'HDS':
            result = generator.generate_hds_report(report_data, output_path, output_format)
        else:
            result = generator.generate_generic_report(report_data, output_path, output_format)
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Finalizing document', 'progress': 75}
        )
        
        # Verify file was created
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Generated report file not found: {output_path}")
        
        # Get file size
        file_size = os.path.getsize(output_path)
        
        # Update report status in database
        report.status = 'GENERATED'
        report.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Report generation completed', 'progress': 100}
        )
        
        logger.info(f"Report generation completed for {report_id}: {output_path}")
        
        return {
            'status': 'success',
            'report_id': report_id,
            'report_type': report_type,
            'output_path': output_path,
            'filename': filename,
            'file_size': file_size,
            'output_format': output_format,
            'generated_at': datetime.utcnow().isoformat(),
            'generation_time': current_task.request.eta or 'unknown'
        }
        
    except Exception as e:
        logger.error(f"Report generation failed for {report_id}: {e}")
        
        # Update report status to failed
        try:
            from models import db, Report
            report = Report.query.get(report_id)
            if report:
                report.status = 'GENERATION_FAILED'
                report.updated_at = datetime.utcnow()
                db.session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update report status: {db_error}")
        
        # Retry on certain errors
        if isinstance(e, (ConnectionError, TimeoutError)) and self.request.retries < self.max_retries:
            try:
                raise self.retry(countdown=120 * (self.request.retries + 1))
            except self.MaxRetriesExceededError:
                pass
        
        return {
            'status': 'failed',
            'error': str(e),
            'report_id': report_id,
            'report_type': report_type,
            'failed_at': datetime.utcnow().isoformat()
        }


@celery_app.task(bind=True)
def process_report_approval_task(self, report_id: str, approver_email: str, 
                               approval_action: str, comments: Optional[str] = None) -> Dict[str, Any]:
    """
    Process report approval workflow.
    
    Args:
        report_id: Report identifier
        approver_email: Email of the approver
        approval_action: 'approve' or 'reject'
        comments: Optional approval comments
    
    Returns:
        Dict with approval processing result
    """
    try:
        logger.info(f"Processing approval for report {report_id} by {approver_email}: {approval_action}")
        
        # Import required modules
        from models import db, Report, User
        from tasks.email_tasks import send_notification_email_task
        
        # Get report and approver
        report = Report.query.get(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found")
        
        approver = User.query.filter_by(email=approver_email).first()
        if not approver:
            raise ValueError(f"Approver {approver_email} not found")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Processing approval', 'progress': 25}
        )
        
        # Process approval
        approval_data = {
            'approver_email': approver_email,
            'approver_name': approver.full_name,
            'action': approval_action,
            'comments': comments,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Update report approval status
        if approval_action.lower() == 'approve':
            report.status = 'APPROVED'
            notification_type = 'report_approved'
        elif approval_action.lower() == 'reject':
            report.status = 'REJECTED'
            notification_type = 'report_rejected'
        else:
            raise ValueError(f"Invalid approval action: {approval_action}")
        
        # Update report approvals JSON
        approvals = report.approvals_json or '[]'
        import json
        approvals_list = json.loads(approvals)
        approvals_list.append(approval_data)
        report.approvals_json = json.dumps(approvals_list)
        report.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Sending notifications', 'progress': 50}
        )
        
        # Send notification to report creator
        creator = User.query.filter_by(email=report.user_email).first()
        if creator:
            notification_data = {
                'user_name': creator.full_name,
                'report_title': report.document_title or f"{report.type} Report",
                'document_reference': report.document_reference,
                'approved_by' if approval_action.lower() == 'approve' else 'rejected_by': approver.full_name,
                'approved_at' if approval_action.lower() == 'approve' else 'rejected_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'rejection_reason': comments if approval_action.lower() == 'reject' else None,
                'report_url': f"{current_app.config.get('BASE_URL', '')}/reports/{report_id}"
            }
            
            # Send notification email asynchronously
            send_notification_email_task.apply_async(
                args=[creator.email, notification_type, notification_data]
            )
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Approval processing completed', 'progress': 100}
        )
        
        logger.info(f"Approval processed successfully for report {report_id}")
        
        return {
            'status': 'success',
            'report_id': report_id,
            'approval_action': approval_action,
            'approver_email': approver_email,
            'new_status': report.status,
            'processed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Approval processing failed for report {report_id}: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'report_id': report_id,
            'approval_action': approval_action,
            'approver_email': approver_email
        }


@celery_app.task(bind=True)
def batch_report_generation_task(self, report_ids: list, output_format: str = 'pdf') -> Dict[str, Any]:
    """
    Generate multiple reports in batch.
    
    Args:
        report_ids: List of report IDs to generate
        output_format: Output format for all reports
    
    Returns:
        Dict with batch generation results
    """
    try:
        total_reports = len(report_ids)
        successful_generations = []
        failed_generations = []
        
        logger.info(f"Starting batch report generation for {total_reports} reports")
        
        # Process each report
        for i, report_id in enumerate(report_ids):
            try:
                # Update progress
                progress = int((i / total_reports) * 100)
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'status': f'Processing report {i+1} of {total_reports}',
                        'progress': progress,
                        'current_report': report_id,
                        'successful': len(successful_generations),
                        'failed': len(failed_generations)
                    }
                )
                
                # Get report data
                from models import Report
                report = Report.query.get(report_id)
                if not report:
                    failed_generations.append({
                        'report_id': report_id,
                        'error': 'Report not found'
                    })
                    continue
                
                # Prepare report data
                report_data = {
                    'id': report.id,
                    'type': report.type,
                    'document_title': report.document_title,
                    'document_reference': report.document_reference,
                    'project_reference': report.project_reference,
                    'client_name': report.client_name,
                    'revision': report.revision,
                    'prepared_by': report.prepared_by,
                    'user_email': report.user_email,
                    'version': report.version
                }
                
                # Generate report
                result = generate_report_task.apply_async(
                    args=[report_id, report.type, report_data, output_format]
                )
                
                # Wait for result (with timeout)
                generation_result = result.get(timeout=300)  # 5 minutes timeout
                
                if generation_result.get('status') == 'success':
                    successful_generations.append(generation_result)
                else:
                    failed_generations.append({
                        'report_id': report_id,
                        'error': generation_result.get('error', 'Unknown error')
                    })
                    
            except Exception as e:
                failed_generations.append({
                    'report_id': report_id,
                    'error': str(e)
                })
                logger.error(f"Failed to generate report {report_id}: {e}")
        
        success_rate = (len(successful_generations) / total_reports * 100) if total_reports > 0 else 0
        
        logger.info(f"Batch generation completed: {len(successful_generations)} successful, {len(failed_generations)} failed")
        
        return {
            'status': 'completed',
            'total_reports': total_reports,
            'successful_count': len(successful_generations),
            'failed_count': len(failed_generations),
            'success_rate': success_rate,
            'successful_generations': successful_generations,
            'failed_generations': failed_generations,
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Batch report generation failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'total_reports': len(report_ids),
            'successful_count': len(successful_generations),
            'failed_count': len(failed_generations)
        }


@celery_app.task(bind=True)
def cleanup_generated_reports_task(self, max_age_days: int = 30) -> Dict[str, Any]:
    """
    Clean up old generated report files.
    
    Args:
        max_age_days: Maximum age of files to keep in days
    
    Returns:
        Dict with cleanup results
    """
    try:
        import glob
        from datetime import datetime, timedelta
        
        logger.info(f"Starting cleanup of generated reports older than {max_age_days} days")
        
        # Get report output directory
        output_dir = current_app.config.get('REPORT_OUTPUT_DIR', '/tmp/reports')
        
        if not os.path.exists(output_dir):
            return {
                'status': 'success',
                'message': 'Report output directory does not exist',
                'files_deleted': 0,
                'space_freed': 0
            }
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        # Find old files
        pattern = os.path.join(output_dir, '*')
        all_files = glob.glob(pattern)
        
        files_deleted = 0
        space_freed = 0
        
        for file_path in all_files:
            try:
                # Check file age
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_mtime < cutoff_date:
                    # Get file size before deletion
                    file_size = os.path.getsize(file_path)
                    
                    # Delete file
                    os.remove(file_path)
                    
                    files_deleted += 1
                    space_freed += file_size
                    
                    logger.debug(f"Deleted old report file: {file_path}")
                    
            except Exception as e:
                logger.error(f"Failed to delete file {file_path}: {e}")
        
        logger.info(f"Cleanup completed: {files_deleted} files deleted, {space_freed} bytes freed")
        
        return {
            'status': 'success',
            'files_deleted': files_deleted,
            'space_freed': space_freed,
            'space_freed_mb': round(space_freed / (1024 * 1024), 2),
            'max_age_days': max_age_days,
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Report cleanup failed: {e}")
        return {
            'status': 'failed',
            'error': str(e),
            'max_age_days': max_age_days
        }