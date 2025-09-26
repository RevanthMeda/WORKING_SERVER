from flask import current_app
import os

def generate_report_html(context, output_path):
    """Generates an HTML report from context data for the first page."""
    try:
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png').replace('\\', '/')

        html = f"""
<html>
<head>
<style>
    body {{ font-family: Calibri, sans-serif; font-size: 11pt; }}
    .header {{ border-bottom: 1px solid #000; padding-bottom: 10px; margin-bottom: 20px; }}
    .logo {{ width: 8.37cm; height: 1.74cm; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
    .label-cell {{ background-color: #E6F3FF; }}
</style>
</head>
<body>
    <div class="header">
        <img src="file:///{logo_path}" class="logo">
    </div>

    <h1>{context.get('document_title', 'SAT Report')}</h1>

    <table>
        <tr>
            <td class="label-cell">Document Title</td>
            <td>{context.get('document_title', '')}</td>
        </tr>
        <tr>
            <td class="label-cell">Project reference</td>
            <td>{context.get('project_reference', '')}</td>
        </tr>
        <tr>
            <td class="label-cell">Date</td>
            <td>{context.get('date', '')}</td>
        </tr>
        <tr>
            <td class="label-cell">Client Name</td>
            <td>{context.get('client_name', '')}</td>
        </tr>
        <tr>
            <td class="label-cell">Revision</td>
            <td>{context.get('revision', '')}</td>
        </tr>
    </table>

</body>
</html>
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
            
        current_app.logger.info(f"HTML report generated successfully at {output_path}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error generating HTML report: {e}", exc_info=True)
        return False
