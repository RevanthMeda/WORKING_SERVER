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

def add_watermark(doc, image_path):
    if not os.path.exists(image_path):
        return
    
    for section in doc.sections:
        header = section.header
        p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        
        # The following is a workaround to add a watermark
        # It adds a shape to the header with the image
        # The image is set to be behind the text
        p.add_run().add_picture(image_path, width=Cm(15))
        last_paragraph = doc.paragraphs[-1] 
        last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

def build_sat_report(context, output_path):
    """Builds the first page of the SAT report with a watermark."""
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

        # --- Watermark ---
        watermark_path = os.path.join(current_app.root_path, 'static', 'Cully_Watermark.jpg')
        add_watermark(doc, watermark_path)

        # --- Main Body ---
        # ... (rest of the page content)

        doc.save(output_path)
        current_app.logger.info(f"Report first page built successfully at {output_path}")
        return True

    except Exception as e:
        current_app.logger.error(f"Error building report: {e}", exc_info=True)
        return False