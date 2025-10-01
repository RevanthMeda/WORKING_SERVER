from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, make_response
from functools import wraps
from flask_login import login_required, current_user
from models import db, Report, User, SATReport
from auth import login_required, role_required
from utils import setup_approval_workflow_db, create_new_submission_notification, get_unread_count
import json
import uuid
from datetime import datetime

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')



_SAT_LIST_FIELDS = {
    "RELATED_DOCUMENTS",
    "PRE_EXECUTION_APPROVAL",
    "POST_EXECUTION_APPROVAL",
    "PRE_TEST_REQUIREMENTS",
    "KEY_COMPONENTS",
    "IP_RECORDS",
    "SIGNAL_LISTS",
    "DIGITAL_OUTPUTS",
    "ANALOGUE_INPUTS",
    "ANALOGUE_OUTPUTS",
    "MODBUS_DIGITAL_LISTS",
    "MODBUS_ANALOGUE_LISTS",
    "PROCESS_TEST",
    "SCADA_VERIFICATION",
    "TRENDS_TESTING",
    "ALARM_LIST",
    "DIGITAL_SIGNALS",
    "ANALOGUE_INPUT_SIGNALS",
    "ANALOGUE_OUTPUT_SIGNALS",
    "DIGITAL_OUTPUT_SIGNALS",
    "MODBUS_DIGITAL_SIGNALS",
    "MODBUS_ANALOGUE_SIGNALS",
    "SCADA_SCREENSHOTS",
    "TRENDS_SCREENSHOTS",
    "ALARM_SCREENSHOTS"
}



