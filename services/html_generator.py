from flask import current_app
import os
from datetime import datetime

def generate_report_html(context, output_path):
    """Generates an HTML report from context data for the first page."""
    try:
        # --- DATA PREPARATION ---
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png').replace('\\', '/')
        
        # Fallback data for when context is not fully populated
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

        # --- HTML SNIPPET GENERATION ---

        # Document Information Table
        doc_info_html = f"""
            <div class="section-title">Document Information</div>
            <table class="info-table">
                <tr>
                    <td class="label">Document Title</td>
                    <td class="value">{ doc_title }</td>
                </tr>
                <tr>
                    <td class="label">Project reference</td>
                    <td class="value">{ project_ref }</td>
                </tr>
                <tr>
                    <td class="label">Document Reference</td>
                    <td class="value">{ doc_ref }</td>
                </tr>
                <tr>
                    <td class="label">Date</td>
                    <td class="value">{ date }</td>
                </tr>
                <tr>
                    <td class="label">Prepared for</td>
                    <td class="value">{ client_name }</td>
                </tr>
                <tr>
                    <td class="label">Revision</td>
                    <td class="value">{ revision }</td>
                </tr>
            </table>
        """

        # Document Approvals Table
        approvals_html = f"""
            <div class="section-title">Document Approvals</div>
            <table>
                <tr>
                    <td class="label-cell">Prepared by</td>
                    <td style="width: 40%;">{ prepared_by }</td>
                    <td style="width: 40%;"></td>
                </tr>
                <tr>
                    <td class="label-cell">Reviewed by</td>
                    <td style="width: 40%;">{ reviewed_by_tech }</td>
                    <td style="width: 40%;"></td>
                </tr>
                <tr>
                    <td class="label-cell">Reviewed by</td>
                    <td style="width: 40%;">{ reviewed_by_pm }</td>
                    <td style="width: 40%;"></td>
                </tr>
                <tr>
                    <td class="label-cell">Approval (Client)</td>
                    <td style="width: 40%;">{ approved_by_client }</td>
                    <td style="width: 40%;"></td>
                </tr>
            </table>
        """

        # Document Version Control Table
        version_control_html = f"""
            <div class="section-title">Document Version Control</div>
            <table>
                <thead>
                    <tr>
                        <th>Revision Number</th>
                        <th>Details</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>{ revision }</td>
                        <td>{ revision_details }</td>
                        <td>{ revision_date }</td>
                    </tr>
                </tbody>
            </table>
        """

        # --- FULL HTML DOCUMENT ASSEMBLY ---
        
        body_html = f"""
            {doc_info_html}
            {approvals_html}
            {version_control_html}
        """

        html_content = f"""
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Calibri, sans-serif; font-size: 11pt; }}
        table {{ border-collapse: collapse; width: 100%; font-family: Calibri, sans-serif; font-size: 11pt; }}
        th, td {{ border: 1px solid black; padding: 8px; text-align: left; font-weight: normal; vertical-align: top; }}
        .header {{ padding-bottom: 10px; margin-bottom: 20px; text-align: right; }}
        .logo {{ width: 200px; height: auto; }}
        .section-title {{ font-weight: bold; font-size: 11pt; font-family: Calibri, sans-serif; margin-top: 20px; margin-bottom: 10px; }}
        
        /* General table cell styling */
        .label-cell {{ background-color: #E6F3FF; width: 1.88in; }}
        
        /* Info Table specific styles */
        .info-table tr {{ height: 36px; }}
        .info-table .label {{ background-color: #E6F3FF; width: 180px; }}
        
        .footer {{ position: fixed; bottom: 0; left: 0; right: 0; text-align: center; font-size: 10pt; color: #888; }}
        .confidentiality {{ margin-top: 40px; }}
    </style>
</head>
<body>
    <div class="header">
        <img src="file:///{logo_path}" class="logo" alt="Cully Logo">
    </div>

    {body_html}

    <div class="confidentiality">
        <p><strong>Confidentiality Notice:</strong> This document contains confidential and proprietary information of Cully. Unauthorized distribution or reproduction is strictly prohibited.</p>
    </div>
    
    <div class="footer">
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