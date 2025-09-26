from docx import Document
from docx.shared import Mm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from flask import current_app

def add_table(doc, heading, headers, data, keys):
    """Helper function to create a table with a heading."""
    doc.add_heading(heading, level=1)
    table = doc.add_table(rows=1, cols=len(headers), style='Table Grid')
    hdr_cells = table.rows[0].cells
    for i, header_text in enumerate(headers):
        hdr_cells[i].text = header_text
    for item in data:
        row_cells = table.add_row().cells
        for i, key in enumerate(keys):
            row_cells[i].text = str(item.get(key, ''))

def build_sat_report(context, output_path):
    """Builds a complete .docx report programmatically based on a detailed specification."""
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

        # --- Style Definitions ---
        styles = doc.styles
        normal_style = styles['Normal']
        font = normal_style.font # type: ignore
        font.name = 'Calibri'
        font.size = Pt(11)
        p_fmt = normal_style.paragraph_format # type: ignore
        p_fmt.space_before = Pt(0)
        p_fmt.space_after = Pt(6)
        p_fmt.line_spacing = 1.15

        # --- Page 1: Title Page ---
        doc.add_heading(context.get('document_title', 'SAT Report'), level=0).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph('Site Acceptance Test Report').alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(context.get('project_reference', '')).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(f"{context.get('client_name', '')} - {context.get('date', '')}").alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_page_break()

        # --- Revision History ---
        add_table(doc, 'Revision History', ['Revision No.', 'Date', 'Author', 'Description'], context.get('revisions', []), ['revision_no', 'date', 'author', 'description'])

        doc.add_page_break()

        # --- Table of Contents ---
        doc.add_heading('Table of Contents', level=1)
        doc.add_paragraph('[TOC will be generated here]')

        doc.add_page_break()

        # --- Report Sections ---
        for table_spec in context.get('tables', []):
            add_table(doc, table_spec['title'], table_spec['headers'], table_spec['data'], table_spec['keys'])

        # --- Final Page: Approval & Signatures ---
        doc.add_heading('Approval & Signatures', level=1)
        sig_table = doc.add_table(rows=len(context.get('approvers', [])), cols=2)
        for i, approver in enumerate(context.get('approvers', [])):
            sig_table.cell(i, 0).text = approver.get('role', '')
            sig_table.cell(i, 1).text = "Signature: ____________________   Date: __________"

        doc.save(output_path)
        current_app.logger.info(f"Report built successfully at {output_path}")
        return True

    except Exception as e:
        current_app.logger.error(f"Error building report: {e}", exc_info=True)
        return False