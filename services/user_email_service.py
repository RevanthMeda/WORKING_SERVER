"""
AI-powered email service for user account notifications.
Uses the same AI providers as the SAT report email generator (OpenRouter, OpenAI, HuggingFace).
"""
import json
import os
from html import escape
from typing import Any, Dict, Optional, Union
import requests
from flask import current_app


class UserEmailError(Exception):
    """Custom exception for user email generation errors."""
    pass


def generate_user_approval_email(user_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate an AI-written approval email for a newly approved user.
    
    Args:
        user_data: Dictionary containing user information:
            - full_name: User's full name
            - email: User's email address
            - role: Assigned role (Engineer, Admin, PM, Automation Manager)
            - company_name: Optional company name
            - login_url: URL to login page
            
    Returns:
        dict with keys: subject, body (HTML), text (plain text)
    """
    try:
        provider, model_config = _ensure_model()
        prompt = _build_approval_prompt(user_data)
        
        if provider == "openrouter":
            response = _generate_with_openrouter(model_config, prompt)
        elif provider == "openai":
            response = _generate_with_openai(model_config, prompt)
        elif provider == "huggingface":
            response = _generate_with_hf(model_config, prompt)
        else:
            raise UserEmailError(f"AI provider '{provider}' is not supported.")
        
        email_content = _parse_email_response(response)
        if email_content:
            return _compose_approval_email(email_content, user_data)
        
        raise UserEmailError("AI did not return valid email content.")
        
    except Exception as exc:
        current_app.logger.error(f"Error generating approval email: {exc}", exc_info=True)
        return _fallback_approval_email(user_data)


def generate_welcome_email(user_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate a generic welcome email (can be used for manual sending).
    """
    try:
        provider, model_config = _ensure_model()
        prompt = _build_welcome_prompt(user_data)
        
        if provider == "openrouter":
            response = _generate_with_openrouter(model_config, prompt)
        elif provider == "openai":
            response = _generate_with_openai(model_config, prompt)
        elif provider == "huggingface":
            response = _generate_with_hf(model_config, prompt)
        else:
            raise UserEmailError(f"AI provider '{provider}' is not supported.")
        
        email_content = _parse_email_response(response)
        if email_content:
            return _compose_welcome_email(email_content, user_data)
        
        raise UserEmailError("AI did not return valid email content.")
        
    except Exception as exc:
        current_app.logger.error(f"Error generating welcome email: {exc}", exc_info=True)
        return _fallback_welcome_email(user_data)


def _current_provider() -> str:
    """Determine which AI provider to use."""
    provider = (current_app.config.get("AI_PROVIDER") or "openrouter").strip().lower()
    if provider in ("", "auto", "default"):
        if current_app.config.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter"
        if current_app.config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if current_app.config.get("HF_API_TOKEN") or os.environ.get("HF_API_TOKEN"):
            return "huggingface"
        return "none"
    return provider


def _ensure_model():
    """Get the AI model configuration."""
    provider = _current_provider()
    
    if provider == "openrouter":
        token = current_app.config.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        model_id = current_app.config.get("OPENROUTER_MODEL") or "qwen/qwen3-coder:free"
        if not token:
            raise UserEmailError("OPENROUTER_API_KEY not configured.")
        return "openrouter", {"token": token, "model_id": model_id}
    
    if provider == "openai":
        token = current_app.config.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        model_id = current_app.config.get("OPENAI_MODEL") or "gpt-3.5-turbo"
        if not token:
            raise UserEmailError("OPENAI_API_KEY not configured.")
        return "openai", {"token": token, "model_id": model_id}
    
    if provider == "huggingface":
        token = current_app.config.get("HF_API_TOKEN") or os.environ.get("HF_API_TOKEN")
        model_id = current_app.config.get("HF_MODEL") or "HuggingFaceH4/zephyr-7b-beta"
        api_url = (current_app.config.get("HF_API_URL") or "https://api-inference.huggingface.co/models").rstrip("/")
        if not token:
            raise UserEmailError("HF_API_TOKEN not configured.")
        return "huggingface", {"token": token, "model_id": model_id, "api_url": api_url}
    
    raise UserEmailError(f"AI provider '{provider}' is not configured.")


def _build_approval_prompt(user_data: Dict[str, Any]) -> str:
    """Build the prompt for generating an approval email."""
    full_name = user_data.get("full_name", "User")
    role = user_data.get("role", "Engineer")
    company_name = user_data.get("company_name", "Cully Automation")
    
    prompt_lines = [
        "You are a communications specialist for an industrial automation company.",
        "Write a professional and warm approval notification email for a new user account.",
        "Use UK English and keep the tone welcoming but professional.",
        "",
        "Context:",
        f"- User's name: {full_name}",
        f"- Assigned role: {role}",
        f"- Company: {company_name}",
        "",
        "The email should:",
        "1. Welcome the user and confirm their account has been approved",
        "2. Briefly mention their assigned role and what they can do with it",
        "3. Encourage them to log in and start using the system",
        "4. Offer help if they have any questions",
        "",
        "Return a JSON object with these keys:",
        "- subject: (string, <= 60 characters, professional subject line)",
        "- greeting: (string, warm personal greeting using their name)",
        "- body: (string, 2-3 paragraphs of the main message)",
        "- call_to_action: (string, phrase for the login button like 'Login Now')",
        "- closing: (string, friendly sign-off)",
        "",
        "Return ONLY the JSON object, no additional text or markdown."
    ]
    
    return "\n".join(prompt_lines)


def _build_welcome_prompt(user_data: Dict[str, Any]) -> str:
    """Build the prompt for generating a welcome email."""
    full_name = user_data.get("full_name", "User")
    role = user_data.get("role", "User")
    company_name = user_data.get("company_name", "Cully Automation")
    
    prompt_lines = [
        "You are a communications specialist for an industrial automation company.",
        "Write a professional welcome email for an existing user.",
        "Use UK English and keep the tone helpful and professional.",
        "",
        "Context:",
        f"- User's name: {full_name}",
        f"- Role: {role}",
        f"- Company: {company_name}",
        "",
        "The email should:",
        "1. Warmly greet the user",
        "2. Remind them about the SAT Report Generator system",
        "3. Offer assistance if they need help",
        "",
        "Return a JSON object with these keys:",
        "- subject: (string, <= 60 characters)",
        "- greeting: (string, personal greeting)",
        "- body: (string, 1-2 paragraphs)",
        "- call_to_action: (string, button text)",
        "- closing: (string, sign-off)",
        "",
        "Return ONLY the JSON object, no additional text."
    ]
    
    return "\n".join(prompt_lines)


def _generate_with_openrouter(model_cfg: Dict[str, str], prompt: str) -> Any:
    """Generate email content using OpenRouter API."""
    token = model_cfg.get("token", "").strip()
    model_id = model_cfg.get("model_id")
    
    if not token or not model_id:
        raise UserEmailError("OpenRouter credentials are missing.")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 500,
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
    except requests.RequestException as exc:
        raise UserEmailError(f"OpenRouter request failed: {exc}") from exc
    
    if response.status_code >= 400:
        raise UserEmailError(f"OpenRouter error {response.status_code}: {response.text}")
    
    return response.json()


def _generate_with_openai(model_cfg: Dict[str, str], prompt: str) -> Any:
    """Generate email content using OpenAI API."""
    token = model_cfg.get("token", "").strip()
    model_id = model_cfg.get("model_id", "gpt-3.5-turbo")
    
    if not token:
        raise UserEmailError("OpenAI API key is missing.")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": "You are a professional email writer for an industrial automation company."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 500,
    }
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
    except requests.RequestException as exc:
        raise UserEmailError(f"OpenAI request failed: {exc}") from exc
    
    if response.status_code >= 400:
        raise UserEmailError(f"OpenAI error {response.status_code}: {response.text}")
    
    return response.json()


