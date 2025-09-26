from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required

from services.ai_assistant import generate_sat_suggestion, AISuggestionError, ai_is_configured
from services.email_generator import generate_email_content
from models import Report, SATReport
import json

ai_bp = Blueprint('ai', __name__, url_prefix='/ai')


@ai_bp.route('/sat/suggest', methods=['POST'])
@login_required
def sat_suggest():
    """Return an AI-generated suggestion for SAT form fields."""
    if not ai_is_configured(current_app):
        return jsonify({
            'error': 'AI assistance is not configured. Set OPENAI_API_KEY to enable this feature.'
        }), 503

    payload = request.get_json(silent=True) or {}
    field = (payload.get('field') or '').lower()
    context = payload.get('context') or {}

    # Basic guardrails to avoid excessive payload sizes
    if not isinstance(context, dict):
        return jsonify({'error': 'Invalid context supplied.'}), 400
    for key, value in list(context.items()):
        if isinstance(value, str) and len(value) > 2000:
            context[key] = value[:2000]

    try:
        suggestion = generate_sat_suggestion(field, context)
    except AISuggestionError as exc:
        return jsonify({'error': str(exc)}), 400

    return jsonify({'suggestion': suggestion})


@ai_bp.route('/generate-email', methods=['POST'])
@login_required
def generate_email():
    """Generate email content for a report."""
    submission_id = request.json.get('submission_id')
    if not submission_id:
        return jsonify({'error': 'submission_id is required'}), 400

    report = Report.query.get(submission_id)
    if not report:
        return jsonify({'error': 'Report not found'}), 404

    report_data = {}
    if report.type == 'SAT':
        sat_report = SATReport.query.filter_by(report_id=submission_id).first()
        if not sat_report:
            return jsonify({'error': 'SAT Report data not found'}), 404
        report_data = json.loads(sat_report.data_json)
        # The actual data is in the 'context' key
        report_data = report_data.get('context', {})
    else:
        # Handle other report types here in the future
        return jsonify({'error': f'Report type {report.type} not yet supported for email generation'}), 400
    
    # Add top-level report info to the data dict
    report_data['type'] = report.type
    report_data['document_title'] = report.document_title
    report_data['project_reference'] = report.project_reference
    report_data['client_name'] = report.client_name

    email_content = generate_email_content(report_data)

    return jsonify(email_content)
