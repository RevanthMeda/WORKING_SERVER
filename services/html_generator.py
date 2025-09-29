from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Tuple

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Inches, Pt
from flask import current_app

_LABEL_FILL = "C1E4F5"
_HEADER_FONT_SIZE = Pt(12)
_BODY_FONT_SIZE = Pt(10.5)
_DEFAULT_FONT = "Calibri"


def generate_report_docx(context: Dict[str, Any], output_path: str) -> bool:
    """Create a SAT report cover sheet using python-docx."""
    try:
        document = Document()
        _configure_document(document)
        _build_header(document)
        document.add_paragraph("")

        _add_document_information(document, context)
        _add_document_approvals(document, context)
        _add_version_control(document, context)
        _add_confidentiality_notice(document)
        _add_footer(document, context)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        document.save(output_path)
        current_app.logger.info("SAT report generated successfully at %s", output_path)
        return True
    except Exception as exc:  # noqa: BLE001 - we log and return False for caller handling
        current_app.logger.error("Error generating SAT report DOCX: %s", exc, exc_info=True)
        return False


def _configure_document(document: Document) -> None:
    section = document.sections[0]
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)

    normal_style = document.styles["Normal"]
    normal_style.font.name = _DEFAULT_FONT
    normal_style.font.size = Pt(11)


def _build_header(document: Document) -> None:
    section = document.sections[0]
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

    logo_path = os.path.join(current_app.root_path, "static", "cully.png")
    if os.path.exists(logo_path):
        run = paragraph.add_run()
        try:
            run.add_picture(logo_path, width=Inches(2.3))
        except Exception as exc:  # noqa: BLE001 - keep generating even if logo fails
            current_app.logger.warning("Unable to embed logo from %s: %s", logo_path, exc)

    tagline = header.add_paragraph("YOUR PARTNER IN WATER EXCELLENCE")
    tagline.alignment = WD_ALIGN_PARAGRAPH.LEFT
    tagline_run = tagline.runs[0]
    tagline_run.font.name = _DEFAULT_FONT
    tagline_run.font.size = Pt(9)
    tagline_run.font.bold = True

    separator = header.add_paragraph()
    separator.paragraph_format.space_before = Pt(6)
    separator.paragraph_format.space_after = Pt(0)
    separator_run = separator.add_run("\u2014" * 20)
    separator_run.font.size = Pt(7)
    separator.alignment = WD_ALIGN_PARAGRAPH.LEFT


def _add_document_information(document: Document, context: Dict[str, Any]) -> None:
    _add_section_heading(document, "Document Information")

    table = document.add_table(rows=0, cols=2)
    table.autofit = False
    table.allow_autofit = False
    table.columns[0].width = Inches(2.3)
    table.columns[1].width = Inches(4.5)

    info_rows: Iterable[Tuple[str, Any]] = (
        ("Document Title", context.get("DOCUMENT_TITLE", "")),
        ("Project reference", context.get("PROJECT_REFERENCE", "")),
        ("Document Reference", context.get("DOCUMENT_REFERENCE", "")),
        ("Date", context.get("DATE", "")),
        ("Prepared for", context.get("CLIENT_NAME", "")),
        ("Revision", context.get("REVISION", "")),
    )

    for label, value in info_rows:
        cells = table.add_row().cells
        _format_label_cell(cells[0], label)
        _write_cell_text(cells[1], value)