def _generate_with_hf(model_cfg: Dict[str, str], prompt: str) -> str:
    """Generate email content using HuggingFace API."""
    token = model_cfg.get("token")
    model_id = model_cfg.get("model_id")
    api_url = model_cfg.get("api_url", "https://api-inference.huggingface.co/models")
    
    if not token or not model_id:
        raise UserEmailError("HuggingFace credentials are missing.")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 500,
            "temperature": 0.5,
            "top_p": 0.9,
        },
        "options": {"wait_for_model": True},
    }
    
    try:
        response = requests.post(
            f"{api_url}/{model_id}",
            headers=headers,
            json=payload,
            timeout=30
        )
    except requests.RequestException as exc:
        raise UserEmailError(f"HuggingFace request failed: {exc}") from exc
    
    if response.status_code >= 400:
        raise UserEmailError(f"HuggingFace error {response.status_code}: {response.text}")
    
    data = response.json()
    
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and first.get("generated_text"):
            return str(first["generated_text"]).strip()
        if isinstance(first, str):
            return first.strip()
    
    if isinstance(data, dict) and data.get("generated_text"):
        return str(data["generated_text"]).strip()
    
    raise UserEmailError("HuggingFace response was empty.")


def _parse_email_response(response: Any) -> Optional[Dict[str, Any]]:
    """Parse the AI response to extract email content.
    
    Handles multiple response formats:
    - OpenRouter/OpenAI JSON response with choices[0].message.content
    - HuggingFace text responses
    - Raw string responses
    """
    if not response:
        return None
    
    # Extract text content from different response formats
    text = ""
    
    # Handle OpenRouter/OpenAI JSON response
    if isinstance(response, dict):
        if response.get("choices"):
            try:
                text = response["choices"][0]["message"]["content"]
                if isinstance(text, str):
                    text = text.strip()
            except (KeyError, IndexError, TypeError):
                pass
        elif response.get("generated_text"):
            text = str(response["generated_text"]).strip()
    elif isinstance(response, str):
        text = response.strip()
    
    if not text:
        return None
    
    # Clean markdown code blocks
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    
    # Try to parse as JSON
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    
    # Try to find JSON object in the text
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        try:
            result = json.loads(cleaned[start:end])
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass
    
    return None


