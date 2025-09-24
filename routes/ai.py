from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required

from services.ai_assistant import generate_sat_suggestion, AISuggestionError, ai_is_configured

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
