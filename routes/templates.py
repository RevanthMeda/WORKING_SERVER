from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, ReportTemplate, Report
from auth import role_required
from werkzeug.utils import secure_filename
import os
import json
import uuid
from datetime import datetime

templates_bp = Blueprint('templates', __name__)

@templates_bp.route('/manager')
@login_required
@role_required(['Admin', 'Engineer', 'Automation Manager'])
def template_manager():
    """Display template management interface"""
    try:
        # Get all templates
        templates = ReportTemplate.query.filter_by(is_active=True).all()
        
        # Calculate usage statistics
        template_data = []
        for template in templates:
            # Calculate usage percentage (relative to most used template)
            max_usage = max([t.usage_count for t in templates]) if templates else 1
            usage_percentage = (template.usage_count / max_usage * 100) if max_usage > 0 else 0
            
            template_data.append({
                'id': template.id,
                'name': template.name,
                'type': template.type,
                'version': template.version,
                'description': template.description,
                'usage_count': template.usage_count,
                'usage_percentage': usage_percentage,
                'created_at': template.created_at,
                'updated_at': template.updated_at,
                'created_by': template.created_by,
                'is_active': template.is_active
            })
        
        return render_template('template_manager.html', 
                             templates=template_data,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error in template manager: {e}")
        flash('Error loading templates', 'error')
        return redirect(url_for('dashboard.home'))

@templates_bp.route('/api/upload-template', methods=['POST'])
@login_required
@role_required(['Admin'])
def upload_template():
    """Upload a new report template"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.docx'):
            return jsonify({'error': 'Only .docx files are allowed'}), 400
        
        # Get form data
        name = request.form.get('name')
        template_type = request.form.get('type')
        description = request.form.get('description', '')
        version = request.form.get('version', '1.0')
        
        # Generate unique filename
        filename = secure_filename(f"{template_type}_{uuid.uuid4().hex[:8]}.docx")
        filepath = os.path.join(current_app.config['UPLOAD_ROOT'], 'templates', filename)
        
        # Ensure templates directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save file
        file.save(filepath)
        
        # Create template record
        template = ReportTemplate(
            name=name,
            type=template_type,
            version=version,
            description=description,
            template_file=filepath,
            created_by=current_user.email,
            is_active=True,
            usage_count=0
        )
        
        db.session.add(template)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Template uploaded successfully'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error uploading template: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/selector')
@login_required
def report_selector():
    """Enhanced report selector with multiple template types"""
    try:
        # Get active templates grouped by type
        templates = ReportTemplate.query.filter_by(is_active=True).all()
        
        templates_by_type = {
            'SAT': [],
            'FDS': [],
            'HDS': [],
            'FAT': [],
            'COMMISSIONING': []
        }
        
        for template in templates:
            if template.type in templates_by_type:
                templates_by_type[template.type].append(template)
        
        # Get user's recent reports
        recent_reports = Report.query.filter_by(user_email=current_user.email)\
                                    .order_by(Report.created_at.desc())\
                                    .limit(5).all()
        
        return render_template('enhanced_report_selector.html',
                             templates_by_type=templates_by_type,
                             recent_reports=recent_reports,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error in report selector: {e}")
        flash('Error loading report selector', 'error')
        return redirect(url_for('dashboard.home'))

@templates_bp.route('/create/<template_type>')
@login_required
def create_report(template_type):
    """Create a new report based on template type"""
    try:
        # For now, only SAT is fully implemented
        if template_type == 'SAT':
            return redirect(url_for('reports.sat_wizard'))
        
        # For other types, show coming soon message
        flash(f'{template_type} reports coming soon!', 'info')
        return redirect(url_for('templates.report_selector'))
        
    except Exception as e:
        current_app.logger.error(f"Error creating report: {e}")
        flash('Error creating report', 'error')
        return redirect(url_for('dashboard.home'))

@templates_bp.route('/api/template/<int:template_id>/activate', methods=['POST'])
@login_required
@role_required(['Admin'])
def activate_template(template_id):
    """Activate or deactivate a template"""
    try:
        template = ReportTemplate.query.get_or_404(template_id)
        template.is_active = not template.is_active
        db.session.commit()
        
        status = 'activated' if template.is_active else 'deactivated'
        return jsonify({'success': True, 'message': f'Template {status} successfully'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error toggling template status: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@templates_bp.route('/api/template/<int:template_id>/stats')
@login_required
def get_template_stats(template_id):
    """Get usage statistics for a template"""
    try:
        template = ReportTemplate.query.get_or_404(template_id)
        
        # Get reports using this template
        reports = Report.query.filter_by(type=template.type).all()
        
        # Calculate statistics
        stats = {
            'total_uses': template.usage_count,
            'last_30_days': 0,  # To be implemented with date filtering
            'by_user': {},
            'by_status': {'DRAFT': 0, 'PENDING': 0, 'APPROVED': 0}
        }
        
        for report in reports:
            # Count by user
            if report.user_email not in stats['by_user']:
                stats['by_user'][report.user_email] = 0
            stats['by_user'][report.user_email] += 1
            
            # Count by status
            if report.status in stats['by_status']:
                stats['by_status'][report.status] += 1
        
        return jsonify(stats), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting template stats: {e}")
        return jsonify({'error': str(e)}), 500