def _compose_approval_email(content: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, str]:
    """Compose the final approval email from AI-generated content."""
    subject = content.get("subject", "Your Account Has Been Approved")
    greeting = content.get("greeting", f"Dear {user_data.get('full_name', 'User')},")
    body = content.get("body", "Your account has been approved and you can now access the SAT Report Generator system.")
    call_to_action = content.get("call_to_action", "Login Now")
    closing = content.get("closing", "Best regards,\nThe Cully Automation Team")
    
    login_url = user_data.get("login_url", "/login")
    company_name = user_data.get("company_name", "Cully Automation")
    role = user_data.get("role", "User")
    
    html_body = _render_approval_html(
        greeting=greeting,
        body=body,
        call_to_action=call_to_action,
        closing=closing,
        login_url=login_url,
        company_name=company_name,
        role=role
    )
    
    text_body = f"{greeting}\n\n{body}\n\nLogin here: {login_url}\n\n{closing}"
    
    return {
        "subject": subject,
        "body": html_body,
        "text": text_body
    }


def _compose_welcome_email(content: Dict[str, Any], user_data: Dict[str, Any]) -> Dict[str, str]:
    """Compose a welcome email from AI-generated content."""
    subject = content.get("subject", "Welcome to SAT Report Generator")
    greeting = content.get("greeting", f"Hello {user_data.get('full_name', 'there')},")
    body = content.get("body", "We hope you're enjoying using the SAT Report Generator system.")
    call_to_action = content.get("call_to_action", "Go to Dashboard")
    closing = content.get("closing", "Best regards,\nThe Cully Automation Team")
    
    login_url = user_data.get("login_url", "/login")
    company_name = user_data.get("company_name", "Cully Automation")
    
    html_body = _render_welcome_html(
        greeting=greeting,
        body=body,
        call_to_action=call_to_action,
        closing=closing,
        login_url=login_url,
        company_name=company_name
    )
    
    text_body = f"{greeting}\n\n{body}\n\nVisit: {login_url}\n\n{closing}"
    
    return {
        "subject": subject,
        "body": html_body,
        "text": text_body
    }


