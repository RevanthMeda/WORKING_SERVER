from docx import Document
from docx.shared import Mm, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import nsdecls, qn
from docx.oxml import OxmlElement, parse_xml
from flask import current_app
import os

def set_cell_color(cell, color):
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)

def build_sat_report(context, output_path):
    """Builds the first page of the SAT report with precise header layout."""
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
        
        # Using a table for precise logo and tagline alignment
        htable = header.add_table(rows=1, cols=2, width=section.page_width - section.left_margin - section.right_margin)
        logo_cell = htable.cell(0, 0)
        logo_cell.paragraphs[0].clear()
        run = logo_cell.paragraphs[0].add_run()
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png')
        if os.path.exists(logo_path):
            run.add_picture(logo_path, width=Cm(8.37), height=Cm(1.74))
        else:
            logo_cell.text = "Cully Automation"
        
        tagline_cell = htable.cell(0, 1)
        p = tagline_cell.paragraphs[0]
        p.text = f"SAT–{context.get('document_reference', '###')}"
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Add a line-like table
        header.add_paragraph() # Spacer
        line_table = header.add_table(rows=1, cols=1, width=section.page_width - section.left_margin - section.right_margin)
        line_cell = line_table.cell(0, 0)
        line_cell.text = ""
        set_cell_color(line_cell, '000000') # Black fill
        
        # Set row height to be very small to simulate a line
        tr = line_table.rows[0]._tr
        trPr = tr.get_or_add_trPr()
        trHeight = OxmlElement('w:trHeight')
        trHeight.set(qn('w:val'), "50") # 2.5pt height
        trPr.append(trHeight)

        # --- Main Body (empty for now) ---

        doc.save(output_path)
        current_app.logger.info(f"Report header built successfully at {output_path}")
        return True

    except Exception as e:
        current_app.logger.error(f"Error building report header: {e}", exc_info=True)
        return False
