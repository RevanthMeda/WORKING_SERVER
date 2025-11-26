import json
from html import escape
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from flask import current_app


def generate_email_content(
    report_data: Dict[str, Any],
    audience: str = "approver",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Generate rich email content for report notifications using the configured Gemini model.

    Args:
        report_data: Dictionary containing the report context.
        audience: The intended reader (e.g. 'approver', 'submitter').
        extra: Additional contextual information such as URLs or approval stage metadata.

    Returns:
        dict with keys: subject, body, and optional preheader.
    """
    extra = extra or {}
    try:
        model = _ensure_model()
        prompt, generation_config = construct_prompt(report_data, audience, extra)
        response = model.generate_content(prompt, generation_config=generation_config)
        plan = _parse_email_plan(response)
        if not plan:
            raise ValueError("Gemini response did not include valid JSON payload.")

        email_package = _compose_email(plan, report_data, audience, extra)
        return email_package
    except Exception as exc:
        current_app.logger.error(f"Error generating email content: {exc}", exc_info=True)
        return _fallback_email(report_data, audience, extra)


def construct_prompt(
    report_data: Dict[str, Any],
    audience: str,
    extra: Dict[str, Any],
) -> tuple[str, Any]:
    """Construct a detailed prompt for the Gemini model."""
    audience_key = (audience or "approver").strip().lower()
    audience_key = audience_key if audience_key in {"approver", "submitter"} else "approver"

    stage = extra.get("stage")
    approver_title = extra.get("approver_title")

    summary_payload = _build_context_snapshot(report_data)
    if stage:
        summary_payload["approval_stage"] = {
            "stage": stage,
            "title": approver_title or "Approver",
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

    generation_config = genai.types.GenerationConfig(
        temperature=0.55,
        top_p=0.9,
        max_output_tokens=600,
    )

    return "\n".join(prompt_lines), generation_config


def _ensure_model():
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured.")

    genai.configure(api_key=api_key)
    model_name = current_app.config.get("GEMINI_MODEL", "gemini-2.5-pro") or "gemini-2.5-pro"
    return genai.GenerativeModel(model_name)


def _parse_email_plan(response: Any) -> Optional[Dict[str, Any]]:
    text = _extract_text(response)
    if not text:
        return None
    json_payload = _load_json_block(text)
    if isinstance(json_payload, dict):
        return json_payload
    return None


def _extract_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return text.strip()

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

    subject = plan.get("subject") or f"{document_title} - Update"
    preheader = plan.get("preheader") or plan.get("intro") or ""
    intro = plan.get("intro") or ""
    synopsis = plan.get("synopsis") or ""
    highlights = plan.get("highlights") or []
    call_to_action = plan.get("call_to_action") or "Review Details"
    closing = plan.get("closing") or "Thank you for your continued support."

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
                <p style="margin:24px 0 0 0;color:#1f2a44;line-height:1.45;font-size:15px;">{escape(context.get('closing') or '')}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="text-align:center;padding:18px 0 8px 0;">
          <p style="margin:0;color:#5f6c85;font-size:12px;line-height:1.4;">This message was generated automatically by the Cully Automation reporting platform.</p>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _format_stage_label(extra: Dict[str, Any]) -> str:
    stage = extra.get("stage")
    title = extra.get("approver_title")
    if stage and title:
        return f"Stage {stage} - {title}"
    if stage:
        return f"Approval Stage {stage}"
    if title:
        return str(title)
    return ""


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
    approval_url = extra.get("approval_url")
    status_url = extra.get("status_url")

    if audience_key == "approver":
        subject = f"Approval requested: {document_title}"
        html_body = f"""
        <html>
        <body>
            <h1>{escape(document_title)} - Approval Required</h1>
            <p>A new report is ready for your review.</p>
            {f'<p><a href="{escape(approval_url)}">Open approval workspace</a></p>' if approval_url else ''}
            {f'<p><a href="{escape(status_url)}">View live status</a></p>' if status_url else ''}
        </body>
        </html>
        """
    else:
        subject = f"{document_title} submitted successfully"
        html_body = f"""
        <html>
        <body>
            <h1>Submission received</h1>
            <p>Your report <strong>{escape(document_title)}</strong> has been submitted.</p>
            {f'<p><a href="{escape(status_url)}">Track approval progress</a></p>' if status_url else ''}
        </body>
        </html>
        """

    return {"subject": subject.strip(), "body": html_body.strip(), "preheader": ""}
