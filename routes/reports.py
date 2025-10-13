from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, make_response
from functools import wraps
from flask_login import login_required, current_user
from models import db, Report, User, SATReport, FDSReport
from auth import login_required, role_required
from utils import setup_approval_workflow_db, create_new_submission_notification, get_unread_count, process_table_rows
from services.sat_tables import migrate_context_tables
from services.fds_generator import generate_fds_from_sat
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


def _build_empty_fds_submission() -> dict:
    default_confidentiality = (
        "This document contains confidential and proprietary information of Cully. "
        "Unauthorized distribution or reproduction is strictly prohibited."
    )

    version_history = [{
        "Revision": "R0",
        "Details": "Initial Document",
        "Date": "2025-06-03"
    }]

    equipment_list = [
        {"S_No": "1", "Model": "PM573-ETH", "Description": "ABB AC500 CPU Module", "Quantity": "1", "Remarks": "Ethernet, RS232/485"},
        {"S_No": "2", "Model": "TB521-ETH", "Description": "Terminal Base for PM573 CPU", "Quantity": "1", "Remarks": "DIN rail mount"},
        {"S_No": "3", "Model": "DA501", "Description": "ABB Digital I/O Module", "Quantity": "1", "Remarks": "8 DI, 8 DO"},
        {"S_No": "4", "Model": "TB511-ETH", "Description": "Terminal Base for DA501", "Quantity": "1", "Remarks": "DIN rail mount"},
        {"S_No": "5", "Model": "RUT906", "Description": "Teltonika Industrial Router", "Quantity": "1", "Remarks": "4G LTE, Ethernet, Dual SIM"},
        {"S_No": "6", "Model": "PR1DK12", "Description": "DIN Rail Mounting Kit", "Quantity": "1", "Remarks": "For Teltonika Router"},
        {"S_No": "7", "Model": "OMB.6912.03F21", "Description": "Taoglas LTE MIMO Antenna", "Quantity": "1", "Remarks": "698-2700 MHz, N-Type"},
        {"S_No": "8", "Model": "Relay", "Description": "Phenix Contact Relay", "Quantity": "1", "Remarks": "Inhibit signal relay"}
    ]

    communication_protocols = [
        {"Protocol_Type": "Modbus TCP/IP", "Communication_Details": "ABB AC500, Schneider PLC to SCADA", "Remarks": "Real-time monitoring"},
        {"Protocol_Type": "Ethernet", "Communication_Details": "Internal Communication", "Remarks": "Networked devices"}
    ]

    detailed_io = [
        {"Signal_Type": "Digital Input", "Signal_Tag": "DI_00_01_00 to DI_00_01_15", "Description": "General spare digital inputs for future expansion or additional discrete signals as required"},
        {"Signal_Type": "Digital Output", "Signal_Tag": "DO_00_01_00 to DO_00_01_07", "Description": "Spare digital outputs available for control actions or alarm indicators"},
        {"Signal_Type": "Analog Input", "Signal_Tag": "AI_00_01_00 to AI_00_01_03 (spares)", "Description": "Reserved analog inputs for additional future instrumentation"},
        {"Signal_Type": "Analog Output", "Signal_Tag": "AO_00_01_00 to AO_00_01_01", "Description": "Spare analog outputs available for control signals or set points as required"}
    ]

    modbus_digital = [
        {"Address": "MW2800.0", "Description": "Supply Healthy", "Tag": "Supply_Healthy", "Remarks": "Closed for Healthy"},
        {"Address": "MW2800.1", "Description": "Generator Supply On", "Tag": "Generator_Supply_On", "Remarks": "Closed for Supply On"},
        {"Address": "MW2800.2", "Description": "Pump No.1 Auto Available", "Tag": "Pump_1_Auto_Available", "Remarks": "Closed for Auto"},
        {"Address": "MW2800.3", "Description": "Pump No.1 Run", "Tag": "Pump_1_Run", "Remarks": "Closed for Running"},
        {"Address": "MW2800.4", "Description": "Pump No.1 Fault", "Tag": "Pump_1_Fault", "Remarks": "Closed for Fault"},
        {"Address": "MW2800.5", "Description": "Pump No.1 Overheat", "Tag": "Pump_1_Overheat", "Remarks": "Closed for Fault"},
        {"Address": "MW2800.6", "Description": "Pump No.1 Seal Fail", "Tag": "Pump_1_Seal_Fail", "Remarks": "Closed for Fault"},
        {"Address": "MW2800.7", "Description": "Pump No.1 No Load Fault", "Tag": "Pump_1_No_Load_Fault", "Remarks": "Closed for Fault"},
        {"Address": "MW2800.8", "Description": "Pump No.1 E-Stop Activated", "Tag": "Pump_1_E_Stop_Activated", "Remarks": "Closed for Fault"},
        {"Address": "MW2800.9", "Description": "Pump No.2 Auto Available", "Tag": "Pump_2_Auto_Available", "Remarks": "Closed for Auto"}
    ]

    modbus_analog = [
        {"Address": "MW110", "Description": "Wet Well Primary Level", "Range": "0-32000 / 0 - 4 m", "Tag": "Wet_Well_Primary_Level"},
        {"Address": "MW111", "Description": "Bifurcation Manhole Overflow Signal", "Range": "0-32000 / 0 - 431 m3/hr", "Tag": "Bifurcation_Manhole_Overflow_Signal"},
        {"Address": "MW112", "Description": "Outlet Flowrate", "Range": "0-32000 / 0 - 300 m3/hr", "Tag": "Outlet_Flowrate"},
        {"Address": "MW114", "Description": "Pump No.1 Rising Main Pressure", "Range": "0-32000 / 0 - 10 Bar", "Tag": "Pump_1_Rising_Main_Pressure"},
        {"Address": "MW115", "Description": "Pump No.2 Rising Main Pressure", "Range": "0-32000 / 0 - 10 Bar", "Tag": "Pump_2_Rising_Main_Pressure"},
        {"Address": "MW2810", "Description": "Pump No.1 Frequency", "Range": "0 - 500 / 0 - 50.00 Hz", "Tag": "Pump_1_Frequency"},
        {"Address": "MW2811", "Description": "Pump No.1 Current", "Range": "0 - 16 A", "Tag": "Pump_1_Current"},
        {"Address": "MW2813", "Description": "Pump No.2 Frequency", "Range": "0 - 500 / 0 - 50.00 Hz", "Tag": "Pump_2_Frequency"}
    ]

    return {
        "DOCUMENT_TITLE": "Functional Design Specification",
        "PROJECT_REFERENCE": "Midleton NW Pumping Station",
        "DOCUMENT_REFERENCE": "PROJ.544.FDS.01.R1",
        "DATE": "2025-06-03",
        "PREPARED_FOR": "FM Environmental Ltd",
        "REVISION": "R0",
        "PREPARED_BY_NAME": "Revanth Meda",
        "PREPARED_BY_ROLE": "Automation Engineer",
        "PREPARED_BY_DATE": "2025-06-03",
        "PREPARED_BY_EMAIL": "",
        "REVIEWER1_NAME": "Jinnu Chacko",
        "REVIEWER1_ROLE": "Automation Manager",
        "REVIEWER1_DATE": "",
        "REVIEWER1_EMAIL": "",
        "REVIEWER2_NAME": "Dazel Borgie Lewis",
        "REVIEWER2_ROLE": "Project Manager",
        "REVIEWER2_DATE": "",
        "REVIEWER2_EMAIL": "",
        "CLIENT_APPROVAL_NAME": "Eoin Carragher",
        "CLIENT_APPROVAL_DATE": "",
        "VERSION_HISTORY": version_history,
        "CONFIDENTIALITY_NOTICE": default_confidentiality,
        "SYSTEM_OVERVIEW": "",
        "SYSTEM_PURPOSE": "",
        "SCOPE_OF_WORK": "",
        "FUNCTIONAL_REQUIREMENTS": "",
        "PROCESS_DESCRIPTION": "",
        "CONTROL_PHILOSOPHY": "",
        "EQUIPMENT_LIST": equipment_list,
        "COMMUNICATION_PROTOCOLS": communication_protocols,
        "DETAILED_IO_LIST": detailed_io,
        "MODBUS_DIGITAL_REGISTERS": modbus_digital,
        "MODBUS_ANALOG_REGISTERS": modbus_analog
    }



