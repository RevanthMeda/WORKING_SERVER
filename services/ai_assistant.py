import json
import re
from typing import Dict, Any, List, Optional

import requests
import google.generativeai as genai
from flask import current_app


class AISuggestionError(Exception):
    """Raised when AI suggestion generation fails."""


_ALLOWED_FIELDS = {
    'purpose': 'the Purpose section describing why the SAT report is being produced',
    'scope': 'the Scope section outlining the boundaries of testing to be performed'
}



def _current_provider(app) -> str:
    provider = (app.config.get('AI_PROVIDER') or '').strip().lower()
    if provider in ('', 'auto', 'default'):
        if app.config.get('GEMINI_API_KEY'):
            return 'gemini'
        if app.config.get('OPENAI_API_KEY'):
            return 'openai'
        return 'none'
    return provider


def _ensure_gemini_model(error_cls=RuntimeError):
    app = current_app
    api_key = app.config.get('GEMINI_API_KEY')
    if not api_key:
        raise error_cls('GEMINI_API_KEY is not configured.')
    genai.configure(api_key=api_key)
    model_name = app.config.get('GEMINI_MODEL', 'gemini-2.5-pro') or 'gemini-2.5-pro'
    return genai.GenerativeModel(model_name)


def _gemini_text_from_response(response: Any) -> str:
    try:
        text = getattr(response, 'text', None)
        if text:
            return text.strip()
    except (ValueError, IndexError):
        # If .text accessor fails (e.g., due to safety settings blocking),
        # gracefully fall back to checking candidates directly.
        pass

    candidates = getattr(response, 'candidates', []) or []
    for candidate in candidates:
        content = getattr(candidate, 'content', None)
        if not content or not getattr(content, 'parts', None):
            continue
        fragments: List[str] = []
        for part in getattr(content, 'parts', []):
            part_text = getattr(part, 'text', None)
            if part_text:
                fragments.append(part_text)
            elif isinstance(part, str):
                fragments.append(part)
        if fragments:
            return ''.join(fragments).strip()
    return ''


def _parse_json_from_text(text: str) -> Optional[Any]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith('```'):
        cleaned = re.sub(r'^```(?:json)?', '', cleaned, flags=re.IGNORECASE).strip()
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None

def ai_is_configured(app) -> bool:
    """Return True if AI assistance is configured for the given app."""
    if app.config.get('AI_ENABLED'):
        return True
    if app.config.get('GEMINI_API_KEY'):
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

    provider = _current_provider(app)
    if provider == 'gemini':
        return _generate_with_gemini(field_key, submission_context)
    if provider == 'openai':
        return _generate_with_openai(field_key, submission_context)
    if provider == 'none':
        raise AISuggestionError('AI assistance is not configured.')
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



def _generate_with_gemini(field: str, submission_context: Dict[str, Any]) -> str:
    model = _ensure_gemini_model(AISuggestionError)
    audience_hint = submission_context.get('audience') or 'project stakeholders'
    prompt_sections = [
        'You are assisting with drafting a System Acceptance Testing (SAT) report.',
        'Use crisp professional language suitable for engineering documentation.',
        f"Provide content for {_ALLOWED_FIELDS[field]}.",
        'Keep the response concise (2-4 sentences) and avoid markdown formatting.',
    ]

    context_lines = []
    for key, value in submission_context.items():
        if value:
            context_lines.append(f"- {key.replace('_', ' ').title()}: {value}")

    if context_lines:
        prompt_sections.append('Here is relevant context:')
        prompt_sections.extend(context_lines)

    prompt_sections.append(f'Craft the text addressing {audience_hint}.')
    prompt = '\n'.join(prompt_sections)
    generation_config = genai.types.GenerationConfig(temperature=0.3, max_output_tokens=200)
    response = model.generate_content(prompt, generation_config=generation_config)
    text = _gemini_text_from_response(response)
    if not text:
        raise AISuggestionError('Gemini response was empty.')
    return text.strip()

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
    """Generate contextual response using configured AI provider."""
    app = current_app
    provider = _current_provider(app)

    if provider == 'gemini':
        return _generate_contextual_response_gemini(prompt, context, max_tokens)

    if provider not in ('openai', 'none'):
        # Unsupported provider explicitly set
        raise RuntimeError(f"AI provider '{provider}' is not supported.")

    api_key = app.config.get('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not configured.')

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

    context_info = ''
    if context:
        context_info = '\nContext: {0}'.format(json.dumps(context, indent=2))

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f"{prompt}{context_info}"}
        ],
        'temperature': 0.7,
        'max_tokens': max_tokens
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
        raise AISuggestionError(f"OpenAI API error: {response.status_code}")

    data = response.json()
    return data['choices'][0]['message']['content'].strip()




def _generate_contextual_response_gemini(prompt: str, context: Dict[str, Any], max_tokens: int) -> str:
    model = _ensure_gemini_model(RuntimeError)
    system_prompt = (
        "You are an advanced AI assistant for a SAT (Site Acceptance Testing) report generation system. "
        "Provide helpful, accurate, and contextually relevant responses with practical guidance."
    )

    context_block = json.dumps(context, indent=2) if context else 'None provided'
    full_prompt = (
        f"{system_prompt}\n\n"
        f"User message: {prompt}\n\n"
        f"Context:\n{context_block}\n\n"
        'Respond with clear, professional guidance tailored to industrial automation workflows.'
    )

    generation_config = genai.types.GenerationConfig(temperature=0.7, max_output_tokens=max_tokens)
    response = model.generate_content(full_prompt, generation_config=generation_config)
    text = _gemini_text_from_response(response)
    if not text:
        raise RuntimeError('Gemini response was empty.')
    return text.strip()