def no_cache(f):
    """Decorator to prevent caching of routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated_function


def _build_empty_sat_submission():
    base = {
        "DOCUMENT_TITLE": "",
        "PROJECT_REFERENCE": "",
        "DOCUMENT_REFERENCE": "",
        "DATE": "",
        "CLIENT_NAME": "",
        "REVISION": "",
        "REVISION_DETAILS": "",
        "REVISION_DATE": "",
        "USER_EMAIL": "",
        "PREPARED_BY": "",
        "REVIEWED_BY_TECH_LEAD": "",
        "REVIEWED_BY_PM": "",
        "APPROVED_BY_CLIENT": "",
        "PURPOSE": "",
        "SCOPE": ""
    }
    for field in _SAT_LIST_FIELDS:
        base.setdefault(field, [])
    return base



def _merge_sat_submission_data(base: dict, context: dict) -> dict:
    merged = {key: (list(value) if isinstance(value, list) else value) for key, value in base.items()}
    for key, value in context.items():
        if value in (None, ""):
            continue
        if key in _SAT_LIST_FIELDS:
            if isinstance(value, list):
                merged[key] = value
        else:
            merged[key] = value
    return merged


@reports_bp.route('/new')
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def new():
    """Show report type selection page"""
    return render_template('report_selector.html')

@reports_bp.route('/new/sat')
@login_required
@role_required(['Engineer', 'Automation Manager', 'Admin'])
def new_sat():
    """SAT report creation"""
    return redirect(url_for('reports.new_sat_full'))

@reports_bp.route('/new/sat/full')
@no_cache
@login_required
@role_required(['Engineer', 'Automation Manager', 'Admin'])
def new_sat_full():
    """Full SAT report form"""
    try:
        unread_count = get_unread_count()
        submission_id = str(uuid.uuid4())
        submission_data = _build_empty_sat_submission()
        prefill_source = None

        template_id = request.args.get('template_id')
        if template_id:
            template_report = Report.query.get(template_id)
            if template_report:
                sat_template = SATReport.query.filter_by(report_id=template_id).first()
                if sat_template and sat_template.data_json:
                    try:
                        template_data = json.loads(sat_template.data_json)
                        context_data = template_data.get('context', {})
                        submission_data = _merge_sat_submission_data(submission_data, context_data)
                        prefill_source = template_report
                    except json.JSONDecodeError:
                        flash('Could not load template data.', 'error')

        if current_user.is_authenticated:
            submission_data['USER_EMAIL'] = current_user.email
            submission_data['PREPARED_BY'] = current_user.full_name

        return render_template('SAT.html',
                             submission_data=submission_data,
                             submission_id=submission_id,
                             unread_count=unread_count,
                             is_new_report=True,
                             edit_mode=False,
                             prefill_source=prefill_source)
    except Exception as e:
        current_app.logger.error(f"Error rendering SAT form: {e}", exc_info=True)
        submission_data = _build_empty_sat_submission()
        if current_user.is_authenticated:
            submission_data['USER_EMAIL'] = current_user.email
            submission_data['PREPARED_BY'] = current_user.full_name
        return render_template('SAT.html',
                             submission_data=submission_data,
                             submission_id='',
                             unread_count=0,
                             is_new_report=True,
                             edit_mode=False,
                             prefill_source=None)


@reports_bp.route('/sat/wizard')
@login_required
@role_required(['Engineer', 'Automation Manager', 'Admin'])
def sat_wizard():
    """SAT wizard route for editing existing reports"""
    try:
        from models import Report, SATReport
        import json
        from utils import get_unread_count
        
        # Get submission_id from query params (for edit mode)
        submission_id = request.args.get('submission_id')
        edit_mode = request.args.get('edit_mode', 'false').lower() == 'true'
        
        if not submission_id or not edit_mode:
            # If no submission_id, redirect to new SAT form
            return redirect(url_for('reports.new_sat_full'))
        
        # Get the report from database
        report = Report.query.get(submission_id)
        if not report:
            flash('Report not found.', 'error')
            return redirect(url_for('dashboard.home'))
        
        # Check permissions
        if report.locked:
            flash('This report is locked and cannot be edited.', 'warning')
            return redirect(url_for('status.view_status', submission_id=submission_id))
        
        # Check ownership for Engineers
        if current_user.role == 'Engineer' and report.user_email != current_user.email:
            flash('You do not have permission to edit this report.', 'error')
            return redirect(url_for('dashboard.home'))
        
        # Get SAT report data
        sat_report = SATReport.query.filter_by(report_id=submission_id).first()
        if not sat_report:
            flash('Report data not found.', 'error')
            return redirect(url_for('dashboard.home'))
        
        # Parse the stored data
        try:
            stored_data = json.loads(sat_report.data_json)
            context_data = stored_data.get('context', {})
        except:
            context_data = {}
        
        # Get unread notifications count
        unread_count = get_unread_count()
        
        # Render the SAT form with existing data for editing
        return render_template('SAT.html',
                             submission_data=context_data,
                             submission_id=submission_id,
                             unread_count=unread_count,
                             user_role=current_user.role if hasattr(current_user, 'role') else 'user',
                             edit_mode=True,
                             is_new_report=False)
                             
    except Exception as e:
        current_app.logger.error(f"Error in sat_wizard: {e}", exc_info=True)
        flash('An error occurred while loading the report for editing.', 'error')
        return redirect(url_for('dashboard.home'))

@reports_bp.route('/new/site-survey')
@login_required
@role_required(['Engineer', 'Automation Manager', 'Admin'])
def new_site_survey():
    """Site Survey report creation"""
    try:
        import uuid
        from utils import get_unread_count
        
        # Create empty submission data structure for new site survey reports
        submission_data = {
            'DOCUMENT_TITLE': '',
            'SITE_NAME': '',
            'SITE_LOCATION': '',
            'SITE_ACCESS_DETAILS': '',
            'ON_SITE_PARKING': '',
            'AREA_ENGINEER': '',
            'SITE_CARETAKER': '',
            'SURVEY_COMPLETED_BY': current_user.full_name if current_user.is_authenticated else '',
            'CONTROL_APPROACH_DISCUSSED': '',
            'VISUAL_INSPECTION': '',
            'SITE_TYPE': '',
            'ELECTRICAL_SUPPLY': '',
            'PLANT_PHOTOS_COMPLETED': '',
            'SITE_UNDERGOING_CONSTRUCTION': '',
            'CONSTRUCTION_DESCRIPTION': ''
        }
        
        unread_count = get_unread_count()
        submission_id = str(uuid.uuid4())
        
        return render_template('Site_Survey.html', 
                             submission_data=submission_data,
                             submission_id=submission_id,
                             unread_count=unread_count,
                             is_new_report=True)
    except Exception as e:
        current_app.logger.error(f"Error rendering Site Survey form: {e}")
        submission_data = {}
        return render_template('Site_Survey.html', 
                             submission_data=submission_data,
                             submission_id='',
                             unread_count=0)

@reports_bp.route('/new/scada-migration')
@login_required
@role_required(['Engineer', 'Automation Manager', 'Admin'])
def new_scada_migration():
    """SCADA Migration Site Survey report creation"""
    try:
        import uuid
        from utils import get_unread_count
        
        # Create empty submission data structure for new SCADA migration reports
        submission_data = {
            'SITE_NAME': '',
            'SITE_LOCATION': '',
            'SITE_ACCESS_DETAILS': '',
            'ON_SITE_PARKING': '',
            'AREA_ENGINEER': '',
            'SITE_CARETAKER': '',
            'SURVEY_COMPLETED_BY': current_user.full_name if current_user.is_authenticated else '',
            'CONTROL_APPROACH_DISCUSSED': '',
            'VISUAL_INSPECTION': '',
            'SITE_TYPE': '',
            'ELECTRICAL_SUPPLY': '',
            'PLANT_PHOTOS_COMPLETED': '',
            'SITE_UNDERGOING_CONSTRUCTION': '',
            'CONSTRUCTION_DESCRIPTION': '',
            'SYSTEM_ARCHITECTURE_DESCRIPTION': '',
            'PLC_DETAILS': {},
            'HMI_DETAILS': {},
            'ROUTER_DETAILS': {},
            'NETWORK_CONFIGURATION': {},
            'MOBILE_SIGNAL_STRENGTH': {},
            'LOCAL_SCADA_DETAILS': {},
            'VERIFICATION_CHECKLIST': {}
        }
        
        unread_count = get_unread_count()
        submission_id = str(uuid.uuid4())
        
        return render_template('SCADA_migration.html', 
                             submission_data=submission_data,
                             submission_id=submission_id,
                             unread_count=unread_count,
                             is_new_report=True)
    except Exception as e:
        current_app.logger.error(f"Error rendering SCADA Migration form: {e}")
        submission_data = {}
        return render_template('SCADA_migration.html', 
                             submission_data=submission_data,
                             submission_id='',
                             unread_count=0)