def _render_approval_html(greeting: str, body: str, call_to_action: str, 
                          closing: str, login_url: str, company_name: str, role: str) -> str:
    """Render the approval email as HTML."""
    body_paragraphs = body.split("\n\n") if "\n\n" in body else [body]
    body_html = "".join(
        f'<p style="margin:0 0 16px 0;color:#1f2a44;line-height:1.6;font-size:15px;">{escape(p.strip())}</p>'
        for p in body_paragraphs if p.strip()
    )
    
    closing_html = closing.replace("\n", "<br>")
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;margin:0 auto;padding:32px 16px;">
        <tr>
            <td>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;box-shadow:0 4px 24px rgba(15,34,58,0.1);overflow:hidden;">
                    <tr>
                        <td style="background:linear-gradient(135deg,#0b5fff 0%,#1e40af 100%);padding:32px;text-align:center;">
                            <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">Account Approved</h1>
                            <p style="margin:8px 0 0 0;color:rgba(255,255,255,0.9);font-size:14px;">Welcome to {escape(company_name)}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <div style="display:inline-block;padding:6px 16px;border-radius:20px;background:#e8f1ff;color:#0b5fff;font-size:13px;font-weight:600;margin-bottom:20px;">
                                Role: {escape(role)}
                            </div>
                            <p style="margin:0 0 20px 0;color:#1f2a44;font-size:16px;font-weight:600;">{escape(greeting)}</p>
                            {body_html}
                            <div style="text-align:center;margin:28px 0;">
                                <a href="{escape(login_url)}" style="display:inline-block;padding:14px 32px;background:#0b5fff;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px;">{escape(call_to_action)}</a>
                            </div>
                            <p style="margin:24px 0 0 0;color:#5f6c85;line-height:1.5;font-size:14px;">{closing_html}</p>
                        </td>
                    </tr>
                </table>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td style="text-align:center;padding:24px 0;">
                            <p style="margin:0;color:#5f6c85;font-size:12px;">This email was sent by {escape(company_name)} SAT Report Generator</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def _render_welcome_html(greeting: str, body: str, call_to_action: str,
                         closing: str, login_url: str, company_name: str) -> str:
    """Render a welcome email as HTML."""
    body_paragraphs = body.split("\n\n") if "\n\n" in body else [body]
    body_html = "".join(
        f'<p style="margin:0 0 16px 0;color:#1f2a44;line-height:1.6;font-size:15px;">{escape(p.strip())}</p>'
        for p in body_paragraphs if p.strip()
    )
    
    closing_html = closing.replace("\n", "<br>")
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;margin:0 auto;padding:32px 16px;">
        <tr>
            <td>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;box-shadow:0 4px 24px rgba(15,34,58,0.1);overflow:hidden;">
                    <tr>
                        <td style="background:linear-gradient(135deg,#10b981 0%,#059669 100%);padding:32px;text-align:center;">
                            <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">Welcome</h1>
                            <p style="margin:8px 0 0 0;color:rgba(255,255,255,0.9);font-size:14px;">{escape(company_name)}</p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <p style="margin:0 0 20px 0;color:#1f2a44;font-size:16px;font-weight:600;">{escape(greeting)}</p>
                            {body_html}
                            <div style="text-align:center;margin:28px 0;">
                                <a href="{escape(login_url)}" style="display:inline-block;padding:14px 32px;background:#10b981;color:#ffffff;text-decoration:none;border-radius:8px;font-weight:600;font-size:15px;">{escape(call_to_action)}</a>
                            </div>
                            <p style="margin:24px 0 0 0;color:#5f6c85;line-height:1.5;font-size:14px;">{closing_html}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def _fallback_approval_email(user_data: Dict[str, Any]) -> Dict[str, str]:
    """Generate a fallback approval email without AI."""
    full_name = user_data.get("full_name", "User")
    role = user_data.get("role", "User")
    login_url = user_data.get("login_url", "/login")
    company_name = user_data.get("company_name", "Cully Automation")
    
    subject = "Your Account Has Been Approved"
    
    greeting = f"Dear {full_name},"
    body = f"We are pleased to inform you that your account has been approved.\n\nYou have been assigned the role of {role}, which gives you access to the SAT Report Generator system. You can now log in and start creating and managing your reports.\n\nIf you have any questions or need assistance, please don't hesitate to reach out to our support team."
    call_to_action = "Login to Your Account"
    closing = "Best regards,\nThe Cully Automation Team"
    
    html_body = _render_approval_html(
        greeting=greeting,
        body=body,
        call_to_action=call_to_action,
        closing=closing,
        login_url=login_url,
        company_name=company_name,
        role=role
    )
    
    text_body = f"{greeting}\n\n{body}\n\nLogin here: {login_url}\n\n{closing}"
    
    return {
        "subject": subject,
        "body": html_body,
        "text": text_body
    }


def _fallback_welcome_email(user_data: Dict[str, Any]) -> Dict[str, str]:
    """Generate a fallback welcome email without AI."""
    full_name = user_data.get("full_name", "User")
    login_url = user_data.get("login_url", "/login")
    company_name = user_data.get("company_name", "Cully Automation")
    
    subject = "Welcome to SAT Report Generator"
    
    greeting = f"Hello {full_name},"
    body = "We hope you're enjoying using the SAT Report Generator system. This powerful tool helps you create comprehensive System Acceptance Testing reports efficiently.\n\nIf you need any assistance or have questions, our team is here to help."
    call_to_action = "Go to Dashboard"
    closing = "Best regards,\nThe Cully Automation Team"
    
    html_body = _render_welcome_html(
        greeting=greeting,
        body=body,
        call_to_action=call_to_action,
        closing=closing,
        login_url=login_url,
        company_name=company_name
    )
    
    text_body = f"{greeting}\n\n{body}\n\nVisit: {login_url}\n\n{closing}"
    
    return {
        "subject": subject,
        "body": html_body,
        "text": text_body
    }
