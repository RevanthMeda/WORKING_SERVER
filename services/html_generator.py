from flask import current_app
import os

def generate_report_html(context, output_path):
    """Generates an HTML report from context data for the first page."""
    try:
        logo_path = os.path.join(current_app.root_path, 'static', 'cully.png').replace('\\', '/')

        # Document Approvals
        approvals_html = ""
        approvals = context.get('approvals', [])
        if approvals:
            for approval in approvals:
                approvals_html += f"""
                    <tr>
                        <td class="label-cell">{approval.get('role', '')}</td>
                        <td>{approval.get('name', '')}</td>
                    </tr>
                """
        else:
            approvals_html = """
                <tr>
                    <td class="label-cell">Prepared by</td>
                    <td>Revanth</td>
                </tr>
                <tr>
                    <td class="label-cell">Reviewed by</td>
                    <td>Jinnu</td>
                </tr>
                <tr>
                    <td class="label-cell">Reviewed by</td>
                    <td>Dazel</td>
                </tr>
                <tr>
                    <td class="label-cell">Approval (Client)</td>
                    <td>Test</td>
                </tr>
            """


        # Document Version Control
        version_history_html = ""
        version_history = context.get('version_history', [])
        if version_history:
            for version in version_history:
                version_history_html += f"""
                    <tr>
                        <td>{version.version_number}</td>
                        <td>{version.change_summary}</td>
                        <td>{version.created_at.strftime('%Y-%m-%d')}</td>
                    </tr>
                """
        else:
            version_history_html = f"""
                <tr>
                    <td>{context.get('revision', 'R0')}</td>
                    <td>{ "test" }</td>
                    <td>{context.get('date', '')}</td>
                </tr>
            """


        html = f"""
<html>
<head>
<style>
    body {{ font-family: Calibri, sans-serif; font-size: 11pt; }}
    .header {{ border-bottom: 1px solid #000; padding-bottom: 10px; margin-bottom: 20px; }}
    .logo {{ width: 8.37cm; height: 1.74cm; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
    th, td {{ border: 1px solid #000; padding: 8px; text-align: left; }}
    .label-cell {{ background-color: #E6F3FF; }}
    .section-title {{ font-weight: bold; margin-top: 20px; margin-bottom: 10px; }}
    .footer {{ text-align: center; margin-top: 50px; font-size: 10pt; }}
</style>
</head>
<body>
    <div class="header">
        <img src="file:///{logo_path}" class="logo">
    </div>

    <div class="section-title">Document Information</div>
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
            <td class="label-cell">Document Reference</td>
            <td>{context.get('document_reference', '')}</td>
        </tr>
        <tr>
            <td class="label-cell">Date</td>
            <td>{context.get('date', '')}</td>
        </tr>
        <tr>
            <td class="label-cell">Prepared for</td>
            <td>{context.get('client_name', '')}</td>
        </tr>
        <tr>
            <td class="label-cell">Revision</td>
            <td>{context.get('revision', '')}</td>
        </tr>
    </table>

    <div class="section-title">Document Approvals</div>
    <table>
        {approvals_html}
    </table>

    <div class="section-title">Document Version Control</div>
    <table>
        <tr>
            <th>Revision Number</th>
            <th>Details</th>
            <th>Date</th>
        </tr>
        {version_history_html}
    </table>

    <div class="section-title">Confidentiality Notice</div>
    <p>This document contains confidential and proprietary information of Cully. Unauthorized distribution or reproduction is strictly prohibited.</p>

    <div class="footer">
        WWW.CULLY.IE
    </div>
</body>
</html>