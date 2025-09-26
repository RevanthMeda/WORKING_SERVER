from docx import Document
from docx.shared import Inches
from flask import current_app
import os

def build_sat_report(context, output_path):
    """Builds a .docx report with only the header containing the logo."""
    try:
        doc = Document()
        section = doc.sections[0]

        # --- Header ---
        header = section.header
        header.is_linked_to_previous = False
        header.paragraphs[0].text = ""
        
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png')
        if os.path.exists(logo_path):
            p = header.paragraphs[0]
            run = p.add_run()
            run.add_picture(logo_path, width=Inches(2.0))
        else:
            p = header.paragraphs[0]
            p.text = "Cully Automation"

        doc.save(output_path)
        current_app.logger.info(f"Report header built successfully at {output_path}")
        return True

    except Exception as e:
        current_app.logger.error(f"Error building report header: {e}", exc_info=True)
        return False
