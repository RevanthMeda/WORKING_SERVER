from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, make_response, abort
from functools import wraps
from flask_login import login_required, current_user
from models import db, Report, User, SATReport, FDSReport
from auth import login_required, role_required
from utils import setup_approval_workflow_db, create_new_submission_notification, get_unread_count, process_table_rows
from services.sat_tables import migrate_context_tables
from services.fds_generator import generate_fds_from_sat
from services.equipment_assets import build_architecture_payload
import json
import uuid
from datetime import datetime
from typing import Optional

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


def _get_first_value(source: dict, *keys, default: str = '') -> str:
    """Return the first non-empty value found for the provided keys."""
    if not isinstance(source, dict):
        return default
    for key in keys:
        value = source.get(key)
        if value not in (None, ''):
            return value
    return default


def _normalize_equipment_rows(rows):
    normalized = []
    for index, raw in enumerate(rows or [], start=1):
        if not isinstance(raw, dict):
            continue
        normalized.append({
            "S_No": _get_first_value(raw, "S_No", "s_no", "serial_no", "order", default=str(index)),
            "Model": _get_first_value(raw, "Model", "model", "model_number", "Model_Number"),
            "Description": _get_first_value(raw, "Description", "description", "Details"),
            "Quantity": _get_first_value(raw, "Quantity", "quantity", "Qty"),
            "Remarks": _get_first_value(raw, "Remarks", "remarks", "Notes", "datasheet_url"),
        })
    return [row for row in normalized if any(value for value in row.values())]


def _normalize_protocol_rows(rows):
    normalized = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        normalized.append({
            "Protocol_Type": _get_first_value(raw, "Protocol_Type", "protocol_type", "type"),
            "Communication_Details": _get_first_value(raw, "Communication_Details", "communication_details", "details"),
            "Remarks": _get_first_value(raw, "Remarks", "remarks", "Notes"),
        })
    return [row for row in normalized if any(value for value in row.values())]


def _normalize_io_rows(rows, fallback_type=None):
    normalized = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        signal_type = _get_first_value(raw, "Signal_Type", "signal_type", "Type", "type", default=fallback_type or '')
        signal_tag = _get_first_value(raw, "Signal_Tag", "signal_tag", "Tag", "tag", "Name", "name")
        description = _get_first_value(raw, "Description", "description", "Detail", "detail", "Notes", "notes")
        if not any([signal_type, signal_tag, description]):
            continue
        normalized.append({
            "Signal_Type": signal_type or (fallback_type or ''),
            "Signal_Tag": signal_tag,
            "Description": description
        })
    return normalized


def _normalize_modbus_digital_rows(rows):
    normalized = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        normalized.append({
            "S_No": _get_first_value(raw, "S_No", "s_no", "Serial", "Index"),
            "Address": _get_first_value(raw, "Address", "address"),
            "Description": _get_first_value(raw, "Description", "description"),
            "Remarks": _get_first_value(raw, "Remarks", "remarks", "Notes")
        })
    return [row for row in normalized if any(value for value in row.values())]


def _normalize_modbus_analog_rows(rows):
    normalized = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        normalized.append({
            "S_No": _get_first_value(raw, "S_No", "s_no", "Serial", "Index"),
            "Address": _get_first_value(raw, "Address", "address"),
            "Description": _get_first_value(raw, "Description", "description"),
            "Remarks": _get_first_value(raw, "Remarks", "remarks", "Notes")
        })
    return [row for row in normalized if any(value for value in row.values())]


def _assert_report_access(report: Optional[Report]):
    """Ensure the current user can access the given report."""
    if not report:
        abort(404, description="Report not found.")
    if current_user.role == 'Engineer' and report.user_email != current_user.email:
        abort(403, description="You do not have permission to access this report.")


