
import google.generativeai as genai
from flask import current_app
import json

def generate_email_content(report_data):
    """
    Generates email content based on report data using the Gemini model.

    Args:
        report_data (dict): A dictionary containing the report data.

    Returns:
        dict: A dictionary with 'subject' and 'body' for the email.
    """
    try:
        api_key = current_app.config.get('GEMINI_API_KEY')
        model_name = current_app.config.get('GEMINI_MODEL', 'gemini-1.5-pro-latest')

        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        # Construct a detailed prompt
        prompt = construct_prompt(report_data)

        response = model.generate_content(prompt)
        
        # Assuming the model returns a JSON string with 'subject' and 'body'
        email_content = json.loads(response.text)
        
        return email_content

    except Exception as e:
        current_app.logger.error(f"Error generating email content: {e}")
        # Fallback to a default email
        return {
            "subject": f"Report Completed: {report_data.get('document_title', 'N/A')}",
            "body": "The report has been completed and is ready for review."
        }

def construct_prompt(report_data):
    """Constructs a prompt for the Gemini model based on report data."""
    
    report_type = report_data.get('type', 'SAT')
    document_title = report_data.get('document_title', 'N/A')
    project_reference = report_data.get('project_reference', 'N/A')
    client_name = report_data.get('client_name', 'N/A')

    # Basic information
    prompt = f"""
    Generate a professional email for a {report_type} report.
    The email should be suitable for stakeholders in the water industry.
    The output should be a JSON object with two keys: "subject" and "body".

    Report Details:
    - Document Title: {document_title}
    - Project Reference: {project_reference}
    - Client: {client_name}
    """

    # Add more details based on report type
    if report_type == 'SAT':
        # Extract some key findings from the SAT report
        process_tests = report_data.get('PROCESS_TEST', [])
        passed_tests = [t for t in process_tests if t.get('Pass/Fail') == 'Pass']
        failed_tests = [t for t in process_tests if t.get('Pass/Fail') == 'Fail']

        prompt += f"""
        SAT Report Summary:
        - Total Process Tests: {len(process_tests)}
        - Passed Tests: {len(passed_tests)}
        - Failed Tests: {len(failed_tests)}
        """
        if failed_tests:
            prompt += "\n- Noteworthy failed tests include: " + ", ".join([t.get('Item', 'N/A') for t in failed_tests])

    prompt += """
    Based on the above information, generate a concise and professional email.
    The body should be in HTML format.
    """
    
    return prompt

