import json
from typing import Dict, Any, List, Optional

import requests
from flask import current_app


class AISuggestionError(Exception):
    """Raised when AI suggestion generation fails."""


_ALLOWED_FIELDS = {
    'purpose': 'the Purpose section describing why the SAT report is being produced',
    'scope': 'the Scope section outlining the boundaries of testing to be performed'
}


def ai_is_configured(app) -> bool:
    """Return True if AI assistance is configured for the given app."""
    if app.config.get('AI_ENABLED'):
        return True
    if app.config.get('OPENAI_API_KEY'):
        return True
    return False


def generate_sat_suggestion(field: str, submission_context: Dict[str, Any]) -> str:
    """Generate an AI suggestion for the requested SAT field."""
    field_key = field.lower()
    if field_key not in _ALLOWED_FIELDS:
        raise AISuggestionError(f"Unsupported field '{field}'.")

    app = current_app
    if not ai_is_configured(app):
        raise AISuggestionError('AI assistance is not configured. Set OPENAI_API_KEY or disable the feature.')

    provider = (app.config.get('AI_PROVIDER') or 'openai').lower()
    if provider == 'openai':
        return _generate_with_openai(field_key, submission_context)
    raise AISuggestionError(f"AI provider '{provider}' is not supported.")


def generate_intelligent_response(prompt: str, context: Dict[str, Any] = None, max_tokens: int = 500) -> str:
    """Generate intelligent response using AI for the agent system."""
    app = current_app
    if not ai_is_configured(app):
        return "I'm here to help, but AI services are not configured. I can still assist with basic tasks."

    try:
        return _generate_contextual_response(prompt, context or {}, max_tokens)
    except Exception as e:
        # Fallback to basic response if AI fails
        return "I understand you need assistance. Let me help you with that using my built-in capabilities."


