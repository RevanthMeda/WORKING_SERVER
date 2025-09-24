from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Report, ReportVersion, SATReport
import json
import difflib
from datetime import datetime

compare_bp = Blueprint('compare', __name__)

@compare_bp.route('/versions/<report_id>')
@login_required
def version_history(report_id):
    """Show version history for a report"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Check permissions
        if report.user_email != current_user.email and current_user.role != 'Admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get all versions
        versions = ReportVersion.query.filter_by(report_id=report_id)\
                                     .order_by(ReportVersion.created_at.desc())\
                                     .all()
        
        # If no versions exist, create initial version from current state
        if not versions:
            create_version_snapshot(report)
            versions = ReportVersion.query.filter_by(report_id=report_id)\
                                         .order_by(ReportVersion.created_at.desc())\
                                         .all()
        
        return render_template('version_history.html',
                             report=report,
                             versions=versions,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error loading version history: {e}")
        return jsonify({'error': str(e)}), 500

@compare_bp.route('/diff/<report_id>')
@login_required
def compare_versions(report_id):
    """Compare two versions of a report"""
    try:
        version1_id = request.args.get('v1')
        version2_id = request.args.get('v2')
        
        if not version1_id or not version2_id:
            return jsonify({'error': 'Both versions required'}), 400
        
        # Get versions
        v1 = ReportVersion.query.get_or_404(version1_id)
        v2 = ReportVersion.query.get_or_404(version2_id)
        
        # Check permissions
        report = Report.query.get(report_id)
        if report.user_email != current_user.email and current_user.role != 'Admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Parse JSON data
        data1 = json.loads(v1.data_snapshot)
        data2 = json.loads(v2.data_snapshot)
        
        # Generate diff
        diff_results = generate_field_diff(data1, data2)
        
        return render_template('version_diff.html',
                             report=report,
                             version1=v1,
                             version2=v2,
                             diff_results=diff_results,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error comparing versions: {e}")
        return jsonify({'error': str(e)}), 500

@compare_bp.route('/api/diff-data/<report_id>')
@login_required
def get_diff_data(report_id):
    """Get diff data in JSON format for dynamic rendering"""
    try:
        version1_id = request.args.get('v1')
        version2_id = request.args.get('v2')
        
        if not version1_id or not version2_id:
            return jsonify({'error': 'Both versions required'}), 400
        
        v1 = ReportVersion.query.get_or_404(version1_id)
        v2 = ReportVersion.query.get_or_404(version2_id)
        
        data1 = json.loads(v1.data_snapshot)
        data2 = json.loads(v2.data_snapshot)
        
        diff_results = generate_field_diff(data1, data2)
        
        return jsonify({
            'success': True,
            'diff': diff_results,
            'version1': {
                'id': v1.id,
                'version': v1.version_number,
                'created_at': v1.created_at.isoformat(),
                'created_by': v1.created_by
            },
            'version2': {
                'id': v2.id,
                'version': v2.version_number,
                'created_at': v2.created_at.isoformat(),
                'created_by': v2.created_by
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error getting diff data: {e}")
        return jsonify({'error': str(e)}), 500

def create_version_snapshot(report):
    """Create a version snapshot of the current report state"""
    try:
        # Get report data
        if report.type == 'SAT':
            sat_report = SATReport.query.filter_by(report_id=report.id).first()
            if sat_report:
                data_snapshot = sat_report.data_json
            else:
                data_snapshot = json.dumps({})
        else:
            # For other report types
            data_snapshot = json.dumps({
                'document_title': report.document_title,
                'project_reference': report.project_reference,
                'client_name': report.client_name,
                'revision': report.revision
            })
        
        # Create version record
        version = ReportVersion(
            report_id=report.id,
            version_number=report.revision or 'R0',
            created_by=report.user_email,
            change_summary='Initial version',
            data_snapshot=data_snapshot,
            is_current=True
        )
        
        # Mark other versions as not current
        ReportVersion.query.filter_by(report_id=report.id).update({'is_current': False})
        
        db.session.add(version)
        db.session.commit()
        
        return version
    except Exception as e:
        current_app.logger.error(f"Error creating version snapshot: {e}")
        db.session.rollback()
        return None

def generate_field_diff(data1, data2):
    """Generate field-by-field diff between two data snapshots"""
    diff_results = []
    
    # Get context data if available
    context1 = data1.get('context', data1)
    context2 = data2.get('context', data2)
    
    # Get all unique keys from both versions
    all_keys = set(context1.keys()) | set(context2.keys())
    
    for key in sorted(all_keys):
        val1 = context1.get(key, '')
        val2 = context2.get(key, '')
        
        # Convert to strings for comparison
        str1 = str(val1) if val1 else ''
        str2 = str(val2) if val2 else ''
        
        if str1 != str2:
            # Generate line diff
            if '\n' in str1 or '\n' in str2:
                # Multi-line diff
                lines1 = str1.splitlines()
                lines2 = str2.splitlines()
                diff = list(difflib.unified_diff(lines1, lines2, lineterm=''))
            else:
                # Single line diff
                diff = []
                if str1:
                    diff.append(f'- {str1}')
                if str2:
                    diff.append(f'+ {str2}')
            
            diff_results.append({
                'field': key,
                'old_value': str1,
                'new_value': str2,
                'diff': diff,
                'change_type': 'added' if not str1 else 'removed' if not str2 else 'modified'
            })
    
    return diff_results

@compare_bp.route('/api/save-version/<report_id>', methods=['POST'])
@login_required
def save_version(report_id):
    """Save current state as a new version"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Check permissions
        if report.user_email != current_user.email and current_user.role not in ['Admin', 'Automation Manager']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get change summary from request
        change_summary = request.json.get('change_summary', 'Manual save')
        
        # Create version snapshot
        version = create_version_snapshot(report)
        if version:
            version.change_summary = change_summary
            db.session.commit()
            
            return jsonify({
                'success': True,
                'version': {
                    'id': version.id,
                    'version_number': version.version_number,
                    'created_at': version.created_at.isoformat()
                }
            })
        else:
            return jsonify({'error': 'Failed to create version'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Error saving version: {e}")
        return jsonify({'error': str(e)}), 500