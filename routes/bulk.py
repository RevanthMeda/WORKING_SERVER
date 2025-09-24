from flask import Blueprint, render_template, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from models import db, Report, SATReport, ReportArchive
from security.audit import AuditLog
from auth import role_required
from datetime import datetime, timedelta
import json
import zipfile
import io
import os

bulk_bp = Blueprint('bulk', __name__)

@bulk_bp.route('/operations')
@login_required
@role_required(['Admin', 'Automation Manager'])
def bulk_operations():
    """Bulk operations interface"""
    try:
        return render_template('bulk_operations.html', current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error loading bulk operations: {e}")
        return jsonify({'error': str(e)}), 500

@bulk_bp.route('/api/export', methods=['POST'])
@login_required
def bulk_export():
    """Export multiple reports as ZIP"""
    try:
        report_ids = request.json.get('report_ids', [])
        
        if not report_ids:
            return jsonify({'error': 'No reports selected'}), 400
        
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for report_id in report_ids:
                report = Report.query.get(report_id)
                
                if not report:
                    continue
                
                # Check permissions
                if report.user_email != current_user.email and current_user.role not in ['Admin', 'Automation Manager']:
                    continue
                
                # Get report file paths
                file_paths = []
                
                # Add Word document if exists
                word_path = f"outputs/{report.id}/SAT_{report.project_reference}.docx"
                if os.path.exists(word_path):
                    file_paths.append(word_path)
                
                # Add PDF if exists
                pdf_path = f"outputs/{report.id}/SAT_{report.project_reference}.pdf"
                if os.path.exists(pdf_path):
                    file_paths.append(pdf_path)
                
                # Add files to ZIP
                for file_path in file_paths:
                    if os.path.exists(file_path):
                        arc_name = f"{report.project_reference}/{os.path.basename(file_path)}"
                        zip_file.write(file_path, arcname=arc_name)
                
                # Log the export
                log_audit_action('export', 'report', report.id, f'Bulk export of report {report.id}')
        
        zip_buffer.seek(0)
        
        # Send ZIP file
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'reports_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error in bulk export: {e}")
        return jsonify({'error': str(e)}), 500

@bulk_bp.route('/api/status-update', methods=['POST'])
@login_required
@role_required(['Admin', 'Automation Manager'])
def bulk_status_update():
    """Update status for multiple reports"""
    try:
        data = request.json
        report_ids = data.get('report_ids', [])
        new_status = data.get('status')
        
        if not report_ids or not new_status:
            return jsonify({'error': 'Missing required fields'}), 400
        
        updated_count = 0
        
        for report_id in report_ids:
            report = Report.query.get(report_id)
            
            if report:
                old_status = report.status
                report.status = new_status
                report.updated_at = datetime.utcnow()
                updated_count += 1
                
                # Log the change
                log_audit_action('update', 'report', report.id, 
                               f'Bulk status update from {old_status} to {new_status}')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} reports',
            'updated_count': updated_count
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in bulk status update: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bulk_bp.route('/api/delete', methods=['POST'])
@login_required
@role_required(['Admin'])
def bulk_delete():
    """Delete multiple reports"""
    try:
        report_ids = request.json.get('report_ids', [])
        
        if not report_ids:
            return jsonify({'error': 'No reports selected'}), 400
        
        deleted_count = 0
        
        for report_id in report_ids:
            report = Report.query.get(report_id)
            
            if report:
                # Archive before deletion if needed
                if request.json.get('archive_before_delete', True):
                    archive_report(report)
                
                # Delete associated SAT report data
                if report.type == 'SAT':
                    sat_report = SATReport.query.filter_by(report_id=report.id).first()
                    if sat_report:
                        db.session.delete(sat_report)
                
                # Log the deletion
                log_audit_action('delete', 'report', report.id, 
                               f'Bulk deletion of report {report.document_title}')
                
                db.session.delete(report)
                deleted_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} reports',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in bulk delete: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bulk_bp.route('/api/archive', methods=['POST'])
