from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required

from services.bot_assistant import (
    start_conversation,
    process_user_message,
    ingest_upload,
    resolve_report_download_url,
)
from services.ai_agent import (
    start_ai_conversation,
    process_ai_message,
    reset_ai_conversation,
    get_ai_capabilities,
    get_ai_context,
)

bot_bp = Blueprint('bot', __name__, url_prefix='/bot')


def _ensure_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, '')]
    if value in (None, ''):
        return []
    return [str(value)]


def _initialise_payload(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base: Dict[str, Any] = dict(payload or {})
    base['messages'] = _ensure_list(base.get('messages'))
    base['warnings'] = _ensure_list(base.get('warnings'))
    base['errors'] = _ensure_list(base.get('errors'))
    return base


def _merge_agent_payload(
    assistant_payload: Optional[Dict[str, Any]],
    agent_payload: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    payload = _initialise_payload(assistant_payload)

    if agent_payload:
        payload['agent'] = agent_payload

        agent_message = agent_payload.get('message')
        if agent_message:
            payload['messages'].append(str(agent_message))

        suggestions = agent_payload.get('suggestions') or []
        if suggestions:
            existing = payload.get('suggestions')
            if isinstance(existing, list):
                merged = existing[:]
            elif existing:
                merged = [existing]
            else:
                merged = []
            for suggestion in suggestions:
                if suggestion and suggestion not in merged:
                    merged.append(suggestion)
            payload['suggestions'] = merged

        actions = agent_payload.get('actions')
        if actions:
            payload['agent_actions'] = actions

        next_steps = agent_payload.get('next_steps')
        if next_steps:
            payload['agent_next_steps'] = next_steps

        reasoning = agent_payload.get('reasoning')
        if reasoning:
            payload['agent_reasoning'] = reasoning

        confidence = agent_payload.get('confidence')
        if confidence is not None:
            payload['agent_confidence'] = confidence

        metadata = agent_payload.get('metadata')
        if metadata:
            payload['agent_metadata'] = metadata

    return payload


@bot_bp.route('/start', methods=['POST'])
@login_required
def bot_start():
    try:
        assistant_payload = start_conversation()
    except Exception:  # noqa: BLE001 - propagate friendly error to client
        current_app.logger.exception('Failed to start assistant conversation.')
        return jsonify({'errors': ['Failed to initialise the assistant.']}), 500

    try:
        agent_payload = start_ai_conversation()
    except Exception:  # noqa: BLE001 - agent is optional fallback
        current_app.logger.exception('Failed to start AI agent conversation.')
        agent_payload = None

    combined = _merge_agent_payload(assistant_payload, agent_payload)
    if agent_payload is None:
        combined.setdefault('warnings', []).append(
            'Advanced AI agent is temporarily unavailable; continuing with fallback assistant.'
        )
    return jsonify(combined)


@bot_bp.route('/reset', methods=['POST'])
@login_required
def bot_reset():
    try:
        assistant_payload = start_conversation()
    except Exception:  # noqa: BLE001 - propagate friendly error to client
        current_app.logger.exception('Failed to reset assistant conversation.')
        return jsonify({'errors': ['Failed to reset the assistant.']}), 500

    assistant_payload.setdefault('messages', []).append("Conversation reset. Let's start fresh.")

    try:
        agent_payload = reset_ai_conversation()
    except Exception:  # noqa: BLE001 - agent is optional fallback
        current_app.logger.exception('Failed to reset AI agent conversation.')
        agent_payload = None

    combined = _merge_agent_payload(assistant_payload, agent_payload)
    if agent_payload is None:
        combined.setdefault('warnings', []).append(
            'Advanced AI agent is temporarily unavailable after reset; continuing with fallback assistant.'
        )
    return jsonify(combined)


@bot_bp.route('/message', methods=['POST'])
@login_required
def bot_message():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    mode = (data.get('mode') or 'default').strip().lower() or 'default'

    if not message:
        return jsonify({'errors': ['Message cannot be empty.']}), 400

    assistant_payload: Optional[Dict[str, Any]] = None
    assistant_error: Optional[str] = None
    try:
        assistant_payload = process_user_message(message, mode=mode)
    except Exception:  # noqa: BLE001 - degrade gracefully
        assistant_error = 'Failed to process message with workflow assistant.'
        current_app.logger.exception('Error while processing user message with workflow assistant.')

    context_updates: Dict[str, Any] = {}
    if assistant_payload:
        collected = assistant_payload.get('collected')
        if isinstance(collected, dict):
            context_updates['current_report_data'] = collected
        if assistant_payload.get('field'):
            context_updates['next_required_field'] = assistant_payload['field']
        pending_fields = assistant_payload.get('pending_fields')
        if isinstance(pending_fields, list):
            context_updates['pending_fields'] = pending_fields
        if assistant_payload.get('completed'):
            context_updates['current_task'] = 'report_ready'

    if mode and mode != 'default':
        context_updates['interaction_mode'] = mode
    if request.referrer:
        context_updates['page_referrer'] = request.referrer

    agent_payload: Optional[Dict[str, Any]] = None
    try:
        agent_payload = process_ai_message(
            message,
            context_updates=context_updates or None,
        )
    except Exception:  # noqa: BLE001 - degrade gracefully
        current_app.logger.exception('Error while processing message with AI agent.')

    if assistant_payload is None and agent_payload is None:
        return jsonify({'errors': ['Assistant is unavailable right now. Please try again later.']}), 503

    combined = _merge_agent_payload(assistant_payload, agent_payload)

    if assistant_error:
        combined.setdefault('errors', []).append(assistant_error)

    if not combined['messages']:
        combined['messages'].append("I'm here and ready to help, but I need a bit more detail.")

    return jsonify(combined)


@bot_bp.route('/upload', methods=['POST'])
@login_required
def bot_upload():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided.'}), 400

    messages: List[str] = []
    errors: List[str] = []
    warnings: List[str] = []
    last_payload: Optional[Dict[str, Any]] = None
    file_names: List[str] = []

    for storage in files:
        if storage and storage.filename:
            file_names.append(storage.filename)
        result = ingest_upload(storage)
        last_payload = result
        if 'message' in result:
            messages.append(str(result['message']))
        if 'error' in result:
            errors.append(str(result['error']))
        warnings.extend(str(item) for item in result.get('warnings', []) if item)

    if last_payload is None:
        return jsonify({'error': 'Upload failed.'}), 500

    response: Dict[str, Any] = {
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

    agent_payload: Optional[Dict[str, Any]] = None
    agent_context_updates: Dict[str, Any] = {}
    if isinstance(response.get('collected'), dict):
        agent_context_updates['current_report_data'] = response['collected']
    if response.get('pending_fields'):
        agent_context_updates['pending_fields'] = response['pending_fields']

    summary_parts = [f'Processed {len(files)} file(s).']
    if file_names:
        preview = file_names[:5]
        summary_parts.append(f"Files: {', '.join(preview)}" + ('...' if len(file_names) > 5 else ''))
    if messages:
        summary_parts.extend(messages)
    agent_message = ' '.join(summary_parts)

    try:
        agent_payload = process_ai_message(
            agent_message,
            context_updates=agent_context_updates or None,
        )
    except Exception:  # noqa: BLE001 - degrade gracefully
        current_app.logger.exception('Error while updating AI agent after file upload.')

    combined = _merge_agent_payload(response, agent_payload)
    return jsonify(combined)


@bot_bp.route('/document/<submission_id>', methods=['GET'])
@login_required
def bot_document(submission_id):
    result = resolve_report_download_url(submission_id)
    status = 200 if 'download_url' in result else 404
    return jsonify(result), status


@bot_bp.route('/capabilities', methods=['GET'])
@login_required
def bot_capabilities():
    try:
        capabilities = get_ai_capabilities()
    except Exception:  # noqa: BLE001 - degrade gracefully
        current_app.logger.exception('Failed to fetch AI agent capabilities.')
        return jsonify({'errors': ['Unable to fetch AI agent capabilities.']}), 500
    return jsonify({'capabilities': capabilities})


@bot_bp.route('/context', methods=['GET'])
@login_required
def bot_context():
    try:
        context = get_ai_context()
    except Exception:  # noqa: BLE001 - degrade gracefully
        current_app.logger.exception('Failed to fetch AI agent context.')
        return jsonify({'errors': ['Unable to fetch AI agent context.']}), 500
    return jsonify({'context': context})
