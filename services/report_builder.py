from docx import Document
from docx.shared import Mm, Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls, qn
from docx.oxml import OxmlElement, parse_xml
from flask import current_app
import os

def set_cell_color(cell, color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def build_sat_report(context, output_path):
    """Builds the first page of the SAT report with a styled header."""
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
        
        htable = header.add_table(rows=1, cols=2, width=section.page_width - section.left_margin - section.right_margin)
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png')
        if os.path.exists(logo_path):
            logo_cell = htable.cell(0, 0)
            logo_cell.paragraphs[0].clear()
            run = logo_cell.paragraphs[0].add_run()
            run.add_picture(logo_path, width=Inches(2.0))
        else:
            htable.cell(0, 0).text = "Cully Automation"
        
        tagline_cell = htable.cell(0, 1)
        p = tagline_cell.paragraphs[0]
        p.text = f"SAT–{context.get('document_reference', '###')}"
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Add a horizontal line
        p = header.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)
        p_border = OxmlElement('w:pBdr')
        bottom_border = OxmlElement('w:bottom')
        bottom_border.set(qn('w:val'), 'single')
        bottom_border.set(qn('w:sz'), '4') # 0.5 pt
        bottom_border.set(qn('w:space'), '1')
        bottom_border.set(qn('w:color'), 'auto')
        p_border.append(bottom_border)
        p._p.get_or_add_pPr().append(p_border)

        # --- Main Body (empty for now) ---

        doc.save(output_path)
        current_app.logger.info(f"Report header built successfully at {output_path}")
        return True

    except Exception as e:
        current_app.logger.error(f"Error building report header: {e}", exc_info=True)
        return False