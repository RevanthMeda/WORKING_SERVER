import json
import os
from html import escape
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import current_app


def generate_email_content(
    report_data: Dict[str, Any],
    audience: str = "approver",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Generate rich email content for report notifications using the configured AI model (OpenRouter or HuggingFace).

    Args:
        report_data: Dictionary containing the report context.
        audience: The intended reader (e.g. 'approver', 'submitter').
        extra: Additional contextual information such as URLs or approval stage metadata.

    Returns:
        dict with keys: subject, body, and optional preheader.
    """
    extra = extra or {}
    provider = None
    try:
        provider, model = _ensure_model()
        prompt, generation_config = construct_prompt(report_data, audience, extra)

        if provider == "openrouter":
            response = _generate_with_openrouter(model, prompt, generation_config)
        elif provider == "huggingface":
            response = _generate_with_hf(model, prompt, generation_config)
        else:
            raise RuntimeError(f"AI provider '{provider}' is not supported for email generation.")

        plan = _parse_email_plan(response)
        if not plan:
            raise ValueError("AI response did not include valid JSON payload.")

        email_package = _compose_email(plan, report_data, audience, extra)
        return email_package
    except Exception as exc:
        current_app.logger.error(f"Error generating email content: {exc}", exc_info=True)

        # If primary failed and Hugging Face is available, try it as a secondary provider
        try:
            if provider != "huggingface" and _has_hf_token():
                hf_model = {
                    "token": current_app.config.get("HF_API_TOKEN") or os.environ.get("HF_API_TOKEN"),
                    "model_id": current_app.config.get("HF_MODEL") or "HuggingFaceH4/zephyr-7b-beta",
                    "api_url": (current_app.config.get("HF_API_URL") or "https://api-inference.huggingface.co/models").rstrip("/"),
                }
                prompt, generation_config = construct_prompt(report_data, audience, extra)
                response = _generate_with_hf(hf_model, prompt, generation_config)
                plan = _parse_email_plan(response)
                if plan:
                    return _compose_email(plan, report_data, audience, extra)
        except Exception as hf_exc:
            current_app.logger.error(f"Secondary HuggingFace attempt failed: {hf_exc}", exc_info=True)

        return _fallback_email(report_data, audience, extra)


def construct_prompt(
    report_data: Dict[str, Any],
    audience: str,
    extra: Dict[str, Any],
) -> tuple[str, Dict[str, Any]]:
    """Construct a detailed prompt for the AI model."""
    audience_key = (audience or "approver").strip().lower()
    audience_key = audience_key if audience_key in {"approver", "submitter"} else "approver"

    stage = extra.get("stage")
    approver_title = extra.get("approver_title")

    summary_payload = _build_context_snapshot(report_data)
    if stage:
        # Provide role context without exposing stage numbering to keep copy professional
        summary_payload["approval_stage"] = {
            "role": approver_title or "Approver",
        }

    prompt_lines: List[str] = [
        "You are a communications specialist for an industrial automation company.",
        "Craft a polished HTML email that is persuasive yet professional.",
        "Use UK English tone and keep the wording focused on action and clarity.",
        "Always return JSON only with the schema described below.",
        "",
        "Return a JSON object with these keys:",
        "- subject: (string, <= 90 characters)",
        "- preheader: (string, short teaser text <= 110 characters)",
        "- intro: (string, warm greeting/introduction in 2 sentences max)",
        "- synopsis: (string, 2-3 sentence summary describing the report purpose and backdrop)",
        "- highlights: (array of 3 concise bullet strings spotlighting progress or insights)",
        "- call_to_action: (string, the phrase to display on the main action button)",
        "- closing: (string, friendly closing sentence acknowledging next steps)",
    ]

    if audience_key == "approver":
        prompt_lines.extend(
            [
                "",
                "Audience context:",
                "- The recipient is an approval stakeholder (e.g. Automation Manager or Project Manager).",
                "- Reinforce why their approval matters by referencing the value to operations or schedule.",
                "- Mention the approval stage number when provided.",
                '- Keep the call to action directive, e.g. "Review & Approve Report".',
            ]
        )
    else:
        prompt_lines.extend(
            [
                "",
                "Audience context:",
                "- The recipient is the original report submitter.",
                "- Congratulate the progress, highlight report coverage, and emphasise their next action.",
                "- Encourage them to review status or update the submission if required.",
            ]
        )

    prompt_lines.extend(
        [
            "",
            "Use the following structured report snapshot as factual grounding:",
            json.dumps(summary_payload, indent=2),
            "",
            "Do not add commentary outside of the JSON object.",
        ]
    )

    generation_config = {
        "temperature": 0.55,
        "top_p": 0.9,
        "max_tokens": 600,
    }

    return "\n".join(prompt_lines), generation_config


def _current_provider() -> str:
    provider = (current_app.config.get("AI_PROVIDER") or "openrouter").strip().lower()
    if provider in ("", "auto", "default"):
        if current_app.config.get("OPENROUTER_API_KEY"):
            return "openrouter"
        if current_app.config.get("HF_API_TOKEN"):
            return "huggingface"
        return "none"
    return provider


def _has_hf_token() -> bool:
    return bool(current_app.config.get("HF_API_TOKEN") or os.environ.get("HF_API_TOKEN"))


def _ensure_model() -> Tuple[str, Any]:
    provider = _current_provider()
    if provider == "openrouter":
        token = current_app.config.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEY")
        model_id = current_app.config.get("OPENROUTER_MODEL") or "qwen/qwen3-coder:free"
        if not token:
            raise RuntimeError("OPENROUTER_API_KEY not configured.")
        return "openrouter", {"token": token, "model_id": model_id}

    if provider == "huggingface":
        token = current_app.config.get("HF_API_TOKEN") or os.environ.get("HF_API_TOKEN")
        model_id = current_app.config.get("HF_MODEL") or "HuggingFaceH4/zephyr-7b-beta"
        api_url = (current_app.config.get("HF_API_URL") or "https://api-inference.huggingface.co/models").rstrip("/")
        if not token:
            raise RuntimeError("HF_API_TOKEN not configured.")
        return "huggingface", {"token": token, "model_id": model_id, "api_url": api_url}
    raise RuntimeError(f"AI provider '{provider}' is not configured.")


def _generate_with_openrouter(model_cfg: Dict[str, str], prompt: str, generation_config: Dict[str, Any]) -> Dict[str, Any]:
    token = (model_cfg.get("token") or "").strip()
    model_id = model_cfg.get("model_id")
    if not token or not model_id:
        raise RuntimeError("OpenRouter credentials are missing.")

    try:
        current_app.logger.info(f"OpenRouter call: model={model_id}, key_len={len(token)}")
    except Exception:
        pass

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": generation_config.get("temperature", 0.55),
        "top_p": generation_config.get("top_p", 0.9),
        "max_tokens": generation_config.get("max_tokens", 600),
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text}")
    return response.json()


def _generate_with_hf(model_cfg: Dict[str, str], prompt: str, generation_config: Dict[str, Any]) -> str:
    token = model_cfg.get("token")
    model_id = model_cfg.get("model_id")
    api_url = model_cfg.get("api_url") or "https://api-inference.huggingface.co/models"
    if not token or not model_id:
        raise RuntimeError("HuggingFace credentials are missing.")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": generation_config.get("max_tokens", 600),
            "temperature": generation_config.get("temperature", 0.55),
            "top_p": generation_config.get("top_p", 0.9),
        },
        "options": {"wait_for_model": True},
    }

    response = requests.post(f"{api_url}/{model_id}", headers=headers, json=payload, timeout=30)
    if response.status_code >= 400:
        raise RuntimeError(f"HuggingFace error {response.status_code}: {response.text}")

    data = response.json()
    text = _extract_hf_text(data)
    if not text:
        raise RuntimeError("HuggingFace response was empty.")
    return text.strip()


def _parse_email_plan(response: Any) -> Optional[Dict[str, Any]]:
    text = _extract_text(response)
    if not text:
        return None
    json_payload = _load_json_block(text)
    if isinstance(json_payload, dict):
        return json_payload
    return None


def _extract_text(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()

    # OpenRouter JSON response
    if isinstance(response, dict) and response.get("choices"):
        try:
            content = response["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content.strip()
        except Exception:
            pass

    try:
        text = getattr(response, "text", None)
    except Exception:
        text = None
    if text:
        try:
            return text.strip()
        except Exception:
            pass

    candidates = getattr(response, "candidates", []) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            continue
        fragments: List[str] = []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                fragments.append(part_text)
            elif isinstance(part, str):
                fragments.append(part)
        if fragments:
            return "".join(fragments).strip()
    return ""


def _extract_hf_text(data: Any) -> str:
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and first.get("generated_text"):
            return str(first.get("generated_text", "")).strip()
        if isinstance(first, str):
            return first.strip()

    if isinstance(data, dict):
        if data.get("generated_text"):
            return str(data.get("generated_text", "")).strip()
        # text-generation-inference style
        if data.get("choices") and isinstance(data["choices"], list):
            maybe = data["choices"][0]
            if isinstance(maybe, dict):
                return str(maybe.get("text", "")).strip()

    return ""


def _load_json_block(text: str) -> Optional[Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.lstrip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def _compose_email(
    plan: Dict[str, Any],
    report_data: Dict[str, Any],
    audience: str,
    extra: Dict[str, Any],
) -> Dict[str, str]:
    document_title = (
        report_data.get("DOCUMENT_TITLE")
        or report_data.get("document_title")
        or report_data.get("DOCUMENT_REFERENCE")
        or "SAT Report"
    )

    if (audience or "").strip().lower() == "approver":
        fallback_subject = f"Approval requested: {document_title}"
        if extra.get("approver_title"):
            fallback_subject = f"{extra.get('approver_title')}: {document_title} approval"
    else:
        fallback_subject = f"{document_title} - Update"
    subject = plan.get("subject") or fallback_subject
    preheader = plan.get("preheader") or plan.get("intro") or ""
    intro = plan.get("intro") or ""
    synopsis = plan.get("synopsis") or ""
    highlights = plan.get("highlights") or []
    call_to_action = plan.get("call_to_action") or "Review Details"
    closing = plan.get("closing") or "Thank you for your continued support."

    # Personalised greeting
    greeting_name = ""
    if (audience or "").lower().strip() == "approver":
        greeting_name = extra.get("approver_name") or extra.get("approver_title") or ""
    else:
        greeting_name = extra.get("submitter_name") or extra.get("prepared_by") or report_data.get("PREPARED_BY") or report_data.get("prepared_by") or ""
    def _looks_like_greeting(text: str) -> bool:
        if not text:
            return False
        prefix = text.strip().lower()
        return prefix.startswith("dear ")
    if greeting_name and not _looks_like_greeting(intro):
        intro = f"Dear {greeting_name},\n{intro}".strip()

    author_name = extra.get("prepared_by") or report_data.get("PREPARED_BY") or report_data.get("prepared_by") or ""

    stage_label = _format_stage_label(extra)
    meta = {
        "document_title": document_title,
        "stage_label": stage_label,
        "audience": audience,
        "preheader": preheader,
        "intro": intro,
        "synopsis": synopsis,
        "highlights": highlights if isinstance(highlights, list) else [str(highlights)],
        "call_to_action": call_to_action,
        "closing": closing,
        "approval_url": extra.get("approval_url"),
        "status_url": extra.get("status_url"),
        "edit_url": extra.get("edit_url"),
        "author_line": f"Prepared by {author_name}" if author_name else "",
    }

    body_html = _render_email_html(meta)
    return {"subject": subject.strip(), "body": body_html.strip(), "preheader": preheader.strip()}


def _render_email_html(context: Dict[str, Any]) -> str:
    def _render_paragraph_block(value: str) -> str:
        if not value:
            return ""
        paragraphs = [line.strip() for line in value.splitlines() if line.strip()]
        if not paragraphs:
            return ""
        return "".join(
            f'<p style="margin:0 0 12px 0;color:#1f2a44;line-height:1.45;font-size:15px;">{escape(paragraph)}</p>'
            for paragraph in paragraphs
        )

    highlights_html = ""
    highlights = [item for item in context.get("highlights", []) if isinstance(item, str) and item.strip()]
    if highlights:
        highlight_items = "".join(
            f'<li style="margin:0 0 8px 0;">{escape(item.strip())}</li>' for item in highlights[:5]
        )
        highlights_html = (
            '<ul style="padding-left:18px;margin:0 0 16px 0;color:#1f2a44;line-height:1.45;font-size:15px;">'
            f"{highlight_items}"
            "</ul>"
        )

    primary_cta_url = context.get("approval_url") if context.get("audience") == "approver" else context.get("edit_url")
    if not primary_cta_url:
        primary_cta_url = context.get("status_url")

    button_html = ""
    if primary_cta_url:
        button_html = (
            f'<a href="{escape(primary_cta_url)}" '
            'style="display:inline-block;padding:12px 28px;margin:12px 0 0 0;'
            'background:#0b5fff;color:#ffffff;text-decoration:none;border-radius:6px;'
            'font-weight:600;font-size:15px;">'
            f"{escape(context.get('call_to_action') or 'Review Report')}"
            "</a>"
        )

    secondary_links: List[str] = []
    status_url = context.get("status_url")
    if status_url and status_url != primary_cta_url:
        secondary_links.append(
            f'<a href="{escape(status_url)}" style="color:#0b5fff;text-decoration:none;font-weight:500;">View current status</a>'
        )

    if context.get("audience") == "submitter" and context.get("edit_url") and context.get("edit_url") != primary_cta_url:
        secondary_links.append(
            f'<a href="{escape(context["edit_url"])}" style="color:#0b5fff;text-decoration:none;font-weight:500;">Update submission</a>'
        )

    secondary_html = ""
    if secondary_links:
        secondary_html = (
            '<p style="margin:16px 0 0 0;color:#1f2a44;font-size:14px;">'
            + " | ".join(secondary_links)
            + "</p>"
        )

    author_html = ""
    if context.get("author_line"):
        author_html = _render_paragraph_block(context["author_line"])

    stage_badge = ""
    if context.get("stage_label"):
        stage_badge = (
            '<span style="display:inline-block;padding:6px 12px;border-radius:999px;'
            'background:#e8f1ff;color:#0b5fff;font-size:12px;font-weight:600;margin-bottom:16px;">'
            f"{escape(context['stage_label'])}"
            "</span>"
        )

    return f"""<html>
  <body style="margin:0;padding:0;background-color:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;">
    <span style="display:none!important;color:#f4f6fb;font-size:1px;line-height:1px;">{escape(context.get('preheader') or '')}</span>
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:640px;margin:0 auto;padding:32px 16px;">
      <tr>
        <td>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;box-shadow:0 14px 32px rgba(15,34,58,0.12);padding:32px;">
            <tr>
              <td>
                <h1 style="margin:0 0 12px 0;color:#0b1b3a;font-size:24px;line-height:1.25;font-weight:700;">{escape(context.get('document_title') or 'Report Update')}</h1>
                {stage_badge}
                {_render_paragraph_block(context.get('intro') or '')}
                {_render_paragraph_block(context.get('synopsis') or '')}
                {highlights_html}
                {button_html}
                {secondary_html}
                {author_html}
                <p style="margin:24px 0 0 0;color:#1f2a44;line-height:1.45;font-size:15px;">{escape(context.get('closing') or '')}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="text-align:center;padding:18px 0 8px 0;">
          <p style="margin:0;color:#5f6c85;font-size:12px;line-height:1.4;">This message was generated automatically by the Cully Automation reporting platform.</p>
          <p style="margin:4px 0 0;color:#5f6c85;font-size:12px;line-height:1.6;">
            Developed by
            <a href="https://www.linkedin.com/in/revanth-meda-1ab294226/" style="color:#0b5fff;text-decoration:none;font-weight:600;" target="_blank">Revanth Meda</a>
            for
            <a href="https://www.cully.ie/" style="color:#0b5fff;text-decoration:none;font-weight:600;" target="_blank">CULLY LTD</a>
          </p>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _format_stage_label(extra: Dict[str, Any]) -> str:
    title = extra.get("approver_title")
    if title:
        return str(title)
    return "Approval request"


def _build_context_snapshot(report_data: Dict[str, Any]) -> Dict[str, Any]:
    snapshot: Dict[str, Any] = {}

    def _first_non_empty(*keys: str) -> str:
        for key in keys:
            value = report_data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    snapshot["document_title"] = _first_non_empty("DOCUMENT_TITLE", "document_title")
    snapshot["project_reference"] = _first_non_empty("PROJECT_REFERENCE", "project_reference")
    snapshot["client_name"] = _first_non_empty("CLIENT_NAME", "client_name")
    snapshot["prepared_by"] = _first_non_empty("PREPARED_BY", "prepared_by")
    snapshot["purpose"] = _first_non_empty("PURPOSE", "purpose")
    snapshot["scope"] = _first_non_empty("SCOPE", "scope")
    snapshot["revision"] = _first_non_empty("REVISION", "revision")

    narrative_fields = [
        "PROJECT_BACKGROUND",
        "SYSTEM_OVERVIEW",
        "TECHNICAL_SUMMARY",
        "KEY_FINDINGS",
        "NOTES",
    ]
    narratives: Dict[str, str] = {}
    for field in narrative_fields:
        value = report_data.get(field)
        if isinstance(value, str) and value.strip():
            narratives[field.lower()] = value.strip()
    if narratives:
        snapshot["narrative_sections"] = narratives

    process_tests = report_data.get("PROCESS_TEST") or report_data.get("PROCESS_TEST_TABLE") or []
    if isinstance(process_tests, list) and process_tests:
        total = len(process_tests)
        passed = sum(
            1 for row in process_tests if str(row.get("Pass/Fail", "")).strip().lower().startswith("pass")
        )
        failed_rows = [
            row.get("Item") or row.get("Test") or row.get("Description") or ""
            for row in process_tests
            if str(row.get("Pass/Fail", "")).strip().lower().startswith("fail")
        ]
        snapshot["process_tests"] = {
            "total": total,
            "passed": passed,
            "failed": max(total - passed, 0),
            "notable_failures": [item for item in failed_rows if item][:3],
        }

    inspections = report_data.get("INSPECTION_CHECKS") or []
    if isinstance(inspections, list) and inspections:
        snapshot["inspection_items"] = len(inspections)

    milestones = report_data.get("PROJECT_MILESTONES") or []
    if isinstance(milestones, list) and milestones:
        snapshot["milestones"] = [
            {k: v for k, v in row.items() if isinstance(v, str) and v.strip()} for row in milestones[:5]
        ]

    return {key: value for key, value in snapshot.items() if value}


def _fallback_email(report_data: Dict[str, Any], audience: str, extra: Dict[str, Any]) -> Dict[str, str]:
    audience_key = (audience or "approver").strip().lower()
    document_title = (
        report_data.get("DOCUMENT_TITLE")
        or report_data.get("document_title")
        or report_data.get("DOCUMENT_REFERENCE")
        or "SAT Report"
    )
    project_ref = report_data.get("PROJECT_REFERENCE") or report_data.get("project_reference") or ""
    client_name = report_data.get("CLIENT_NAME") or report_data.get("client_name") or ""
    purpose = report_data.get("PURPOSE") or report_data.get("purpose") or ""
    scope = report_data.get("SCOPE") or report_data.get("scope") or ""
    approval_url = extra.get("approval_url")
    status_url = extra.get("status_url")
    edit_url = extra.get("edit_url")
    author_name = extra.get("prepared_by") or report_data.get("PREPARED_BY") or report_data.get("prepared_by") or ""

    if audience_key == "approver":
        details = []
        if project_ref:
            details.append(f"Project reference: {escape(project_ref)}")
        if client_name:
            details.append(f"Client: {escape(client_name)}")
        if purpose:
            details.append(f"Purpose: {escape(purpose)}")
        if scope:
            details.append(f"Scope: {escape(scope)}")

        greeting = ""
        approver_name = extra.get("approver_name") or extra.get("approver_title")
        if approver_name:
            greeting = f"<p>Dear {escape(approver_name)},</p>"
        subject = f"Approval requested: {document_title}"
        html_body = f"""
        <html>
        <body>
            <h1>{escape(document_title)} - Approval Required</h1>
            {greeting if greeting else '<p>A new report is ready for your review.</p>'}
            {'<p>This report was prepared by ' + escape(author_name) + '.</p>' if author_name else ''}
            {''.join(f'<p>{line}</p>' for line in details)}
            {f'<p><a href="{escape(approval_url)}">Open approval workspace</a></p>' if approval_url else ''}
            {f'<p><a href="{escape(status_url)}">View live status</a></p>' if status_url else ''}
        </body>
        </html>
        """
    else:
        greeting = ""
        submitter_name = extra.get("submitter_name") or author_name
        if submitter_name:
            greeting = f"<p>Dear {escape(submitter_name)},</p>"
        subject = f"{document_title} submitted successfully"
        html_body = f"""
        <html>
        <body>
            <h1>Submission received</h1>
            {greeting if greeting else ''}
            <p>Your report <strong>{escape(document_title)}</strong> has been submitted.</p>
            {'<p>Prepared by ' + escape(author_name) + '.</p>' if author_name else ''}
            {f'<p><a href="{escape(status_url)}">Track approval progress</a></p>' if status_url else ''}
            {f'<p><a href="{escape(edit_url)}">Update your submission</a></p>' if edit_url else ''}
            {f'<p>Project reference: {escape(project_ref)}</p>' if project_ref else ''}
            {f'<p>Client: {escape(client_name)}</p>' if client_name else ''}
            {f'<p>Purpose: {escape(purpose)}</p>' if purpose else ''}
            {f'<p>Scope: {escape(scope)}</p>' if scope else ''}
        </body>
        </html>
        """

    return {"subject": subject.strip(), "body": html_body.strip(), "preheader": ""}
