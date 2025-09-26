from docx import Document
from docx.shared import Mm, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls, qn
from docx.oxml import OxmlElement, parse_xml
from docx.shared import RGBColor
from flask import current_app
import os

def set_cell_color(cell, color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def apply_table_styles(table):
    """Applies the user's detailed table styling."""
    for row in table.rows:
        row.height = Pt(25)
        for cell in row.cells:
            cell.paragraphs[0].paragraph_format.space_before = Pt(8)
            cell.paragraphs[0].paragraph_format.space_after = Pt(8)

    widths = (Cm(5.5), Cm(10.5))
    for row in table.rows:
        for idx, width in enumerate(widths):
            if idx < len(row.cells):
                row.cells[idx].width = width

def build_sat_report(context, output_path):
    """Builds the first page of the SAT report with a clean header."""
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
        header.is_linked_to_previous = False
        header.paragraphs[0].text = ""
        
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png')
        if os.path.exists(logo_path):
            p = header.paragraphs[0]
            run = p.add_run()
            run.add_picture(logo_path, width=Cm(8.37), height=Cm(1.74))
        else:
            header.paragraphs[0].text = "Cully Automation"

        # Add a thin horizontal line
        p = header.add_paragraph()
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(3)
        p_border = OxmlElement('w:pBdr')
        bottom_border = OxmlElement('w:bottom')
        bottom_border.set(qn('w:val'), 'single')
        bottom_border.set(qn('w:sz'), '2') # 0.25pt
        p_border.append(bottom_border)
        p._p.get_or_add_pPr().append(p_border)

        # --- Main Body ---
        doc.add_paragraph() # Spacer
        info_table = doc.add_table(rows=5, cols=2, style='Table Grid')
        apply_table_styles(info_table)
        info_labels = ['Document Title', 'Project reference', 'Date', 'Client Name', 'Revision']
        info_keys = ['document_title', 'project_reference', 'date', 'client_name', 'revision']
        for i, label in enumerate(info_labels):
            cell = info_table.cell(i, 0)
            cell.text = label
            set_cell_color(cell, 'E6F3FF') # Light blue fill
            info_table.cell(i, 1).text = str(context.get(info_keys[i], ''))

        # ... (rest of the page)

        doc.save(output_path)
        current_app.logger.info(f"Report first page built successfully at {output_path}")
        return True

    except Exception as e:
        current_app.logger.error(f"Error building report: {e}", exc_info=True)
        return False
