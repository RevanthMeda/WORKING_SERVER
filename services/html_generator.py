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
            <div class="section-title" style="font-weight: bold; font-size: 11pt; font-family: Calibri, sans-serif; margin-top: 20px; margin-bottom: 10px;">Document Information</div>
            <table style="width: 100%; border-collapse: collapse; border: 1px solid black; font-family: Calibri, sans-serif; font-size: 11pt;">
                <tr style="height: 36px;">
                    <td style="width: 180px; border: 1px solid black; padding: 8px; background-color: #E6F3FF;">Document Title</td>
                    <td style="border: 1px solid black; padding: 8px;">{ doc_title }</td>
                </tr>
                <tr style="height: 36px;">
                    <td style="width: 180px; border: 1px solid black; padding: 8px; background-color: #E6F3FF;">Project reference</td>
                    <td style="border: 1px solid black; padding: 8px;">{ project_ref }</td>
                </tr>
                <tr style="height: 36px;">
                    <td style="width: 180px; border: 1px solid black; padding: 8px; background-color: #E6F3FF;">Document Reference</td>
                    <td style="border: 1px solid black; padding: 8px;">{ doc_ref }</td>
                </tr>
                <tr style="height: 36px;">
                    <td style="width: 180px; border: 1px solid black; padding: 8px; background-color: #E6F3FF;">Date</td>
                    <td style="border: 1px solid black; padding: 8px;">{ date }</td>
                </tr>
                <tr style="height: 36px;">
                    <td style="width: 180px; border: 1px solid black; padding: 8px; background-color: #E6F3FF;">Prepared for</td>
                    <td style="border: 1px solid black; padding: 8px;">{ client_name }</td>
                </tr>
                <tr style="height: 36px;">
                    <td style="width: 180px; border: 1px solid black; padding: 8px; background-color: #E6F3FF;">Revision</td>
                    <td style="border: 1px solid black; padding: 8px;">{ revision }</td>
                </tr>
            </table>
        """

        # Document Approvals Table
        approvals_html = f"""
            <div class="section-title" style="font-weight: bold; font-size: 11pt; font-family: Calibri, sans-serif; margin-top: 20px; margin-bottom: 10px;">Document Approvals</div>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Prepared by</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ prepared_by }</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;"></td>
                </tr>
                <tr>
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Reviewed by</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ reviewed_by_tech }</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;"></td>
                </tr>
                <tr>
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Reviewed by</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ reviewed_by_pm }</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;"></td>
                </tr>
                <tr>
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Approval (Client)</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ approved_by_client }</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;"></td>
                </tr>
            </table>
        """

        # Document Version Control Table
        version_control_html = f"""
            <div class="section-title" style="font-weight: bold; font-size: 11pt; font-family: Calibri, sans-serif; margin-top: 20px; margin-bottom: 10px;">Document Version Control</div>
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr>
                        <th style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">Revision Number</th>
                        <th style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">Details</th>
                        <th style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">Date</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ revision }</td>
                        <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ revision_details }</td>
                        <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ revision_date }</td>
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
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #000; padding: 8px; text-align: left; vertical-align: top; }}
        .header {{ padding-bottom: 10px; margin-bottom: 20px; text-align: right; }}
        .logo {{ width: 200px; height: auto; }}
        .section-title {{ font-weight: bold; font-size: 11pt; margin-top: 20px; margin-bottom: 10px; }}
        .label-cell {{ background-color: #E6F3FF; width: 1.88in; }}
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