from flask import Blueprint, jsonify, request, current_app
import google.generativeai as genai
import os
from flask_login import login_required, current_user

# Import both old and new systems for backward compatibility
from services.bot_assistant import (
    ingest_upload,
    resolve_report_download_url,
    BotConversationState,
)

# Import new AI agent system
from services.ai_agent import (
    start_ai_conversation,
    reset_ai_conversation,
    get_ai_capabilities,
    get_ai_context,
    ai_agent
)

bot_bp = Blueprint('bot', __name__, url_prefix='/bot')


@bot_bp.route('/start', methods=['POST'])
@login_required
def bot_start():
    """Start a new AI-powered conversational session."""
    try:
        # Use new AI agent system
        response = start_ai_conversation()
        
        # Add user context
        response['user'] = {
            'id': current_user.id,
            'name': current_user.full_name,
            'email': current_user.email,
            'role': current_user.role
        }
        
        return jsonify(response)
    except Exception as e:
        # Fallback to basic system if AI agent fails
        from services.bot_assistant import start_conversation
        return jsonify(start_conversation())


@bot_bp.route('/message', methods=['POST'])
@login_required
def bot_message():
    """Process user message with Gemini LLM."""
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    context = data.get('context', {})

    if not message:
        return jsonify({'errors': ['Message cannot be empty.']}), 400

    try:
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'errors': ['GEMINI_API_KEY not configured.']}), 500

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')

        # Construct the prompt
        prompt = f"""
        You are a helpful assistant for the Cully Automation website.
        Your task is to assist users in completing their tasks on the website.
        You have knowledge of the website's structure and functionality.

        Current context:
        - Page URL: {request.referrer}

        User message: "{message}"

        Based on the user's message and the context, provide a helpful response.
        If the user is asking to perform an action, provide the necessary steps or information.
        """

        response = model.generate_content(prompt)

        return jsonify({'messages': [response.text]})

    except Exception as e:
        current_app.logger.error(f"Error in bot_message function: {e}", exc_info=True)
        return jsonify({'errors': ['Failed to communicate with the LLM.']}), 500


@bot_bp.route('/reset', methods=['POST'])
@login_required
def bot_reset():
    """Reset AI conversation."""
    try:
        # Reset AI agent
        response = reset_ai_conversation()
        return jsonify(response)
    except Exception as e:
        # Fallback to basic system
        BotConversationState().reset()
        from services.bot_assistant import start_conversation
        return jsonify(start_conversation())


@bot_bp.route('/capabilities', methods=['GET'])
@login_required
def bot_capabilities():
    """Get AI agent capabilities."""
    try:
        capabilities = get_ai_capabilities()
        return jsonify({
            'capabilities': capabilities,
            'agent_type': 'advanced_ai',
            'version': '2.0'
        })
    except Exception as e:
        return jsonify({
            'capabilities': ['basic_conversation', 'form_filling'],
            'agent_type': 'basic',
            'version': '1.0'
        })


@bot_bp.route('/context', methods=['GET'])
@login_required
def bot_context():
    """Get current AI context."""
    try:
        context = get_ai_context()
        return jsonify(context)
    except Exception as e:
        return jsonify({'error': 'Context not available'}), 500


@bot_bp.route('/upload', methods=['POST'])
@login_required
def bot_upload():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided.'}), 400

    messages = []
    errors = []
    warnings = []
    last_payload = None

    for storage in files:
        result = ingest_upload(storage)
        last_payload = result
        if 'message' in result:
            messages.append(result['message'])
        if 'error' in result:
            errors.append(result['error'])
        warnings.extend(result.get('warnings', []))

    if last_payload is None:
        return jsonify({'error': 'Upload failed.'}), 500

    response = {
        'messages': messages,
        'collected': last_payload.get('collected', {}),
        'completed': last_payload.get('completed'),
        'pending_fields': last_payload.get('pending_fields', []),
    }

    if not last_payload.get('completed', False):
        response['field'] = last_payload.get('field')
        response['question'] = last_payload.get('question')
        if 'help_text' in last_payload:
            response['help_text'] = last_payload['help_text']

    if warnings:
        response['warnings'] = warnings
    if errors:
        response['errors'] = errors

    return jsonify(response)


@bot_bp.route('/document/<submission_id>', methods=['GET'])
@login_required
def bot_document(submission_id):
    result = resolve_report_download_url(submission_id)
    status = 200 if 'download_url' in result else 404
    return jsonify(result), status