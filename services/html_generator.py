from flask import current_app
import os

def generate_report_html(context, output_path):
    """Generates an HTML report from context data for the first page."""
    try:
        # --- DATA PREPARATION ---
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png').replace('\\', '/')
        
        doc_title = context.get('DOCUMENT_TITLE', '')
        project_ref = context.get('PROJECT_REFERENCE', '')
        doc_ref = context.get('DOCUMENT_REFERENCE', '')
        date = context.get('DATE', '')
        client_name = context.get('CLIENT_NAME', '')
        revision = context.get('REVISION', '')
        
        prepared_by = context.get('PREPARED_BY', '')
        reviewed_by_tech = context.get('REVIEWED_BY_TECH_LEAD', '')
        reviewed_by_pm = context.get('REVIEWED_BY_PM', '')
        approved_by_client = context.get('APPROVED_BY_CLIENT', '')

        revision_details = context.get('REVISION_DETAILS', '')
        revision_date = context.get('REVISION_DATE', '')

        # --- STYLE DEFINITIONS FOR DOCX COMPATIBILITY ---
        section_title_style = "font-weight: bold; font-size: 11pt; font-family: Calibri, sans-serif; margin-top: 20px; margin-bottom: 10px;"
        table_style = "width: 100%; border-collapse: collapse; font-family: Calibri, sans-serif; font-size: 11pt;"
        
        # Styles for Document Info table
        info_label_style = "width: 180px; height: 36px; border: 1px solid black; padding: 8px; background-color: #E6F3FF; font-family: Calibri, sans-serif; font-size: 11pt;"
        info_value_style = "height: 36px; border: 1px solid black; padding: 8px; font-family: Calibri, sans-serif; font-size: 11pt;"

        # Styles for Approvals table
        approvals_label_style = "width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;"
        approvals_value_style = "width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;"
        
        # Styles for Version Control table
        header_style = "border: 1px solid black; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;"
        cell_style = "border: 1px solid black; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;"

        # --- HTML SNIPPET GENERATION ---

        doc_info_html = f"""
            <div style="{section_title_style}">Document Information</div>
            <table style="{table_style}">
                <tr>
                    <td style="{info_label_style}">Document Title</td>
                    <td style="{info_value_style}">{doc_title}</td>
                </tr>
                <tr>
                    <td style="{info_label_style}">Project reference</td>
                    <td style="{info_value_style}">{project_ref}</td>
                </tr>
                <tr>
                    <td style="{info_label_style}">Document Reference</td>
                    <td style="{info_value_style}">{doc_ref}</td>
                </tr>
                <tr>
                    <td style="{info_label_style}">Date</td>
                    <td style="{info_value_style}">{date}</td>
                </tr>
                <tr>
                    <td style="{info_label_style}">Prepared for</td>
                    <td style="{info_value_style}">{client_name}</td>
                </tr>
                <tr>
                    <td style="{info_label_style}">Revision</td>
                    <td style="{info_value_style}">{revision}</td>
                </tr>
            </table>
        """

        approvals_html = f"""
            <div style="{section_title_style}">Document Approvals</div>
            <table style="{table_style}">
                <tr>
                    <td style="{approvals_label_style}">Prepared by</td>
                    <td style="{approvals_value_style}">{prepared_by}</td>
                    <td style="{approvals_value_style}"></td>
                </tr>
                <tr>
                    <td style="{approvals_label_style}">Reviewed by</td>
                    <td style="{approvals_value_style}">{reviewed_by_tech}</td>
                    <td style="{approvals_value_style}"></td>
                </tr>
                <tr>
                    <td style="{approvals_label_style}">Reviewed by</td>
                    <td style="{approvals_value_style}">{reviewed_by_pm}</td>
                    <td style="{approvals_value_style}"></td>
                </tr>
                <tr>
                    <td style="{approvals_label_style}">Approval (Client)</td>
                    <td style="{approvals_value_style}">{approved_by_client}</td>
                    <td style="{approvals_value_style}"></td>
                </tr>
            </table>
        """

        version_control_html = f"""
            <div style="{section_title_style}">Document Version Control</div>
            <table style="{table_style}">
                <thead>
                    <tr>
                        <th style="{header_style}">Revision Number</th>
                        <th style="{header_style}">Details</th>
                        <th style="{header_style}">Date</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="{cell_style}">{revision}</td>
                        <td style="{cell_style}">{revision_details}</td>
                        <td style="{cell_style}">{revision_date}</td>
                    </tr>
                </tbody>
            </table>
        """

        body_html = f"""
            <h1 style="color: red;">DEBUG TEST v1</h1>
            {doc_info_html}
            {approvals_html}
            {version_control_html}
        """

        html_content = f"""
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Calibri, sans-serif; font-size: 11pt;">
    <div style="padding-bottom: 10px; margin-bottom: 20px; text-align: right;">
        <img src="file:///{logo_path}" style="width: 200px; height: auto;" alt="Cully Logo">
    </div>

    {body_html}

    <div style="margin-top: 40px;">
        <p><strong>Confidentiality Notice:</strong> This document contains confidential and proprietary information of Cully. Unauthorized distribution or reproduction is strictly prohibited.</p>
    </div>
    
    <div style="position: fixed; bottom: 0; left: 0; right: 0; text-align: center; font-size: 10pt; color: #888;">
        WWW.CULLY.IE
    </div>
</body>
</html>
"""

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        current_app.logger.info(f"HTML report generated successfully at {output_path}")
        return True
    except Exception as e:
        current_app.logger.error(f"Error generating HTML report: {e}", exc_info=True)
        return False