def _analyze_intent_with_ai(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze user intent using configured AI provider."""
    app = current_app
    provider = _current_provider(app)

    if provider == 'gemini':
        return _analyze_intent_with_gemini(message, context)

    if provider not in ('openai', 'none'):
        raise RuntimeError(f"AI provider '{provider}' is not supported for intent analysis.")

    api_key = app.config.get('OPENAI_API_KEY')
    if not api_key:
        return _analyze_intent_fallback(message)

    model = app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    system_prompt = """Analyze the user's message and determine their intent. Return a JSON object with:
- intent: primary intent (create_report, get_help, analyze_data, workflow_assistance, knowledge_query, system_operation, collaboration, troubleshooting, general)
- confidence: confidence score (0.0-1.0)
- entities: extracted entities like project names, dates, etc.
- urgency: urgency level (low, medium, high)
- sentiment: sentiment (positive, neutral, negative)"""

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f"Message: {message}\nContext: {json.dumps(context)}"}
        ],
        'temperature': 0.3,
        'max_tokens': 200
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
    except Exception:
        return _analyze_intent_fallback(message)


    try:
        data = response.json()
        result = json.loads(data['choices'][0]['message']['content'])
        return result
    except:
        return _analyze_intent_fallback(message)



def _analyze_intent_with_gemini(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    model = _ensure_gemini_model(RuntimeError)
    prompt = (
        "Analyze the user's request and respond with a JSON object containing the keys "
        "intent, confidence, entities, urgency, and sentiment."
    )
    user_payload = (
        f"Context: {json.dumps(context)}\n"
        f"History: {json.dumps(history_slice)}\n\n"
        'Respond with JSON array only.'
    )
    generation_config = genai.types.GenerationConfig(temperature=0.3, max_output_tokens=220)
    response = model.generate_content(f"{prompt}\n\n{user_payload}", generation_config=generation_config)

    data = _parse_json_from_text(text)
    if not isinstance(data, dict):
        return _analyze_intent_fallback(message)

    intent = data.get('intent') or data.get('primary_intent') or 'general'
    confidence = data.get('confidence', 0.6)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.6

    entities = data.get('entities')
    if not isinstance(entities, dict):
        entities = {}

    urgency = data.get('urgency', 'medium')
    sentiment = data.get('sentiment', 'neutral')

    return {
        'intent': intent,
        'confidence': confidence,
        'entities': entities,
        'urgency': urgency,
        'sentiment': sentiment,
    }


def _generate_ai_suggestions_gemini(context: Dict[str, Any], user_history: List[Dict[str, Any]]) -> List[str]:
    model = _ensure_gemini_model(RuntimeError)
    prompt = ("Based on the user's context and recent history, suggest 4-5 practical next actions. "
              "Return the result as a JSON array of strings.")
    history_slice = user_history[-5:]
    user_payload = (
        f"Context: {json.dumps(context)}\n"
        f"History: {json.dumps(history_slice)}\n\n"
        'Respond with JSON array only.'
    )
    generation_config = genai.types.GenerationConfig(temperature=0.5, max_output_tokens=180)
    response = model.generate_content(f"{prompt}\n\n{user_payload}", generation_config=generation_config)
    text = _gemini_text_from_response(response)

    suggestions = _parse_json_from_text(text)
    if isinstance(suggestions, list):
        return [str(item).strip() for item in suggestions if str(item).strip()]
    return [
        'Create a new SAT report',
        'Analyze your data',
        'Get workflow guidance',
        'Explore system features'
    ]

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
    provider = _current_provider(app)

    if provider == 'gemini':
        return _generate_ai_suggestions_gemini(context, user_history)

    if provider not in ('openai', 'none'):
        raise RuntimeError(f"AI provider '{provider}' is not supported for suggestions.")

    api_key = app.config.get('OPENAI_API_KEY')
    if not api_key:
        return [
            'Create a new SAT report',
            'Analyze your data',
            'Get workflow guidance',
            'Explore system features'
        ]

    model = app.config.get('OPENAI_MODEL', 'gpt-3.5-turbo')

    system_prompt = """Based on the user's context and history, suggest 4-5 relevant actions they might want to take.
Focus on practical, actionable suggestions related to SAT report generation, data analysis, workflow optimization, etc.
Return as a JSON array of strings."""

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f"Context: {json.dumps(context)}\nHistory: {json.dumps(user_history[-5:])}"}
        ],
        'temperature': 0.5,
        'max_tokens': 150
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
            raise Exception('API error')

        data = response.json()
        suggestions = json.loads(data['choices'][0]['message']['content'])
        return suggestions if isinstance(suggestions, list) else []
    except Exception:
        return [
            'Create a new SAT report',
            'Analyze your data',
            'Get workflow guidance',
            'Explore system features'
        ]



