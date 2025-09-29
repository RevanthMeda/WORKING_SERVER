from flask import current_app
import os
from datetime import datetime

def generate_report_html(context, output_path):
    """Generates an HTML report from context data for the first page."""
    try:
        # --- DATA PREPARATION ---
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png').replace('\\', '/')
        
        # Fallback data for when context is not fully populated
        doc_title = context.get('document_title', 'Test')
        project_ref = context.get('project_reference', 'TEST-123')
        doc_ref = context.get('document_reference', 'test-doc-12')
        date = context.get('date', datetime.now().strftime('%Y-%m-%d'))
        client_name = context.get('client_name', 'test')
        revision = context.get('revision', 'R0')
        revision_details = context.get('revision_details', 'test')
        revision_date = context.get('revision_date', datetime.now().strftime('%Y-%m-%d'))

        approvals = context.get('approvals', [
            {'role': 'Prepared by', 'name': 'Revanth'},
            {'role': 'Reviewed by', 'name': 'Jinnu'},
            {'role': 'Reviewed by', 'name': 'Dazel'},
            {'role': 'Approval (Client)', 'name': 'Test'}
        ])

        # --- HTML SNIPPET GENERATION ---

        # Document Information Table
        doc_info_html = f"""
            <div class="section-title" style="font-weight: bold; font-size: 11pt; font-family: Calibri, sans-serif; margin-top: 20px; margin-bottom: 10px;">Document Information</div>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="height: 0.40in;">
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Document Title</td>
                    <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ doc_title }</td>
                </tr>
                <tr style="height: 0.40in;">
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Project reference</td>
                    <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ project_ref }</td>
                </tr>
                <tr style="height: 0.40in;">
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Document Reference</td>
                    <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ doc_ref }</td>
                </tr>
                <tr style="height: 0.40in;">
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Date</td>
                    <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ date }</td>
                </tr>
                <tr style="height: 0.40in;">
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Prepared for</td>
                    <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ client_name }</td>
                </tr>
                <tr style="height: 0.40in;">
                    <td class="label-cell" style="width: 1.88in; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">Revision</td>
                    <td style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{ revision }</td>
                </tr>
            </table>
        "

        # Document Approvals Table
        approvals_rows = ""
        for approval in approvals:
            approvals_rows += f"""
                <tr>
                    <td class="label-cell" style="border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt; background-color: #E6F3FF;">{approval.get('role', '')}</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;">{approval.get('name', '')}</td>
                    <td style="width: 40%; border: 1px solid #000; padding: 8px; text-align: left; font-family: Calibri, sans-serif; font-size: 11pt;"></td>
                </tr>
            """
        
        approvals_html = f"""
            <div class="section-title" style="font-weight: bold; font-size: 11pt; font-family: Calibri, sans-serif; margin-top: 20px; margin-bottom: 10px;">Document Approvals</div>
            <table style="width: 100%; border-collapse: collapse;">
                {approvals_rows}
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
