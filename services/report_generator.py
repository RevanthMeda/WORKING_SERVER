from docxtpl import DocxTemplate
from flask import current_app

def generate_report_with_docxtpl(template_path, context, output_path):
    """
    Generates a .docx report from a template using docxtpl.

    Args:
        template_path (str): The path to the .docx template file.
        context (dict): A dictionary containing the data to be rendered in the template.
        output_path (str): The path to save the generated report.
    """
    try:
        doc = DocxTemplate(template_path)
        doc.render(context)
        doc.save(output_path)
        current_app.logger.info(f"Report generated successfully at {output_path}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error generating report with docxtpl: {e}", exc_info=True)
        return False