def _hydrate_fds_submission(fds_payload: Optional[dict]) -> dict:
    """Convert stored FDS JSON payload into the flat structure expected by the template."""
    submission = _build_empty_fds_submission()
    if not isinstance(fds_payload, dict):
        return submission

    header = fds_payload.get("document_header", {}) or {}
    submission["DOCUMENT_TITLE"] = _get_first_value(header, "document_title", default=submission["DOCUMENT_TITLE"])
    submission["PROJECT_REFERENCE"] = _get_first_value(header, "project_reference", default=submission["PROJECT_REFERENCE"])
    submission["DOCUMENT_REFERENCE"] = _get_first_value(header, "document_reference", default=submission["DOCUMENT_REFERENCE"])
    submission["DATE"] = _get_first_value(header, "date", default=submission["DATE"])
    submission["PREPARED_FOR"] = _get_first_value(header, "prepared_for", default=submission["PREPARED_FOR"])
    submission["REVISION"] = _get_first_value(header, "revision", default=submission["REVISION"])
    submission["REVISION_DETAILS"] = _get_first_value(header, "revision_details", default=submission["REVISION_DETAILS"])
    submission["REVISION_DATE"] = _get_first_value(header, "revision_date", default=submission["REVISION_DATE"])
    submission["USER_EMAIL"] = _get_first_value(header, "user_email", default=submission["USER_EMAIL"])

    approvals = fds_payload.get("document_approvals", []) or []
    prepared = approvals[0] if len(approvals) > 0 else {}
    reviewer1 = approvals[1] if len(approvals) > 1 else {}
    reviewer2 = approvals[2] if len(approvals) > 2 else {}
    client = approvals[3] if len(approvals) > 3 else {}

    submission["PREPARED_BY_NAME"] = _get_first_value(prepared, "name", default=submission["PREPARED_BY_NAME"])
    submission["PREPARED_BY_ROLE"] = _get_first_value(prepared, "role", default=submission["PREPARED_BY_ROLE"])
    submission["PREPARED_BY_DATE"] = _get_first_value(prepared, "date", default=submission["PREPARED_BY_DATE"])
    submission["PREPARED_BY_EMAIL"] = _get_first_value(prepared, "email", default=submission.get("PREPARED_BY_EMAIL", ""))

    submission["REVIEWER1_NAME"] = _get_first_value(reviewer1, "name", default=submission["REVIEWER1_NAME"])
    submission["REVIEWER1_ROLE"] = _get_first_value(reviewer1, "role", default=submission["REVIEWER1_ROLE"])
    submission["REVIEWER1_DATE"] = _get_first_value(reviewer1, "date", default=submission["REVIEWER1_DATE"])
    submission["REVIEWER1_EMAIL"] = _get_first_value(reviewer1, "email", default=submission.get("REVIEWER1_EMAIL", ""))

    submission["approver_1_name"] = submission["REVIEWER1_NAME"]
    submission["approver_1_email"] = submission.get("REVIEWER1_EMAIL", "")

    submission["REVIEWER2_NAME"] = _get_first_value(reviewer2, "name", default=submission["REVIEWER2_NAME"])
    submission["REVIEWER2_ROLE"] = _get_first_value(reviewer2, "role", default=submission["REVIEWER2_ROLE"])
    submission["REVIEWER2_DATE"] = _get_first_value(reviewer2, "date", default=submission["REVIEWER2_DATE"])
    submission["REVIEWER2_EMAIL"] = _get_first_value(reviewer2, "email", default=submission.get("REVIEWER2_EMAIL", ""))

    submission["approver_2_name"] = submission["REVIEWER2_NAME"]
    submission["approver_2_email"] = submission.get("REVIEWER2_EMAIL", "")

    submission["CLIENT_APPROVAL_NAME"] = _get_first_value(client, "name", default=submission["CLIENT_APPROVAL_NAME"])
    submission["CLIENT_APPROVAL_DATE"] = _get_first_value(client, "date", default=submission.get("CLIENT_APPROVAL_DATE", ""))
    submission["CLIENT_APPROVAL_EMAIL"] = _get_first_value(client, "email", default=submission.get("CLIENT_APPROVAL_EMAIL", ""))

    submission["VERSION_HISTORY"] = fds_payload.get("document_versions") or submission["VERSION_HISTORY"]
    submission["CONFIDENTIALITY_NOTICE"] = fds_payload.get("confidentiality_notice") or submission["CONFIDENTIALITY_NOTICE"]

    system_overview = fds_payload.get("system_overview", {}) or {}
    submission["SYSTEM_OVERVIEW"] = _get_first_value(system_overview, "overview", default=submission["SYSTEM_OVERVIEW"])
    submission["SYSTEM_PURPOSE"] = _get_first_value(system_overview, "purpose", default=submission["SYSTEM_PURPOSE"])
    submission["SCOPE_OF_WORK"] = _get_first_value(system_overview, "scope_of_work", default=submission["SCOPE_OF_WORK"])
    submission["PURPOSE"] = _get_first_value(system_overview, "purpose", default=submission["PURPOSE"])
    submission["SCOPE"] = _get_first_value(system_overview, "scope_of_work", default=submission["SCOPE"])

    submission["FUNCTIONAL_REQUIREMENTS"] = fds_payload.get("functional_requirements") or submission["FUNCTIONAL_REQUIREMENTS"]
    submission["PROCESS_DESCRIPTION"] = fds_payload.get("process_description") or submission["PROCESS_DESCRIPTION"]
    submission["CONTROL_PHILOSOPHY"] = fds_payload.get("control_philosophy") or submission["CONTROL_PHILOSOPHY"]

    io_mapping = fds_payload.get("io_signal_mapping", {}) or {}
    submission["DIGITAL_SIGNALS"] = (
        fds_payload.get("digital_signals")
        or io_mapping.get("digital_signals")
        or submission["DIGITAL_SIGNALS"]
    )
    submission["ANALOGUE_INPUT_SIGNALS"] = (
        fds_payload.get("analogue_input_signals")
        or io_mapping.get("analogue_input_signals")
        or submission["ANALOGUE_INPUT_SIGNALS"]
    )
    submission["ANALOGUE_OUTPUT_SIGNALS"] = (
        fds_payload.get("analogue_output_signals")
        or io_mapping.get("analogue_output_signals")
        or submission["ANALOGUE_OUTPUT_SIGNALS"]
    )
    submission["DIGITAL_OUTPUT_SIGNALS"] = (
        fds_payload.get("digital_output_signals")
        or io_mapping.get("digital_output_signals")
        or submission["DIGITAL_OUTPUT_SIGNALS"]
    )

    hardware = fds_payload.get("equipment_and_hardware", {}) or {}
    equipment_rows = _normalize_equipment_rows(hardware.get("equipment_list") or hardware.get("equipment") or [])
    if equipment_rows:
        submission["EQUIPMENT_LIST"] = equipment_rows

    comms = fds_payload.get("communication_and_modbus", {}) or {}
    protocol_rows = _normalize_protocol_rows(comms.get("protocols"))
    if protocol_rows:
        submission["COMMUNICATION_PROTOCOLS"] = protocol_rows

    submission["MODBUS_DIGITAL_SIGNALS"] = (
        fds_payload.get("modbus_digital_signals")
        or comms.get("modbus_digital_signals")
        or submission["MODBUS_DIGITAL_SIGNALS"]
    )
    submission["MODBUS_ANALOGUE_SIGNALS"] = (
        fds_payload.get("modbus_analogue_signals")
        or comms.get("modbus_analogue_signals")
        or submission["MODBUS_ANALOGUE_SIGNALS"]
    )

    detailed_io_rows = _normalize_io_rows(io_mapping.get("detailed_io_list"))
    if not detailed_io_rows:
        detailed_io_rows = (
            _normalize_io_rows(submission["DIGITAL_SIGNALS"], fallback_type="Digital Signal") +
            _normalize_io_rows(submission["ANALOGUE_INPUT_SIGNALS"], fallback_type="Analogue Input") +
            _normalize_io_rows(submission["ANALOGUE_OUTPUT_SIGNALS"], fallback_type="Analogue Output") +
            _normalize_io_rows(submission["DIGITAL_OUTPUT_SIGNALS"], fallback_type="Digital Output") +
            _normalize_io_rows(io_mapping.get("analog_signals"), fallback_type="Analog Signal")
        )
    if detailed_io_rows:
        submission["DETAILED_IO_LIST"] = detailed_io_rows

    digital_registers = _normalize_modbus_digital_rows(comms.get("modbus_digital_registers"))
    if not digital_registers:
        mapping = fds_payload.get("io_signal_mapping") or {}
        digital_registers = _normalize_modbus_digital_rows(mapping.get("modbus_digital_registers"))
    if digital_registers:
        submission["MODBUS_DIGITAL_REGISTERS"] = digital_registers

    analog_registers = _normalize_modbus_analog_rows(comms.get("modbus_analog_registers"))
    if not analog_registers:
        mapping = fds_payload.get("io_signal_mapping") or {}
        analog_registers = _normalize_modbus_analog_rows(mapping.get("modbus_analog_registers"))
    if analog_registers:
        submission["MODBUS_ANALOG_REGISTERS"] = analog_registers

    architecture_layout = fds_payload.get("system_architecture")
    if architecture_layout:
        try:
            submission["SYSTEM_ARCHITECTURE_LAYOUT"] = json.dumps(architecture_layout)
        except (TypeError, ValueError):
            current_app.logger.warning("Unable to serialise stored architecture layout for submission preload.")

    return submission


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

    return {
        "DOCUMENT_TITLE": "",
        "PROJECT_REFERENCE": "",
        "DOCUMENT_REFERENCE": "",
        "DATE": "",
        "PREPARED_FOR": "",
        "REVISION": "",
        "REVISION_DETAILS": "",
        "REVISION_DATE": "",
        "USER_EMAIL": "",
        "PREPARED_BY_NAME": "",
        "PREPARED_BY_ROLE": "",
        "PREPARED_BY_DATE": "",
        "PREPARED_BY_EMAIL": "",
        "REVIEWER1_NAME": "",
        "REVIEWER1_ROLE": "",
        "REVIEWER1_DATE": "",
        "REVIEWER1_EMAIL": "",
        "REVIEWER2_NAME": "",
        "REVIEWER2_ROLE": "",
        "REVIEWER2_DATE": "",
        "REVIEWER2_EMAIL": "",
        "CLIENT_APPROVAL_NAME": "",
        "CLIENT_APPROVAL_DATE": "",
        "CLIENT_APPROVAL_EMAIL": "",
        "PURPOSE": "",
        "SCOPE": "",
        "approver_1_name": "",
        "approver_1_email": "",
        "approver_2_name": "",
        "approver_2_email": "",
        "VERSION_HISTORY": [],
        "CONFIDENTIALITY_NOTICE": default_confidentiality,
        "SYSTEM_OVERVIEW": "",
        "SYSTEM_PURPOSE": "",
        "SCOPE_OF_WORK": "",
        "FUNCTIONAL_REQUIREMENTS": "",
        "PROCESS_DESCRIPTION": "",
        "CONTROL_PHILOSOPHY": "",
        "SYSTEM_ARCHITECTURE_LAYOUT": "",
        "EQUIPMENT_LIST": [],
        "COMMUNICATION_PROTOCOLS": [],
        "DETAILED_IO_LIST": [],
        "MODBUS_DIGITAL_REGISTERS": [],
        "MODBUS_ANALOG_REGISTERS": [],
        "DIGITAL_SIGNALS": [],
        "ANALOGUE_INPUT_SIGNALS": [],
        "ANALOGUE_OUTPUT_SIGNALS": [],
        "DIGITAL_OUTPUT_SIGNALS": [],
        "MODBUS_DIGITAL_SIGNALS": [],
        "MODBUS_ANALOGUE_SIGNALS": []
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
            submission_data['USER_EMAIL'] = current_user.email or submission_data.get('USER_EMAIL', '')

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


@reports_bp.route('/fds/wizard')
@no_cache
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def fds_wizard():
    """Load an existing FDS report for editing."""
    try:
        submission_id = request.args.get('submission_id')
        edit_mode = request.args.get('edit_mode', 'false').lower() == 'true'

        if not submission_id or not edit_mode:
            return redirect(url_for('reports.new_fds'))

        report = Report.query.get(submission_id)
        if not report or report.type != 'FDS':
            flash('FDS report not found.', 'error')
            return redirect(url_for('dashboard.my_reports'))

        if report.locked:
            flash('This report is locked and cannot be edited.', 'warning')
            return redirect(url_for('status.view_status', submission_id=submission_id))

        if current_user.role == 'Engineer' and report.user_email != current_user.email:
            flash('You do not have permission to edit this report.', 'error')
            return redirect(url_for('dashboard.my_reports'))

        fds_report = FDSReport.query.filter_by(report_id=submission_id).first()
        stored_payload = {}
        if fds_report and fds_report.data_json:
            try:
                stored_payload = json.loads(fds_report.data_json)
            except json.JSONDecodeError:
                current_app.logger.warning(
                    "Unable to parse FDS JSON for report %s; falling back to defaults",
                    submission_id
                )
        submission_data = _hydrate_fds_submission(stored_payload)

        if current_user.is_authenticated and not submission_data.get('PREPARED_BY_EMAIL'):
            submission_data['PREPARED_BY_EMAIL'] = current_user.email

        if not submission_data.get('USER_EMAIL'):
            submission_data['USER_EMAIL'] = report.user_email or ''

        if fds_report:
            layout_payload = fds_report.get_system_architecture()
            if layout_payload:
                try:
                    submission_data['SYSTEM_ARCHITECTURE_LAYOUT'] = json.dumps(layout_payload)
                except (TypeError, ValueError):
                    current_app.logger.warning("Unable to serialize architecture layout for submission %s", submission_id)

        unread_count = get_unread_count()

        return render_template(
            'FDS.html',
            submission_data=submission_data,
            submission_id=submission_id,
            unread_count=unread_count,
            is_new_report=False,
            edit_mode=True
        )
    except Exception as exc:
        current_app.logger.error(f"Error loading FDS report for editing: {exc}", exc_info=True)
        flash('An error occurred while loading the FDS report.', 'error')
        return redirect(url_for('dashboard.my_reports'))


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


@reports_bp.route('/system-architecture/preview', methods=['POST'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def preview_system_architecture():
    """Generate a provisional system architecture layout from an equipment list."""
    payload = request.get_json(silent=True) or {}
    equipment_rows = payload.get('equipment') or payload.get('equipment_list') or []

    if not isinstance(equipment_rows, list) or not equipment_rows:
        return jsonify({
            "success": False,
            "message": "Equipment list is required to generate the architecture."
        }), 400

    submission_id = (payload.get('submission_id') or '').strip()
    existing_layout = payload.get('existing_layout') if isinstance(payload.get('existing_layout'), dict) else None

    saved_layout = None
    if submission_id:
        report = Report.query.get(submission_id)
        if report:
            _assert_report_access(report)
            if report.fds_report:
                saved_layout = report.fds_report.get_system_architecture()

    merged_layout = existing_layout or saved_layout
    try:
        architecture_payload = build_architecture_payload(equipment_rows, merged_layout)
    except Exception as exc:
        current_app.logger.error("Failed to build architecture preview: %s", exc, exc_info=True)
        return jsonify({
            "success": False,
            "message": "Unable to generate architecture preview at this time."
        }), 500

    return jsonify({
        "success": True,
        "payload": architecture_payload
    })


@reports_bp.route('/system-architecture/<submission_id>', methods=['GET'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def fetch_system_architecture(submission_id):
    """Return the saved architecture layout (and regenerate assets if necessary)."""
    report = Report.query.get(submission_id)
    _assert_report_access(report)

    equipment_rows = []
    saved_layout = None

    fds_report = report.fds_report
    if fds_report:
        saved_layout = fds_report.get_system_architecture()
        try:
            data_json = json.loads(fds_report.data_json or '{}')
            equipment_rows = data_json.get("equipment_and_hardware", {}).get("equipment_list", [])
        except Exception:
            current_app.logger.warning("Failed to parse FDS data_json for report %s", submission_id)

    if equipment_rows:
        try:
            architecture_payload = build_architecture_payload(equipment_rows, saved_layout)
        except Exception as exc:
            current_app.logger.error("Failed to rebuild architecture for report %s: %s", submission_id, exc, exc_info=True)
            architecture_payload = saved_layout or {"nodes": [], "connections": []}
    else:
        architecture_payload = saved_layout or {"nodes": [], "connections": []}

    return jsonify({
        "success": True,
        "payload": architecture_payload,
        "equipment": equipment_rows
    })


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
        report.prepared_by = request.form.get('prepared_by_name', '').strip() or report.prepared_by
        report.updated_at = datetime.utcnow()

        if not report.version or is_new_report:
            report.version = report.revision or 'R0'

        purpose_html = (request.form.get('purpose', '') or '').strip()
        scope_html = (request.form.get('scope', '') or '').strip()
        if purpose_html in ('<p><br></p>', '<p></p>'):
            purpose_html = ''
        if scope_html in ('<p><br></p>', '<p></p>'):
            scope_html = ''
        scope_of_work_value = request.form.get('scope_of_work', '').strip() or scope_html

        document_header = {
            "document_title": report.document_title,
            "project_reference": report.project_reference,
            "document_reference": report.document_reference,
            "date": request.form.get('date', ''),
            "prepared_for": report.client_name,
            "revision": report.revision,
            "revision_details": request.form.get('revision_details', '').strip(),
            "revision_date": request.form.get('revision_date', '').strip(),
            "user_email": request.form.get('user_email', '').strip(),
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
                "modbus_digital_s_no[]": "S_No",
                "modbus_digital_address[]": "Address",
                "modbus_digital_description[]": "Description",
                "modbus_digital_remarks[]": "Remarks"
            },
            add_placeholder=False
        )

        modbus_analog_rows = process_table_rows(
            request.form,
            {
                "modbus_analog_s_no[]": "S_No",
                "modbus_analog_address[]": "Address",
                "modbus_analog_description[]": "Description",
                "modbus_analog_remarks[]": "Remarks"
            },
            add_placeholder=False
        )

        digital_signals_rows = process_table_rows(
            request.form,
            {
                "digital_s_no[]": "S_No",
                "digital_rack[]": "Rack",
                "digital_pos[]": "Pos",
                "digital_signal_tag[]": "Signal_TAG",
                "digital_description[]": "Description",
                "digital_result[]": "Result",
                "digital_punch[]": "Punch",
                "digital_verified[]": "Verified",
                "digital_comment[]": "Comment"
            },
            add_placeholder=False
        )

        analogue_input_rows = process_table_rows(
            request.form,
            {
                "analogue_input_s_no[]": "S_No",
                "analogue_input_rack_no[]": "Rack_No",
                "analogue_input_module_position[]": "Module_Position",
                "analogue_input_signal_tag[]": "Signal_TAG",
                "analogue_input_description[]": "Description",
                "analogue_input_result[]": "Result",
                "analogue_input_punch_item[]": "Punch_Item",
                "analogue_input_verified_by[]": "Verified_by",
                "analogue_input_comment[]": "Comment"
            },
            add_placeholder=False
        )

        analogue_output_rows = process_table_rows(
            request.form,
            {
                "analogue_output_s_no[]": "S_No",
                "analogue_output_rack_no[]": "Rack_No",
                "analogue_output_module_position[]": "Module_Position",
                "analogue_output_signal_tag[]": "Signal_TAG",
                "analogue_output_description[]": "Description",
                "analogue_output_result[]": "Result",
                "analogue_output_punch_item[]": "Punch_Item",
                "analogue_output_verified_by[]": "Verified_by",
                "analogue_output_comment[]": "Comment"
            },
            add_placeholder=False
        )

        digital_output_rows = process_table_rows(
            request.form,
            {
                "digital_output_s_no[]": "S_No",
                "digital_output_rack_no[]": "Rack_No",
                "digital_output_module_position[]": "Module_Position",
                "digital_output_signal_tag[]": "Signal_TAG",
                "digital_output_description[]": "Description",
                "digital_output_result[]": "Result",
                "digital_output_punch_item[]": "Punch_Item",
                "digital_output_verified_by[]": "Verified_by",
                "digital_output_comment[]": "Comment"
            },
            add_placeholder=False
        )

        modbus_digital_signal_rows = process_table_rows(
            request.form,
            {
                "modbus_digital_signal_address[]": "Address",
                "modbus_digital_signal_description[]": "Description",
                "modbus_digital_signal_remarks[]": "Remarks",
                "modbus_digital_signal_result[]": "Result",
                "modbus_digital_signal_punch_item[]": "Punch_Item",
                "modbus_digital_signal_verified_by[]": "Verified_by",
                "modbus_digital_signal_comment[]": "Comment"
            },
            add_placeholder=False
        )

        modbus_analogue_signal_rows = process_table_rows(
            request.form,
            {
                "modbus_analogue_signal_address[]": "Address",
                "modbus_analogue_signal_description[]": "Description",
                "modbus_analogue_signal_range[]": "Range",
                "modbus_analogue_signal_result[]": "Result",
                "modbus_analogue_signal_punch_item[]": "Punch_Item",
                "modbus_analogue_signal_verified_by[]": "Verified_by",
                "modbus_analogue_signal_comment[]": "Comment"
            },
            add_placeholder=False
        )

        layout_raw = (request.form.get('system_architecture_layout') or '').strip()
        architecture_layout = None
        if layout_raw:
            try:
                architecture_layout = json.loads(layout_raw)
            except (TypeError, ValueError):
                current_app.logger.warning("Received invalid architecture layout JSON for submission %s", submission_id)

        fds_data = {
            "document_header": document_header,
            "document_approvals": approvals,
            "document_versions": version_history,
            "confidentiality_notice": request.form.get('confidentiality_notice', '').strip(),
            "system_overview": {
                "overview": request.form.get('system_overview', ''),
                "purpose": purpose_html or request.form.get('system_purpose', ''),
                "scope_of_work": scope_of_work_value
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
                "modbus_analog_registers": modbus_analog_rows,
                "modbus_digital_signals": modbus_digital_signal_rows,
                "modbus_analogue_signals": modbus_analogue_signal_rows
            },
            "io_signal_mapping": {
                "detailed_io_list": detailed_io_rows,
                "digital_signals": digital_signals_rows,
                "analogue_input_signals": analogue_input_rows,
                "analogue_output_signals": analogue_output_rows,
                "digital_output_signals": digital_output_rows
            },
            "digital_signals": digital_signals_rows,
            "analogue_input_signals": analogue_input_rows,
            "analogue_output_signals": analogue_output_rows,
            "digital_output_signals": digital_output_rows,
            "modbus_digital_signals": modbus_digital_signal_rows,
            "modbus_analogue_signals": modbus_analogue_signal_rows
        }

        if architecture_layout:
            fds_data["system_architecture"] = architecture_layout

        fds_report = FDSReport.query.filter_by(report_id=submission_id).first()
        if not fds_report:
            fds_report = FDSReport(report_id=submission_id)
            db.session.add(fds_report)

        fds_report.data_json = json.dumps(fds_data)
        fds_report.functional_requirements = fds_data["functional_requirements"]
        fds_report.process_description = fds_data["process_description"]
        fds_report.control_philosophy = fds_data["control_philosophy"]
        fds_report.set_system_architecture(architecture_layout)

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