def _merge_sat_submission_data(base: dict, context: dict) -> dict:
    merged = {key: (list(value) if isinstance(value, list) else value) for key, value in base.items()}

    normalized_context = migrate_context_tables(context or {})

    for key, value in normalized_context.items():
        if value in (None, ""):
            continue
        if key in _SAT_LIST_FIELDS and isinstance(value, list):
            merged[key] = value
        else:
            merged[key] = value

    for key, value in (context or {}).items():
        if key in normalized_context:
            continue
        if key in _SAT_LIST_FIELDS and isinstance(value, list):
            merged[key] = value
        elif value not in (None, "") and key not in merged:
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
            base_data = _build_empty_sat_submission()
            submission_data = _merge_sat_submission_data(base_data, context_data)
        except:
            submission_data = _build_empty_sat_submission()
        
        # Get unread notifications count
        unread_count = get_unread_count()
        
        # Render the SAT form with existing data for editing
        return render_template('SAT.html',
                             submission_data=submission_data,
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

@reports_bp.route('/new/fds')
@no_cache
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def new_fds():
    """Render the Functional Design Specification form."""
    try:
        unread_count = get_unread_count()
        submission_id = str(uuid.uuid4())
        submission_data = _build_empty_fds_submission()

        if current_user.is_authenticated:
            submission_data.setdefault('PREPARED_BY_NAME', current_user.full_name or submission_data['PREPARED_BY_NAME'])
            submission_data.setdefault('PREPARED_BY_EMAIL', current_user.email or submission_data.get('PREPARED_BY_EMAIL', ''))

        return render_template(
            'FDS.html',
            submission_data=submission_data,
            submission_id=submission_id,
            unread_count=unread_count,
            is_new_report=True,
            edit_mode=False
        )
    except Exception as exc:
        current_app.logger.error(f"Error rendering FDS form: {exc}", exc_info=True)
        flash('Unable to load the FDS form. Please try again later.', 'error')
        return redirect(url_for('dashboard.engineer'))


@reports_bp.route('/generate-fds/<sat_report_id>')
@login_required
@role_required(['Engineer', 'Automation Manager', 'Admin'])
def generate_fds(sat_report_id):
    """Generate an FDS from an existing SAT report."""
    try:
        # 1. Fetch the SAT Report
        sat_report = SATReport.query.filter_by(report_id=sat_report_id).first()
        if not sat_report:
            flash('SAT Report not found.', 'error')
            return redirect(url_for('dashboard.my_reports'))

        # 2. Load SAT data
        sat_data = json.loads(sat_report.data_json)

        # 3. Generate FDS data
        fds_data = generate_fds_from_sat(sat_data)

        # 4. Create new Report and FDSReport objects
        parent_report = Report.query.get(sat_report_id)

        new_report = Report(
            id=str(uuid.uuid4()),
            type='FDS',
            status='DRAFT',
            document_title=fds_data.get("document_header", {}).get("document_title", "Functional Design Specification"),
            project_reference=parent_report.project_reference,
            client_name=parent_report.client_name,
            user_email=current_user.email,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        fds_report = FDSReport(
            report_id=new_report.id,
            data_json=json.dumps(fds_data),
            functional_requirements=fds_data.get("system_overview", {}).get("purpose"),
            process_description=fds_data.get("system_overview", {}).get("scope_of_work"),
            control_philosophy="Generated from SAT report"
        )

        new_report.fds_report = fds_report

        # 5. Save to database
        db.session.add(new_report)
        db.session.commit()

        flash(f'Successfully generated FDS report: {new_report.document_title}', 'success')
        return redirect(url_for('dashboard.my_reports'))

    except Exception as e:
        current_app.logger.error(f"Error generating FDS report: {e}", exc_info=True)
        flash('Failed to generate FDS report.', 'error')
        return redirect(url_for('dashboard.my_reports'))


@reports_bp.route('/submit-fds', methods=['POST'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def submit_fds():
    """Persist an FDS form submission."""
    try:
        submission_id = (request.form.get('submission_id') or '').strip() or str(uuid.uuid4())

        report = Report.query.get(submission_id)
        is_new_report = False

        if not report:
            is_new_report = True
            report = Report(
                id=submission_id,
                type='FDS',
                status='DRAFT',
                user_email=current_user.email,
                created_at=datetime.utcnow(),
                approvals_json='[]'
            )
            db.session.add(report)
        else:
            if report.type != 'FDS':
                report.type = 'FDS'
            report.status = 'DRAFT'
            report.locked = False

        report.document_title = request.form.get('document_title', '').strip() or 'Functional Design Specification'
        report.project_reference = request.form.get('project_reference', '').strip()
        report.document_reference = request.form.get('document_reference', '').strip()
        report.client_name = request.form.get('prepared_for', '').strip()
        report.revision = request.form.get('revision', '').strip() or report.revision or 'R0'
        report.updated_at = datetime.utcnow()

        if not report.version or is_new_report:
            report.version = report.revision or 'R0'

        document_header = {
            "document_title": report.document_title,
            "project_reference": report.project_reference,
            "document_reference": report.document_reference,
            "date": request.form.get('date', ''),
            "prepared_for": report.client_name,
            "revision": report.revision,
        }

        approvals = [
            {
                "role": request.form.get('prepared_by_role', ''),
                "name": request.form.get('prepared_by_name', ''),
                "date": request.form.get('prepared_by_date', ''),
                "email": request.form.get('prepared_by_email', '')
            },
            {
                "role": request.form.get('reviewer1_role', ''),
                "name": request.form.get('reviewer1_name', ''),
                "date": request.form.get('reviewer1_date', ''),
                "email": request.form.get('reviewer1_email', '')
            },
            {
                "role": request.form.get('reviewer2_role', ''),
                "name": request.form.get('reviewer2_name', ''),
                "date": request.form.get('reviewer2_date', ''),
                "email": request.form.get('reviewer2_email', '')
            },
            {
                "role": "Client Approval",
                "name": request.form.get('client_approval_name', ''),
                "date": request.form.get('client_approval_date', ''),
                "email": request.form.get('client_approval_email', '')
            }
        ]

        version_history = process_table_rows(
            request.form,
            {
                "version_revision[]": "Revision",
                "version_details[]": "Details",
                "version_date[]": "Date"
            },
            add_placeholder=False
        )

        equipment_rows = process_table_rows(
            request.form,
            {
                "equipment_sno[]": "S_No",
                "equipment_model[]": "Model",
                "equipment_description[]": "Description",
                "equipment_quantity[]": "Quantity",
                "equipment_remarks[]": "Remarks"
            },
            add_placeholder=False
        )

        protocol_rows = process_table_rows(
            request.form,
            {
                "protocol_type[]": "Protocol_Type",
                "protocol_details[]": "Communication_Details",
                "protocol_remarks[]": "Remarks"
            },
            add_placeholder=False
        )

        detailed_io_rows = process_table_rows(
            request.form,
            {
                "io_signal_type[]": "Signal_Type",
                "io_signal_tag[]": "Signal_Tag",
                "io_description[]": "Description"
            },
            add_placeholder=False
        )

        modbus_digital_rows = process_table_rows(
            request.form,
            {
                "modbus_digital_address[]": "Address",
                "modbus_digital_description[]": "Description",
                "modbus_digital_tag[]": "Tag",
                "modbus_digital_remarks[]": "Remarks"
            },
            add_placeholder=False
        )

        modbus_analog_rows = process_table_rows(
            request.form,
            {
                "modbus_analog_address[]": "Address",
                "modbus_analog_description[]": "Description",
                "modbus_analog_range[]": "Range",
                "modbus_analog_tag[]": "Tag"
            },
            add_placeholder=False
        )

        fds_data = {
            "document_header": document_header,
            "document_approvals": approvals,
            "document_versions": version_history,
            "confidentiality_notice": request.form.get('confidentiality_notice', '').strip(),
            "system_overview": {
                "overview": request.form.get('system_overview', ''),
                "purpose": request.form.get('system_purpose', ''),
                "scope_of_work": request.form.get('scope_of_work', '')
            },
            "functional_requirements": request.form.get('functional_requirements', ''),
            "process_description": request.form.get('process_description', ''),
            "control_philosophy": request.form.get('control_philosophy', ''),
            "equipment_and_hardware": {
                "equipment_list": equipment_rows
            },
            "communication_and_modbus": {
                "protocols": protocol_rows,
                "modbus_digital_registers": modbus_digital_rows,
                "modbus_analog_registers": modbus_analog_rows
            },
            "io_signal_mapping": {
                "detailed_io_list": detailed_io_rows
            }
        }

        fds_report = FDSReport.query.filter_by(report_id=submission_id).first()
        if not fds_report:
            fds_report = FDSReport(report_id=submission_id)
            db.session.add(fds_report)

        fds_report.data_json = json.dumps(fds_data)
        fds_report.functional_requirements = fds_data["functional_requirements"]
        fds_report.process_description = fds_data["process_description"]
        fds_report.control_philosophy = fds_data["control_philosophy"]

        report.fds_report = fds_report

        db.session.commit()

        response_payload = {
            "success": True,
            "message": "FDS draft saved successfully.",
            "submission_id": submission_id,
            "redirect_url": url_for('dashboard.my_reports')
        }

        wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
        )

        if wants_json:
            return jsonify(response_payload)

        flash(response_payload["message"], "success")
        return redirect(response_payload["redirect_url"])

    except Exception as exc:
        current_app.logger.error(f"Error saving FDS report: {exc}", exc_info=True)
        message = 'Failed to save FDS report.'
        wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
        )
        if wants_json:
            return jsonify({"success": False, "message": message}), 500
        flash(message, 'error')
        return redirect(url_for('dashboard.engineer'))