def _add_document_approvals(document: Document, context: Dict[str, Any]) -> None:
    _add_section_heading(document, "Document Approvals")

    table = document.add_table(rows=0, cols=4)
    table.autofit = False
    table.allow_autofit = False
    table.columns[0].width = Inches(2.1)
    table.columns[1].width = Inches(2.1)
    table.columns[2].width = Inches(1.8)
    table.columns[3].width = Inches(1.8)

    approvals: Iterable[Tuple[str, Any, Any, Any]] = (
        (
            "Prepared by",
            context.get("PREPARED_BY", ""),
            context.get("SIG_PREPARED", ""),
            context.get("PREPARER_DATE", ""),
        ),
        (
            "Reviewed by",
            context.get("REVIEWED_BY_TECH_LEAD", ""),
            context.get("SIG_REVIEW_TECH", ""),
            context.get("TECH_LEAD_DATE", ""),
        ),
        (
            "Reviewed by",
            context.get("REVIEWED_BY_PM", ""),
            context.get("SIG_REVIEW_PM", ""),
            context.get("PM_DATE", ""),
        ),
        (
            "Approval (Client)",
            context.get("APPROVED_BY_CLIENT", ""),
            context.get("SIG_APPROVAL_CLIENT", ""),
            context.get("CLIENT_APPROVAL_DATE", ""),
        ),
    )

    for label, name, signature, date in approvals:
        cells = table.add_row().cells
        _format_label_cell(cells[0], label)
        _write_cell_text(cells[1], name)
        _write_cell_text(cells[2], signature)
        _write_cell_text(cells[3], date)


def _add_version_control(document: Document, context: Dict[str, Any]) -> None:
    _add_section_heading(document, "Document Version Control")

    table = document.add_table(rows=1, cols=3)
    table.autofit = False
    table.allow_autofit = False
    table.columns[0].width = Inches(2.3)
    table.columns[1].width = Inches(3.0)
    table.columns[2].width = Inches(1.8)

    headers = ("Revision Number", "Details", "Date")
    for idx, header_text in enumerate(headers):
        _format_header_cell(table.rows[0].cells[idx], header_text)

    revision_row = table.add_row().cells
    _write_cell_text(revision_row[0], context.get("REVISION", ""))
    _write_cell_text(revision_row[1], context.get("REVISION_DETAILS", ""))
    _write_cell_text(revision_row[2], context.get("REVISION_DATE", ""))


def _add_confidentiality_notice(document: Document) -> None:
    document.add_paragraph("")
    table = document.add_table(rows=1, cols=2)
    table.autofit = False
    table.allow_autofit = False
    table.columns[0].width = Inches(2.3)
    table.columns[1].width = Inches(4.5)

    _format_label_cell(table.rows[0].cells[0], "Confidentiality Notice")
    notice = (
        "This document contains confidential and proprietary information of Cully. "
        "Unauthorized distribution or reproduction is strictly prohibited."
    )
    _write_cell_text(table.rows[0].cells[1], notice)


def _add_footer(document: Document, context: Dict[str, Any]) -> None:
    section = document.sections[0]
    footer = section.footer
    footer_paragraph = footer.paragraphs[0]
    footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    reference = context.get("DOCUMENT_REFERENCE", "")
    revision = context.get("REVISION", "")
    footer_text = " ".join(filter(None, [reference, revision, "Page 1"]))
    footer_run = footer_paragraph.add_run(footer_text)
    footer_run.font.name = _DEFAULT_FONT
    footer_run.font.size = Pt(9)

    website_paragraph = footer.add_paragraph("WWW.CULLY.IE")
    website_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    website_run = website_paragraph.runs[0]
    website_run.font.name = _DEFAULT_FONT
    website_run.font.size = Pt(9)
    website_run.font.bold = True


def _add_section_heading(document: Document, title: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(12)
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run(title)
    run.font.name = _DEFAULT_FONT
    run.font.size = _HEADER_FONT_SIZE
    run.font.bold = True


def _format_label_cell(cell, text: str) -> None:
    _write_cell_text(cell, text, bold=True)
    _shade_cell(cell, _LABEL_FILL)


def _format_header_cell(cell, text: str) -> None:
    _write_cell_text(cell, text, bold=True)
    _shade_cell(cell, _LABEL_FILL)


def _write_cell_text(cell, value: Any, bold: bool = False) -> None:
    text = "" if value is None else str(value)
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    run.font.name = _DEFAULT_FONT
    run.font.size = _BODY_FONT_SIZE
    run.font.bold = bold


def _shade_cell(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{color}"/>')
    tc_pr.append(shading)
