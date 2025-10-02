from __future__ import annotations

import os
from typing import Any, Dict

from docx.oxml.ns import qn
from docx.oxml.parser import OxmlElement
from docxtpl import DocxTemplate
from flask import current_app
from services.sat_tables import build_doc_tables_from_context, migrate_context_tables

_TEMPLATE_FALLBACK = "templates/SAT_Template.docx"
_STRING_KEYS = {
    "DOCUMENT_TITLE",
    "PROJECT_REFERENCE",
    "DOCUMENT_REFERENCE",
    "DATE",
    "CLIENT_NAME",
    "REVISION",
    "REVISION_DETAILS",
    "REVISION_DATE",
    "PREPARED_BY",
    "PREPARER_DATE",
    "REVIEWED_BY_TECH_LEAD",
    "TECH_LEAD_DATE",
    "REVIEWED_BY_PM",
    "PM_DATE",
    "APPROVED_BY_CLIENT",
    "SIG_PREPARED",
    "SIG_REVIEW_TECH",
    "SIG_REVIEW_PM",
    "SIG_APPROVAL_CLIENT",
    "PURPOSE",
    "SCOPE",
}
_LIST_KEYS = {
    "RELATED_DOCUMENTS",
    "PRE_APPROVALS",
    "POST_APPROVALS",
    "PRE_TEST_REQUIREMENTS",
    "KEY_COMPONENTS",
    "IP_RECORDS",
    "SIGNAL_LISTS",
    "ANALOGUE_LISTS",
    "MODBUS_DIGITAL_LISTS",
    "MODBUS_ANALOGUE_LISTS",
    "DATA_VALIDATION",
    "PROCESS_TEST",
    "SCADA_VERIFICATION",
    "TRENDS_TESTING",
    "ALARM_LIST",
    "ALARM_IMAGES",
    "SCADA_IMAGES",
    "TRENDS_IMAGES",
}


def generate_report_docx(context: Dict[str, Any], output_path: str) -> bool:
    """Render the SAT template using docxtpl so original styling is preserved."""
    try:
        template_path = _resolve_template_path()
        tpl = DocxTemplate(template_path)
        tpl.render(context)

        _apply_document_properties(tpl, context)

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        tpl.save(output_path)
        current_app.logger.info("SAT report generated successfully at %s", output_path)
        return True
    except Exception as exc:  # noqa: BLE001 - caller handles error display
        current_app.logger.error("Error generating SAT report DOCX: %s", exc, exc_info=True)
        return False


def _resolve_template_path() -> str:
    candidates = [
        current_app.config.get("TEMPLATE_FILE"),
        os.path.join(current_app.root_path, _TEMPLATE_FALLBACK),
        _TEMPLATE_FALLBACK,
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("SAT template document not found.")


def _build_render_context(context: Dict[str, Any]) -> Dict[str, Any]:
    render_context: Dict[str, Any] = {key: "" for key in _STRING_KEYS}
    render_context.update({key: [] for key in _LIST_KEYS})

    normalized_context = migrate_context_tables(context or {})
    doc_tables = build_doc_tables_from_context(context or {})

    for key, value in normalized_context.items():
        if key in _LIST_KEYS and isinstance(value, list):
            render_context[key] = value
        elif key in _STRING_KEYS:
            render_context[key] = value if value is not None else ""

    for key, value in doc_tables.items():
        render_context[key] = value if value is not None else []

    return render_context


def _apply_document_properties(template: DocxTemplate, context: Dict[str, Any]) -> None:
    title = (context or {}).get("DOCUMENT_TITLE") or ""
    revision = (context or {}).get("REVISION") or ""
    document = template.docx

    if title:
        document.core_properties.subject = title

    revision_text = str(revision).strip()
    display_title = revision_text or title
    if display_title:
        document.core_properties.title = display_title

    if revision_text:
        document.core_properties.version = revision_text
        digits = ''.join(ch for ch in revision_text if ch.isdigit())
        if digits:
            revision_value = int(digits) or 1
            document.core_properties.revision = revision_value

    # create element
    update_fields = OxmlElement("w:updateFields")
    # set attribute to true
    update_fields.set(qn("w:val"), "true")
    # add element to settings
    document.settings.element.append(update_fields)


