from docx import Document
from docx.shared import Inches
from flask import current_app

def build_sat_report(context, output_path):
    """
    Builds a .docx report programmatically using python-docx.
    """
    try:
        doc = Document()

        # Set up some basic styles if they are not in the default template
        styles = doc.styles
        if 'Title' not in styles:
            styles.add_style('Title', 1)
            styles['Title'].font.name = 'Calibri'
            styles['Title'].font.size = Inches(0.28)
        if 'Heading 1' not in styles:
            styles.add_style('Heading 1', 1)
            styles['Heading 1'].font.name = 'Calibri'
            styles['Heading 1'].font.size = Inches(0.18)
            styles['Heading 1'].font.bold = True

        # Title
        doc.add_heading(context.get('DOCUMENT_TITLE', 'SAT Report'), level=0)

        # Header
        section = doc.sections[0]
        header = section.header
        p = header.paragraphs[0]
        p.text = f"{context.get('DOCUMENT_REFERENCE', '')}\t{context.get('REVISION', '')}"
        p.style = 'Header'

        # Footer
        footer = section.footer
        p = footer.paragraphs[0]
        p.text = "Page"
        p.style = 'Footer'

        # Main content
        doc.add_heading('1. Introduction', level=1)
        doc.add_paragraph(context.get('PURPOSE', ''))
        doc.add_paragraph(context.get('SCOPE', ''))

        doc.add_heading('2. Report Details', level=1)
        
        # Table with details
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Field'
        hdr_cells[1].text = 'Value'

        details = {
            "Project Reference": context.get('PROJECT_REFERENCE', ''),
            "Client Name": context.get('CLIENT_NAME', ''),
            "Date": context.get('DATE', ''),
            "Prepared By": context.get('PREPARED_BY', ''),
        }

        for key, value in details.items():
            row_cells = table.add_row().cells
            row_cells[0].text = key
            row_cells[1].text = str(value)

        doc.save(output_path)
        current_app.logger.info(f"Report built successfully at {output_path}")
        return True

    except Exception as e:
        current_app.logger.error(f"Error building report: {e}", exc_info=True)
        return False