def analyze_user_intent(message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Analyze user intent using AI."""
    app = current_app
    if not ai_is_configured(app):
        return {"intent": "general", "confidence": 0.5, "entities": {}}

    try:
        return _analyze_intent_with_ai(message, context or {})
    except Exception as e:
        # Fallback to rule-based analysis
        return _analyze_intent_fallback(message)


def generate_smart_suggestions(context: Dict[str, Any], user_history: List[Dict[str, Any]] = None) -> List[str]:
    """Generate smart suggestions based on context and user history."""
    app = current_app
    if not ai_is_configured(app):
        return [
            "Create a new SAT report",
            "View existing reports",
            "Get help with the system",
            "Analyze data"
        ]

    try:
        return _generate_ai_suggestions(context, user_history or [])
    except Exception as e:
        # Fallback suggestions
        return [
            "Create a new SAT report",
            "Analyze your data",
            "Get workflow guidance",
            "Explore system features"
        ]


def _generate_with_openai(field: str, submission_context: Dict[str, Any]) -> str:
    app = current_app
    api_key = app.config.get('OPENAI_API_KEY')
    if not api_key:
        raise AISuggestionError('OPENAI_API_KEY is not configured.')

    model = app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')
    audience_hint = submission_context.get('audience') or 'project stakeholders'

    prompt_sections = [
        "You are assisting with drafting a System Acceptance Testing (SAT) report.",
        "Use crisp professional language suitable for engineering documentation.",
        f"Provide content for {_ALLOWED_FIELDS[field]}.",
        "Keep the response concise (2-4 sentences) and avoid markdown formatting.",
    ]

    context_lines = []
    for key, value in submission_context.items():
        if value:
            context_lines.append(f"- {key.replace('_', ' ').title()}: {value}")

    if context_lines:
        prompt_sections.append("Here is relevant context:")
        prompt_sections.extend(context_lines)

    prompt_sections.append(f"Craft the text addressing {audience_hint}.")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are an assistant that helps prepare formal engineering SAT reports."},
            {"role": "user", "content": "\n".join(prompt_sections)}
        ],
        "temperature": 0.3,
        "max_tokens": 200
    }

    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            data=json.dumps(payload),
            timeout=30
        )
    except requests.RequestException as exc:
        raise AISuggestionError(f'Failed to reach OpenAI: {exc}') from exc

    if response.status_code >= 400:
        raise AISuggestionError(f'OpenAI API error: {response.status_code} {response.text}')

    try:
        data = response.json()
        suggestion = data['choices'][0]['message']['content'].strip()
        if not suggestion:
            raise KeyError('empty suggestion')
        return suggestion
    except (KeyError, IndexError, ValueError) as exc:
        raise AISuggestionError('Unexpected response format from OpenAI.') from exc


def _generate_contextual_response(prompt: str, context: Dict[str, Any], max_tokens: int) -> str:
    """Generate contextual response using OpenAI."""
    app = current_app
    api_key = app.config.get('OPENAI_API_KEY')
    model = app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    system_prompt = """You are an advanced AI assistant for a SAT (Site Acceptance Testing) report generation system. 
You have deep expertise in:
- Automation systems (SCADA, PLC, DCS, HMI, IoT)
- Testing methodologies and best practices
- Engineering documentation standards
- Project management and collaboration
- Data analysis and insights

Provide helpful, accurate, and contextually relevant responses. Be professional but friendly.
Focus on practical solutions and actionable advice."""

    context_info = ""
    if context:
        context_info = f"\nContext: {json.dumps(context, indent=2)}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{prompt}{context_info}"}
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens
    }

    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        data=json.dumps(payload),
        timeout=30
    )

    if response.status_code >= 400:
        raise AISuggestionError(f'OpenAI API error: {response.status_code}')

    data = response.json()
    return data['choices'][0]['message']['content'].strip()


def _analyze_intent_with_ai(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze user intent using AI."""
    app = current_app
    api_key = app.config.get('OPENAI_API_KEY')
    model = app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    system_prompt = """Analyze the user's message and determine their intent. Return a JSON object with:
- intent: primary intent (create_report, get_help, analyze_data, workflow_assistance, knowledge_query, system_operation, collaboration, troubleshooting, general)
- confidence: confidence score (0.0-1.0)
- entities: extracted entities like project names, dates, etc.
- urgency: urgency level (low, medium, high)
- sentiment: sentiment (positive, neutral, negative)"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Message: {message}\nContext: {json.dumps(context)}"}
        ],
        "temperature": 0.3,
        "max_tokens": 200
    }

    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        data=json.dumps(payload),
        timeout=15
    )

    if response.status_code >= 400:
        return _analyze_intent_fallback(message)

    try:
        data = response.json()
        result = json.loads(data['choices'][0]['message']['content'])
        return result
    except:
        return _analyze_intent_fallback(message)


def _analyze_intent_fallback(message: str) -> Dict[str, Any]:
    """Fallback intent analysis using simple rules."""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["create", "new", "generate", "make", "start"]):
        intent = "create_report"
        confidence = 0.7
    elif any(word in message_lower for word in ["help", "how", "what", "guide"]):
        intent = "get_help"
        confidence = 0.6
    elif any(word in message_lower for word in ["analyze", "data", "metrics", "insights"]):
        intent = "analyze_data"
        confidence = 0.6
    else:
        intent = "general"
        confidence = 0.5
    
    return {
        "intent": intent,
        "confidence": confidence,
        "entities": {},
        "urgency": "medium",
        "sentiment": "neutral"
    }


def _generate_ai_suggestions(context: Dict[str, Any], user_history: List[Dict[str, Any]]) -> List[str]:
    """Generate AI-powered suggestions."""
    app = current_app
    api_key = app.config.get('OPENAI_API_KEY')
    model = app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    system_prompt = """Based on the user's context and history, suggest 4-5 relevant actions they might want to take.
Focus on practical, actionable suggestions related to SAT report generation, data analysis, workflow optimization, etc.
Return as a JSON array of strings."""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context: {json.dumps(context)}\nHistory: {json.dumps(user_history[-5:])}"}
        ],
        "temperature": 0.5,
        "max_tokens": 150
    }

    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            data=json.dumps(payload),
            timeout=15
        )

        if response.status_code >= 400:
            raise Exception("API error")

        data = response.json()
        suggestions = json.loads(data['choices'][0]['message']['content'])
        return suggestions if isinstance(suggestions, list) else []
    except:
        return [
            "Create a new SAT report",
            "Analyze your data",
            "Get workflow guidance",
            "Explore system features"
        ]
