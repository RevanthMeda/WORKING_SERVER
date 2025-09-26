from docx import Document
from docx.shared import Mm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml
from docx.shared import RGBColor
from flask import current_app

def set_cell_color(cell, color):
    """Set cell background color."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def build_sat_report(context, output_path):
    """Builds the first page of the SAT report with detailed specifications."""
    try:
        doc = Document()

        # --- Document-Wide Settings ---
        section = doc.sections[0]
        section.page_height = Mm(297)
        section.page_width = Mm(210)
        section.top_margin = Mm(25)
        section.bottom_margin = Mm(25)
        section.left_margin = Mm(25)
        section.right_margin = Mm(25)

        # --- Header ---
        header = section.header
        header_table = header.add_table(rows=1, cols=2, width=section.page_width - section.left_margin - section.right_margin)
        logo_cell = header_table.cell(0, 0)
        logo_cell.text = "CULLY\nYOUR PARTNER IN WATER EXCELLENCE."
        tagline_cell = header_table.cell(0, 1)
        p = tagline_cell.paragraphs[0]
        p.text = f"SAT–{context.get('document_reference', '###')}"
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # --- Document Information Table ---
        doc.add_paragraph() # Spacer
        info_table = doc.add_table(rows=5, cols=2, style='Table Grid')
        info_labels = ['Document Title', 'Project reference', 'Date', 'Client Name', 'Revision']
        info_keys = ['document_title', 'project_reference', 'date', 'client_name', 'revision']
        for i, label in enumerate(info_labels):
            cell = info_table.cell(i, 0)
            cell.text = label
            set_cell_color(cell, 'D9EAD3') # Light blue fill
            info_table.cell(i, 1).text = str(context.get(info_keys[i], ''))

        # --- Document Approvals Table ---
        doc.add_paragraph() # Spacer
        approval_table = doc.add_table(rows=4, cols=3, style='Table Grid')
        approval_labels = ['Prepared by', 'Reviewed by', 'Reviewed by', 'Approval (Client)']
        for i, label in enumerate(approval_labels):
            cell = approval_table.cell(i, 0)
            cell.text = label
            set_cell_color(cell, 'D9EAD3')

        # --- Document Version Control Table ---
        doc.add_paragraph() # Spacer
        version_table = doc.add_table(rows=2, cols=3, style='Table Grid')
        version_hdr = version_table.rows[0].cells
        version_hdr[0].text = 'Revision Number'
        version_hdr[1].text = 'Details'
        version_hdr[2].text = 'Date'
        version_table.rows[1].cells[0].text = str(context.get('revision', 'R0'))

        # --- Confidentiality Notice ---
        doc.add_paragraph().add_run('This document contains proprietary and confidential information... WWW.CULLY.IE').italic = True

        # --- Footer ---
        footer = section.footer
        footer_table = footer.add_table(rows=1, cols=2, width=section.page_width - section.left_margin - section.right_margin)
        footer_cell_left = footer_table.cell(0, 0)
        footer_cell_left.text = f"{context.get('document_reference', '')} / {context.get('revision', '')}"
        footer_cell_right = footer_table.cell(0, 1)
        p = footer_cell_right.paragraphs[0]
        p.text = "Page | 1"
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        doc.save(output_path)
        current_app.logger.info(f"Report first page built successfully at {output_path}")
        return True

    except Exception as e:
        current_app.logger.error(f"Error building report: {e}", exc_info=True)
        return False