@login_required
@role_required(['Admin', 'Automation Manager'])
def bulk_archive():
    """Archive multiple reports"""
    try:
        data = request.json
        report_ids = data.get('report_ids', [])
        retention_days = data.get('retention_days', 365)
        
        if not report_ids:
            return jsonify({'error': 'No reports selected'}), 400
        
        archived_count = 0
        
        for report_id in report_ids:
            report = Report.query.get(report_id)
            
            if report:
                archive = archive_report(report, retention_days)
                if archive:
                    archived_count += 1
                    
                    # Log the archival
                    log_audit_action('archive', 'report', report.id,
                                   f'Archived for {retention_days} days')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Archived {archived_count} reports',
            'archived_count': archived_count
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in bulk archive: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bulk_bp.route('/api/assign', methods=['POST'])
@login_required
@role_required(['Admin', 'Automation Manager'])
def bulk_assign():
    """Assign multiple reports to a user"""
    try:
        data = request.json
        report_ids = data.get('report_ids', [])
        new_user_email = data.get('user_email')
        
        if not report_ids or not new_user_email:
            return jsonify({'error': 'Missing required fields'}), 400
        
        assigned_count = 0
        
        for report_id in report_ids:
            report = Report.query.get(report_id)
            
            if report:
                old_user = report.user_email
                report.user_email = new_user_email
                report.updated_at = datetime.utcnow()
                assigned_count += 1
                
                # Log the assignment
                log_audit_action('assign', 'report', report.id,
                               f'Reassigned from {old_user} to {new_user_email}')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Assigned {assigned_count} reports to {new_user_email}',
            'assigned_count': assigned_count
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in bulk assign: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bulk_bp.route('/api/generate-documents', methods=['POST'])
@login_required
@role_required(['Admin', 'Automation Manager'])
def bulk_generate_documents():
    """Generate documents for multiple reports"""
    try:
        report_ids = request.json.get('report_ids', [])
        document_type = request.json.get('document_type', 'both')  # word, pdf, or both
        
        if not report_ids:
            return jsonify({'error': 'No reports selected'}), 400
        
        generated_count = 0
        errors = []
        
        for report_id in report_ids:
            try:
                report = Report.query.get(report_id)
                
                if report:
                    # Import generation function
                    from utils import generate_sat_document
                    
                    # Generate document
                    if document_type in ['word', 'both']:
                        result = generate_sat_document(report.id, format='docx')
                        if result['success']:
                            generated_count += 1
                    
                    if document_type in ['pdf', 'both']:
                        result = generate_sat_document(report.id, format='pdf')
                        if result['success']:
                            generated_count += 1
                    
                    # Log the generation
                    log_audit_action('generate', 'report', report.id,
                                   f'Bulk document generation ({document_type})')
                    
            except Exception as e:
                errors.append(f"Error generating for {report_id}: {str(e)}")
        
        return jsonify({
            'success': True,
            'message': f'Generated documents for {generated_count} reports',
            'generated_count': generated_count,
            'errors': errors if errors else None
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in bulk document generation: {e}")
        return jsonify({'error': str(e)}), 500

def archive_report(report, retention_days=365):
    """Archive a single report"""
    try:
        # Prepare archive data
        archive_data = {
            'report': {
                'id': report.id,
                'type': report.type,
                'document_title': report.document_title,
                'project_reference': report.project_reference,
                'client_name': report.client_name,
                'status': report.status,
                'revision': report.revision,
                'created_at': report.created_at.isoformat(),
                'updated_at': report.updated_at.isoformat() if report.updated_at else None,
                'user_email': report.user_email
            }
        }
        
        # Add SAT report data if applicable
        if report.type == 'SAT':
            sat_report = SATReport.query.filter_by(report_id=report.id).first()
            if sat_report:
                archive_data['sat_data'] = sat_report.data_json
        
        # Create archive record
        archive = ReportArchive(
            original_report_id=report.id,
            report_type=report.type,
            document_title=report.document_title,
            project_reference=report.project_reference,
            client_name=report.client_name,
            archived_data=json.dumps(archive_data),
            archived_by=current_user.email,
            retention_until=datetime.utcnow() + timedelta(days=retention_days)
        )
        
        db.session.add(archive)
        return archive
        
    except Exception as e:
        current_app.logger.error(f"Error archiving report: {e}")
        return None

def log_audit_action(action, entity_type, entity_id, details):
    """Log an audit action"""
    try:
        audit_log = AuditLog(
            user_email=current_user.email,
            user_name=current_user.full_name,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:200]
        )
        
        db.session.add(audit_log)
        
    except Exception as e:
        current_app.logger.error(f"Error logging audit action: {e}")