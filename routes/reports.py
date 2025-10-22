from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, make_response, abort
from functools import wraps
from flask_login import login_required, current_user
from models import db, Report, User, SATReport, FDSReport, SiteSurveyReport, SystemArchitectureVersion
from auth import login_required, role_required
from utils import (
    setup_approval_workflow_db,
    create_new_submission_notification,
    get_unread_count,
    process_table_rows,
    handle_image_removals,
)
from services.sat_tables import migrate_context_tables
from services.fds_generator import generate_fds_from_sat
from services.equipment_assets import (
    build_architecture_payload,
    list_cached_assets,
    save_user_asset_image,
)
from services.system_architecture import (
    ensure_layout,
    fetch_template,
    fetch_version,
    list_templates,
    list_versions,
    persist_layout,
    record_version_snapshot,
    save_template,
)
import os
import json
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from werkzeug.utils import secure_filename

reports_bp = Blueprint('reports', __name__)



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


def _canonical_static_url(value) -> str:
    """Return a canonical path for static upload URLs so we can deduplicate entries."""
    if value in (None, ''):
        return ''

    candidate = str(value).strip()
    if not candidate:
        return ''

    candidate = candidate.replace('\\', '/')

    try:
        static_url_path = (current_app.static_url_path or '/static').rstrip('/')
    except RuntimeError:
        static_url_path = '/static'
    uploads_prefix = f"{static_url_path}/uploads/"

    parsed = urlparse(candidate)

    if parsed.scheme and parsed.netloc:
        path = (parsed.path or '').replace('\\', '/')
        if not path:
            return parsed.geturl()
        base_path = path if path.startswith('/') else f'/{path}'
        if base_path.startswith(uploads_prefix):
            canonical = base_path
        elif base_path.startswith('/uploads/'):
            canonical = f"{uploads_prefix}{base_path[len('/uploads/'):]}"
        elif base_path.startswith('/static/'):
            canonical = base_path
        else:
            return parsed.geturl()
        return canonical

    if candidate.startswith('//'):
        return candidate

    base, _, _ = candidate.partition('?')
    base = base.replace('\\', '/')

    if base.startswith(uploads_prefix):
        canonical = base
    elif base.startswith(static_url_path):
        canonical = base if base.startswith('/') else f"/{base.lstrip('/')}"
    elif base.startswith('/static/'):
        canonical = '/' + base.lstrip('/')
    elif base.startswith('static/'):
        canonical = '/' + base.lstrip('/')
    elif base.startswith('/uploads/'):
        canonical = f"{uploads_prefix}{base[len('/uploads/'):]}"
    elif base.startswith('uploads/'):
        canonical = f"{uploads_prefix}{base[len('uploads/'):]}"
    else:
        canonical = base if base.startswith('/') or base.startswith('//') else base

    return canonical.strip()


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
    context_block = fds_payload.get("context", {}) or {}
    if context_block:
        merged_header = dict(header)
        context_header = {
            "document_title": context_block.get("DOCUMENT_TITLE"),
            "project_reference": context_block.get("PROJECT_REFERENCE"),
            "document_reference": context_block.get("DOCUMENT_REFERENCE"),
            "date": context_block.get("DATE"),
            "prepared_for": context_block.get("PREPARED_FOR"),
            "revision": context_block.get("REVISION"),
            "revision_details": context_block.get("REVISION_DETAILS"),
            "revision_date": context_block.get("REVISION_DATE"),
            "user_email": context_block.get("USER_EMAIL"),
        }
        for key, value in context_header.items():
            if value not in (None, "") and key not in merged_header:
                merged_header[key] = value
        header = merged_header

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

    if context_block:
        submission["DOCUMENT_TITLE"] = context_block.get("DOCUMENT_TITLE", submission["DOCUMENT_TITLE"])
        submission["PROJECT_REFERENCE"] = context_block.get("PROJECT_REFERENCE", submission["PROJECT_REFERENCE"])
        submission["DOCUMENT_REFERENCE"] = context_block.get("DOCUMENT_REFERENCE", submission["DOCUMENT_REFERENCE"])
        submission["DATE"] = context_block.get("DATE", submission["DATE"])
        submission["PREPARED_FOR"] = context_block.get("PREPARED_FOR", submission["PREPARED_FOR"])
        submission["REVISION"] = context_block.get("REVISION", submission["REVISION"])
        submission["REVISION_DETAILS"] = context_block.get("REVISION_DETAILS", submission["REVISION_DETAILS"])
        submission["REVISION_DATE"] = context_block.get("REVISION_DATE", submission["REVISION_DATE"])
        submission["USER_EMAIL"] = context_block.get("USER_EMAIL", submission["USER_EMAIL"])

        submission["PREPARED_BY_NAME"] = context_block.get("PREPARED_BY_NAME", submission["PREPARED_BY_NAME"])
        submission["PREPARED_BY_ROLE"] = context_block.get("PREPARED_BY_ROLE", submission["PREPARED_BY_ROLE"])
        submission["PREPARED_BY_DATE"] = context_block.get("PREPARED_BY_DATE", submission["PREPARED_BY_DATE"])
        submission["PREPARED_BY_EMAIL"] = context_block.get("PREPARED_BY_EMAIL", submission.get("PREPARED_BY_EMAIL", ""))

        submission["REVIEWER1_NAME"] = context_block.get("REVIEWER1_NAME", submission["REVIEWER1_NAME"])
        submission["REVIEWER1_ROLE"] = context_block.get("REVIEWER1_ROLE", submission["REVIEWER1_ROLE"])
        submission["REVIEWER1_DATE"] = context_block.get("REVIEWER1_DATE", submission["REVIEWER1_DATE"])
        submission["REVIEWER1_EMAIL"] = context_block.get("REVIEWER1_EMAIL", submission.get("REVIEWER1_EMAIL", ""))
        submission["approver_1_name"] = submission["REVIEWER1_NAME"]
        submission["approver_1_email"] = submission.get("REVIEWER1_EMAIL", "")

        submission["REVIEWER2_NAME"] = context_block.get("REVIEWER2_NAME", submission["REVIEWER2_NAME"])
        submission["REVIEWER2_ROLE"] = context_block.get("REVIEWER2_ROLE", submission["REVIEWER2_ROLE"])
        submission["REVIEWER2_DATE"] = context_block.get("REVIEWER2_DATE", submission["REVIEWER2_DATE"])
        submission["REVIEWER2_EMAIL"] = context_block.get("REVIEWER2_EMAIL", submission.get("REVIEWER2_EMAIL", ""))
        submission["approver_2_name"] = submission["REVIEWER2_NAME"]
        submission["approver_2_email"] = submission.get("REVIEWER2_EMAIL", "")

        submission["CLIENT_APPROVAL_NAME"] = context_block.get("CLIENT_APPROVAL_NAME", submission["CLIENT_APPROVAL_NAME"])
        submission["CLIENT_APPROVAL_DATE"] = context_block.get("CLIENT_APPROVAL_DATE", submission.get("CLIENT_APPROVAL_DATE", ""))
        submission["CLIENT_APPROVAL_EMAIL"] = context_block.get("CLIENT_APPROVAL_EMAIL", submission.get("CLIENT_APPROVAL_EMAIL", ""))

        if not submission["VERSION_HISTORY"]:
            submission["VERSION_HISTORY"] = context_block.get("VERSION_HISTORY", submission["VERSION_HISTORY"])
        if not submission["CONFIDENTIALITY_NOTICE"]:
            submission["CONFIDENTIALITY_NOTICE"] = context_block.get("CONFIDENTIALITY_NOTICE", submission["CONFIDENTIALITY_NOTICE"])

        submission["SYSTEM_OVERVIEW"] = context_block.get("SYSTEM_OVERVIEW", submission["SYSTEM_OVERVIEW"])
        submission["SYSTEM_PURPOSE"] = context_block.get("SYSTEM_PURPOSE", submission["SYSTEM_PURPOSE"])
        submission["SCOPE_OF_WORK"] = context_block.get("SCOPE_OF_WORK", submission["SCOPE_OF_WORK"])
        submission["PURPOSE"] = context_block.get("SYSTEM_PURPOSE", submission["PURPOSE"])
        submission["SCOPE"] = context_block.get("SCOPE_OF_WORK", submission["SCOPE"])

        submission["FUNCTIONAL_REQUIREMENTS"] = context_block.get("FUNCTIONAL_REQUIREMENTS", submission["FUNCTIONAL_REQUIREMENTS"])
        submission["PROCESS_DESCRIPTION"] = context_block.get("PROCESS_DESCRIPTION", submission["PROCESS_DESCRIPTION"])
        submission["CONTROL_PHILOSOPHY"] = context_block.get("CONTROL_PHILOSOPHY", submission["CONTROL_PHILOSOPHY"])

        if not submission["EQUIPMENT_LIST"]:
            submission["EQUIPMENT_LIST"] = context_block.get("EQUIPMENT_LIST", submission["EQUIPMENT_LIST"])
        if not submission["COMMUNICATION_PROTOCOLS"]:
            submission["COMMUNICATION_PROTOCOLS"] = context_block.get("COMMUNICATION_PROTOCOLS", submission["COMMUNICATION_PROTOCOLS"])
        if not submission["DETAILED_IO_LIST"]:
            submission["DETAILED_IO_LIST"] = context_block.get("DETAILED_IO_LIST", submission["DETAILED_IO_LIST"])

        submission["DIGITAL_SIGNALS"] = context_block.get("DIGITAL_SIGNALS", submission["DIGITAL_SIGNALS"])
        submission["ANALOGUE_INPUT_SIGNALS"] = context_block.get("ANALOGUE_INPUT_SIGNALS", submission["ANALOGUE_INPUT_SIGNALS"])
        submission["ANALOGUE_OUTPUT_SIGNALS"] = context_block.get("ANALOGUE_OUTPUT_SIGNALS", submission["ANALOGUE_OUTPUT_SIGNALS"])
        submission["DIGITAL_OUTPUT_SIGNALS"] = context_block.get("DIGITAL_OUTPUT_SIGNALS", submission["DIGITAL_OUTPUT_SIGNALS"])

        if not submission["MODBUS_DIGITAL_REGISTERS"]:
            submission["MODBUS_DIGITAL_REGISTERS"] = context_block.get("MODBUS_DIGITAL_REGISTERS", submission["MODBUS_DIGITAL_REGISTERS"])
        if not submission["MODBUS_ANALOG_REGISTERS"]:
            submission["MODBUS_ANALOG_REGISTERS"] = context_block.get("MODBUS_ANALOG_REGISTERS", submission["MODBUS_ANALOG_REGISTERS"])

        submission["MODBUS_DIGITAL_SIGNALS"] = context_block.get("MODBUS_DIGITAL_SIGNALS", submission["MODBUS_DIGITAL_SIGNALS"])
        submission["MODBUS_ANALOGUE_SIGNALS"] = context_block.get("MODBUS_ANALOGUE_SIGNALS", submission["MODBUS_ANALOGUE_SIGNALS"])

        if "SYSTEM_ARCHITECTURE_LAYOUT" in context_block and not submission.get("SYSTEM_ARCHITECTURE_LAYOUT"):
            try:
                submission["SYSTEM_ARCHITECTURE_LAYOUT"] = json.dumps(context_block["SYSTEM_ARCHITECTURE_LAYOUT"])
            except (TypeError, ValueError):
                current_app.logger.warning("Unable to serialise architecture layout from context for submission preload.")

        def _normalise_file_list(value):
            raw_items = []
            if isinstance(value, list):
                raw_items = value
            elif isinstance(value, str):
                candidate = value.strip()
                if candidate:
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, list):
                            raw_items = parsed
                        else:
                            raw_items = [candidate]
                    except Exception:
                        raw_items = [candidate]

            deduped = []
            seen = set()
            for item in raw_items:
                canonical = _canonical_static_url(item)
                if not canonical:
                    continue
                if canonical not in seen:
                    seen.add(canonical)
                    deduped.append(canonical)
            return deduped

        submission["SYSTEM_ARCHITECTURE_FILES"] = _normalise_file_list(context_block.get("SYSTEM_ARCHITECTURE_FILES"))
        submission["APPENDIX1_FILES"] = _normalise_file_list(context_block.get("APPENDIX1_FILES"))
        submission["APPENDIX2_FILES"] = _normalise_file_list(context_block.get("APPENDIX2_FILES"))
        submission["APPENDIX3_FILES"] = _normalise_file_list(context_block.get("APPENDIX3_FILES"))
        submission["APPENDIX4_FILES"] = _normalise_file_list(context_block.get("APPENDIX4_FILES"))
        submission["APPENDIX5_FILES"] = _normalise_file_list(context_block.get("APPENDIX5_FILES"))

        attachments_section = fds_payload.get("attachments", {}) or {}
        if attachments_section:
            submission["SYSTEM_ARCHITECTURE_FILES"] = submission["SYSTEM_ARCHITECTURE_FILES"] or _normalise_file_list(
                attachments_section.get("system_architecture_files")
            )
            submission["APPENDIX1_FILES"] = submission["APPENDIX1_FILES"] or _normalise_file_list(
                attachments_section.get("appendix1_files")
            )
            submission["APPENDIX2_FILES"] = submission["APPENDIX2_FILES"] or _normalise_file_list(
                attachments_section.get("appendix2_files")
            )
            submission["APPENDIX3_FILES"] = submission["APPENDIX3_FILES"] or _normalise_file_list(
                attachments_section.get("appendix3_files")
            )
            submission["APPENDIX4_FILES"] = submission["APPENDIX4_FILES"] or _normalise_file_list(
                attachments_section.get("appendix4_files")
            )
            submission["APPENDIX5_FILES"] = submission["APPENDIX5_FILES"] or _normalise_file_list(
                attachments_section.get("appendix5_files")
            )

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
        "MODBUS_ANALOGUE_SIGNALS": [],
        "SYSTEM_ARCHITECTURE_FILES": [],
        "APPENDIX1_FILES": [],
        "APPENDIX2_FILES": [],
        "APPENDIX3_FILES": [],
        "APPENDIX4_FILES": [],
        "APPENDIX5_FILES": []
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


@reports_bp.route('/system-architecture/layout/<submission_id>', methods=['PUT'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def update_system_architecture_layout(submission_id):
    """Persist a live-updated architecture layout snapshot."""
    report = Report.query.get(submission_id)
    _assert_report_access(report)

    payload = request.get_json(silent=True) or {}
    layout_payload = payload.get("layout", payload)
    note = payload.get("note")
    version_label = payload.get("version_label")

    if not isinstance(layout_payload, (dict, list, str)):
        return jsonify({
            "success": False,
            "message": "Invalid layout payload received."
        }), 400

    try:
        normalised_layout = ensure_layout(layout_payload)
    except Exception as exc:
        current_app.logger.warning("Failed to normalise architecture layout for %s: %s", submission_id, exc, exc_info=True)
        return jsonify({
            "success": False,
            "message": "Unable to process architecture layout."
        }), 400

    persist_layout(
        report,
        normalised_layout,
        created_by=current_user.email,
        note=note,
        version_label=version_label,
    )

    response = {
        "success": True,
        "payload": normalised_layout,
    }
    if version_label:
        latest_versions = list_versions(submission_id, limit=1)
        if latest_versions:
            response["version"] = latest_versions[0]

    return jsonify(response)


@reports_bp.route('/system-architecture/templates', methods=['GET'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def list_architecture_templates():
    """Return available architecture templates for the current user."""
    include_shared = request.args.get("include_shared", "1") != "0"
    owned_only = request.args.get("owned_only", "0") == "1"
    templates = list_templates(
        include_shared=include_shared and not owned_only,
        owned_by=current_user.email if owned_only else None,
    )
    if owned_only:
        templates = [
            template for template in templates
            if template.get("created_by") == current_user.email
            or template.get("updated_by") == current_user.email
        ]
    return jsonify({
        "success": True,
        "templates": templates,
    })


@reports_bp.route('/system-architecture/templates', methods=['POST'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def create_architecture_template():
    """Persist a new reusable architecture template."""
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "message": "Template name is required."}), 400

    layout_payload = payload.get("layout")
    if not layout_payload:
        return jsonify({"success": False, "message": "Template layout payload is required."}), 400

    description = (payload.get("description") or "").strip() or None
    category = (payload.get("category") or "").strip() or None
    is_shared = bool(payload.get("is_shared", True))

    try:
        normalised_layout = ensure_layout(layout_payload)
        template = save_template(
            name=name,
            layout=normalised_layout,
            user_email=current_user.email,
            description=description,
            category=category,
            is_shared=is_shared,
            template_id=None,
        )
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    return jsonify({
        "success": True,
        "template": template.to_dict(include_layout=True),
    }), 201


@reports_bp.route('/system-architecture/templates/<int:template_id>', methods=['GET'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def get_architecture_template(template_id: int):
    """Fetch a template, including the layout payload."""
    payload = fetch_template(template_id, include_layout=True)
    if not payload:
        return jsonify({"success": False, "message": "Template not found."}), 404
    return jsonify({"success": True, "template": payload})


@reports_bp.route('/system-architecture/templates/<int:template_id>', methods=['PUT'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def update_architecture_template(template_id: int):
    """Update an existing template."""
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip() or None
    category = (payload.get("category") or "").strip() or None
    is_shared = bool(payload.get("is_shared", True))
    layout_payload = payload.get("layout")

    existing_template = fetch_template(template_id, include_layout=True)
    if not existing_template:
        return jsonify({"success": False, "message": "Template not found."}), 404

    try:
        normalised_layout = ensure_layout(layout_payload) if layout_payload else None
        template = save_template(
            name=name or existing_template.get("name") or f"Template {template_id}",
            layout=normalised_layout or existing_template.get("layout") or {},
            user_email=current_user.email,
            description=description,
            category=category,
            is_shared=is_shared,
            template_id=template_id,
        )
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    return jsonify({"success": True, "template": template.to_dict(include_layout=True)})


@reports_bp.route('/system-architecture/templates/<int:template_id>', methods=['DELETE'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def delete_architecture_template(template_id: int):
    """Remove a template."""
    success = delete_template(template_id)
    if not success:
        return jsonify({"success": False, "message": "Template not found."}), 404
    return jsonify({"success": True})


@reports_bp.route('/system-architecture/versions/<submission_id>', methods=['GET'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def list_architecture_versions(submission_id: str):
    """Return version history for a submission."""
    report = Report.query.get(submission_id)
    _assert_report_access(report)

    limit_param = request.args.get("limit")
    try:
        limit = max(1, min(100, int(limit_param))) if limit_param else 20
    except ValueError:
        limit = 20

    versions = list_versions(submission_id, limit=limit)
    return jsonify({"success": True, "versions": versions})


@reports_bp.route('/system-architecture/versions/<submission_id>/<int:version_id>', methods=['GET'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def get_architecture_version(submission_id: str, version_id: int):
    """Return a specific version payload."""
    report = Report.query.get(submission_id)
    _assert_report_access(report)

    payload = fetch_version(version_id)
    if not payload or payload.get("report_id") != submission_id:
        return jsonify({"success": False, "message": "Version not found."}), 404
    return jsonify({"success": True, "version": payload})


@reports_bp.route('/system-architecture/versions/<submission_id>', methods=['POST'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def create_architecture_version(submission_id: str):
    """Create a manual snapshot of the current layout."""
    report = Report.query.get(submission_id)
    _assert_report_access(report)

    payload = request.get_json(silent=True) or {}
    layout_payload = payload.get("layout")
    note = payload.get("note")
    version_label = payload.get("version_label")

    if not layout_payload:
        fds_report = report.fds_report
        layout_payload = fds_report.get_system_architecture() if fds_report else {}
        if not layout_payload:
            return jsonify({"success": False, "message": "No layout found to snapshot."}), 400

    try:
        normalised_layout = ensure_layout(layout_payload)
    except Exception:
        return jsonify({"success": False, "message": "Invalid layout payload supplied."}), 400

    snapshot = record_version_snapshot(
        submission_id,
        normalised_layout,
        created_by=current_user.email,
        note=note,
        version_label=version_label,
    )
    if not snapshot:
        return jsonify({"success": False, "message": "Unable to record version snapshot."}), 500

    return jsonify({"success": True, "version": snapshot.to_dict(include_layout=True)}), 201


@reports_bp.route('/system-architecture/assets/library', methods=['GET'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def list_architecture_assets():
    """Return cached assets for the local asset library."""
    try:
        limit_param = request.args.get("limit")
        limit = max(0, min(500, int(limit_param))) if limit_param else 300
    except ValueError:
        limit = 300
    assets = list_cached_assets(limit=limit)
    return jsonify({"success": True, "assets": assets})


@reports_bp.route('/system-architecture/assets/upload', methods=['POST'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def upload_architecture_asset():
    """Upload a custom image to the asset library."""
    model_name = (request.form.get("model_name") or "").strip()
    asset_label = (request.form.get("asset_label") or "").strip()
    storage = request.files.get("file")

    if not storage:
        return jsonify({"success": False, "message": "No file supplied for upload."}), 400

    try:
        asset = save_user_asset_image(
            model_name,
            storage,
            user_email=current_user.email,
            display_name=asset_label or model_name
        )
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        current_app.logger.error("Asset upload failed: %s", exc, exc_info=True)
        return jsonify({"success": False, "message": "Unable to upload asset image."}), 500

    return jsonify({"success": True, "asset": asset}), 201


@reports_bp.route('/system-architecture/live/<submission_id>', methods=['GET'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'PM', 'Admin'])
def poll_architecture_updates(submission_id: str):
    """
    Poll for architecture updates since a timestamp to support lightweight collaboration.
    """
    report = Report.query.get(submission_id)
    _assert_report_access(report)

    since_param = request.args.get("since")
    since_dt = None
    if since_param:
        try:
            since_dt = datetime.fromisoformat(since_param)
        except ValueError:
            since_dt = None
    query = SystemArchitectureVersion.query.filter_by(report_id=submission_id)
    if since_dt:
        query = query.filter(SystemArchitectureVersion.created_at > since_dt)
    updates = (
        query.order_by(SystemArchitectureVersion.created_at.asc())
        .limit(25)
        .all()
    )

    updates_payload = [version.to_dict(include_layout=True) for version in updates]
    for update in updates_payload:
        layout_payload = update.get("layout") or update.get("layout_raw")
        if isinstance(layout_payload, str):
            try:
                layout_payload = json.loads(layout_payload)
            except Exception:
                layout_payload = None
        if layout_payload:
            try:
                update["layout"] = ensure_layout(layout_payload)
            except Exception:
                update["layout"] = layout_payload
        update.pop("layout_raw", None)

    latest_layout = None
    if updates_payload:
        latest_layout = updates_payload[-1].get("layout")
    else:
        fds_report = report.fds_report
        stored_layout = fds_report.get_system_architecture() if fds_report else None
        if stored_layout:
            try:
                latest_layout = ensure_layout(stored_layout)
            except Exception:
                latest_layout = stored_layout

    if isinstance(latest_layout, str):
        try:
            latest_layout = json.loads(latest_layout)
        except Exception:
            pass

    return jsonify({
        "success": True,
        "updates": updates_payload,
        "latest": latest_layout,
        "timestamp": datetime.utcnow().isoformat(),
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

        fds_report = FDSReport.query.filter_by(report_id=submission_id).first()
        existing_payload = {}
        if fds_report and fds_report.data_json:
            try:
                existing_payload = json.loads(fds_report.data_json)
            except json.JSONDecodeError:
                current_app.logger.warning(
                    "Unable to parse existing FDS JSON for submission %s; continuing with defaults",
                    submission_id
                )
                existing_payload = {}
        existing_context = {}
        if isinstance(existing_payload, dict):
            existing_context = existing_payload.get("context", {}) or {}

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
        if architecture_layout:
            try:
                architecture_layout = ensure_layout(architecture_layout, equipment_rows=equipment_rows)
            except Exception as exc:
                current_app.logger.warning("Failed to normalise architecture layout for submission %s: %s", submission_id, exc, exc_info=True)

        upload_root_cfg = current_app.config.get('UPLOAD_ROOT')
        if not isinstance(upload_root_cfg, str) or not upload_root_cfg:
            static_root = current_app.static_folder or os.path.join(current_app.root_path, 'static')
            upload_root_cfg = os.path.join(static_root, 'uploads')
        upload_dir = os.path.join(upload_root_cfg, submission_id)
        os.makedirs(upload_dir, exist_ok=True)

        def normalise_urls(value):
            """Normalise and return a list of attachment URLs."""
            raw_items = []
            if isinstance(value, list):
                raw_items = value
            elif isinstance(value, str):
                if value.strip():
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            raw_items = parsed
                        else:
                            raw_items = [value]
                    except Exception:
                        raw_items = [value]

            normalised = []
            for item in raw_items:
                normalised_value = _canonical_static_url(item)
                if normalised_value:
                    normalised.append(normalised_value)
            return normalised

        def dedupe(items):
            seen = set()
            ordered = []
            for item in items:
                normalised_value = _canonical_static_url(item)
                if normalised_value and normalised_value not in seen:
                    seen.add(normalised_value)
                    ordered.append(normalised_value)
            return ordered

        architecture_files = dedupe(normalise_urls(existing_context.get("SYSTEM_ARCHITECTURE_FILES")))
        appendix1_files = dedupe(normalise_urls(existing_context.get("APPENDIX1_FILES")))
        appendix2_files = dedupe(normalise_urls(existing_context.get("APPENDIX2_FILES")))
        appendix3_files = dedupe(normalise_urls(existing_context.get("APPENDIX3_FILES")))
        appendix4_files = dedupe(normalise_urls(existing_context.get("APPENDIX4_FILES")))
        appendix5_files = dedupe(normalise_urls(existing_context.get("APPENDIX5_FILES")))

        def append_file(field_name, url_list, allow_docs=True):
            for storage in request.files.getlist(field_name):
                if not storage or not storage.filename:
                    continue
                try:
                    filename = secure_filename(storage.filename)
                    if not filename:
                        continue
                    lower_name = filename.lower()
                    if not allow_docs and lower_name.endswith('.pdf'):
                        continue
                    unique_name = f"{uuid.uuid4().hex}_{filename}"
                    file_path = os.path.join(upload_dir, unique_name)
                    storage.save(file_path)
                    rel_path = os.path.join("uploads", submission_id, unique_name).replace("\\", "/")
                    url = url_for("static", filename=rel_path)
                    normalised_url = _canonical_static_url(url)
                    if normalised_url and normalised_url not in url_list:
                        url_list.append(normalised_url)
                except Exception as exc:
                    current_app.logger.error(
                        "Failed to store attachment %s for submission %s: %s",
                        storage.filename,
                        submission_id,
                        exc,
                        exc_info=True
                    )

        handle_image_removals(request.form, "removed_architecture_files", architecture_files)
        handle_image_removals(request.form, "removed_appendix1_files", appendix1_files)
        handle_image_removals(request.form, "removed_appendix2_files", appendix2_files)
        handle_image_removals(request.form, "removed_appendix3_files", appendix3_files)
        handle_image_removals(request.form, "removed_appendix4_files", appendix4_files)
        handle_image_removals(request.form, "removed_appendix5_files", appendix5_files)

        append_file("architecture_files[]", architecture_files, allow_docs=False)
        append_file("appendix1_files[]", appendix1_files, allow_docs=True)
        append_file("appendix2_files[]", appendix2_files, allow_docs=True)
        append_file("appendix3_files[]", appendix3_files, allow_docs=True)
        append_file("appendix4_files[]", appendix4_files, allow_docs=True)
        append_file("appendix5_files[]", appendix5_files, allow_docs=True)

        prepared_block = approvals[0] if len(approvals) > 0 else {}
        reviewer1_block = approvals[1] if len(approvals) > 1 else {}
        reviewer2_block = approvals[2] if len(approvals) > 2 else {}
        client_block = approvals[3] if len(approvals) > 3 else {}

        context = {
            "DOCUMENT_TITLE": document_header.get("document_title", ""),
            "PROJECT_REFERENCE": document_header.get("project_reference", ""),
            "DOCUMENT_REFERENCE": document_header.get("document_reference", ""),
            "DATE": document_header.get("date", ""),
            "PREPARED_FOR": document_header.get("prepared_for", ""),
            "REVISION": document_header.get("revision", ""),
            "REVISION_DETAILS": document_header.get("revision_details", ""),
            "REVISION_DATE": document_header.get("revision_date", ""),
            "USER_EMAIL": document_header.get("user_email", ""),
            "PREPARED_BY_NAME": prepared_block.get("name", ""),
            "PREPARED_BY_ROLE": prepared_block.get("role", ""),
            "PREPARED_BY_DATE": prepared_block.get("date", ""),
            "PREPARED_BY_EMAIL": prepared_block.get("email", ""),
            "REVIEWER1_NAME": reviewer1_block.get("name", ""),
            "REVIEWER1_ROLE": reviewer1_block.get("role", ""),
            "REVIEWER1_DATE": reviewer1_block.get("date", ""),
            "REVIEWER1_EMAIL": reviewer1_block.get("email", ""),
            "REVIEWER2_NAME": reviewer2_block.get("name", ""),
            "REVIEWER2_ROLE": reviewer2_block.get("role", ""),
            "REVIEWER2_DATE": reviewer2_block.get("date", ""),
            "REVIEWER2_EMAIL": reviewer2_block.get("email", ""),
            "CLIENT_APPROVAL_NAME": client_block.get("name", ""),
            "CLIENT_APPROVAL_DATE": client_block.get("date", ""),
            "CLIENT_APPROVAL_EMAIL": client_block.get("email", ""),
            "VERSION_HISTORY": version_history,
            "CONFIDENTIALITY_NOTICE": request.form.get('confidentiality_notice', '').strip(),
            "SYSTEM_OVERVIEW": request.form.get('system_overview', ''),
            "SYSTEM_PURPOSE": purpose_html or request.form.get('system_purpose', ''),
            "SCOPE_OF_WORK": scope_of_work_value,
            "FUNCTIONAL_REQUIREMENTS": request.form.get('functional_requirements', ''),
            "PROCESS_DESCRIPTION": request.form.get('process_description', ''),
            "CONTROL_PHILOSOPHY": request.form.get('control_philosophy', ''),
            "DIGITAL_SIGNALS": digital_signals_rows,
            "ANALOGUE_INPUT_SIGNALS": analogue_input_rows,
            "ANALOGUE_OUTPUT_SIGNALS": analogue_output_rows,
            "DIGITAL_OUTPUT_SIGNALS": digital_output_rows,
            "MODBUS_DIGITAL_SIGNALS": modbus_digital_signal_rows,
            "MODBUS_ANALOGUE_SIGNALS": modbus_analogue_signal_rows,
            "MODBUS_DIGITAL_REGISTERS": modbus_digital_rows,
            "MODBUS_ANALOG_REGISTERS": modbus_analog_rows,
            "COMMUNICATION_PROTOCOLS": protocol_rows,
            "EQUIPMENT_LIST": equipment_rows,
            "DETAILED_IO_LIST": detailed_io_rows,
        }

        if architecture_layout:
            context["SYSTEM_ARCHITECTURE_LAYOUT"] = architecture_layout
        context["SYSTEM_ARCHITECTURE_FILES"] = dedupe(architecture_files)
        context["APPENDIX1_FILES"] = dedupe(appendix1_files)
        context["APPENDIX2_FILES"] = dedupe(appendix2_files)
        context["APPENDIX3_FILES"] = dedupe(appendix3_files)
        context["APPENDIX4_FILES"] = dedupe(appendix4_files)
        context["APPENDIX5_FILES"] = dedupe(appendix5_files)

        fds_data = {
            "context": context,
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
        fds_data["attachments"] = {
            "system_architecture_files": context["SYSTEM_ARCHITECTURE_FILES"],
            "appendix1_files": context["APPENDIX1_FILES"],
            "appendix2_files": context["APPENDIX2_FILES"],
            "appendix3_files": context["APPENDIX3_FILES"],
            "appendix4_files": context["APPENDIX4_FILES"],
            "appendix5_files": context["APPENDIX5_FILES"],
        }

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


@reports_bp.route('/submit-site-survey', methods=['POST'])
@login_required
@role_required(['Engineer', 'Automation Manager', 'Admin'])
def submit_site_survey():
    """Persist a Site Survey form submission."""
    try:
        submission_id = (request.form.get('submission_id') or '').strip() or str(uuid.uuid4())

        report = Report.query.get(submission_id)
        is_new_report = False

        if not report:
            is_new_report = True
            report = Report(
                id=submission_id,
                type='SITE_SURVEY',
                status='DRAFT',
                user_email=current_user.email,
                created_at=datetime.utcnow(),
                approvals_json='[]'
            )
            db.session.add(report)
        else:
            report.type = 'SITE_SURVEY'
            report.status = 'DRAFT'
            report.locked = False

        report.document_title = request.form.get('document_title', '').strip() or 'Site Survey Report'
        report.project_reference = request.form.get('project_reference', '').strip()
        report.document_reference = request.form.get('document_reference', '').strip()
        report.client_name = request.form.get('prepared_for', '').strip()
        report.revision = request.form.get('revision', '').strip() or report.revision or 'R0'
        report.prepared_by = request.form.get('prepared_by_name', '').strip() or report.prepared_by
        report.updated_at = datetime.utcnow()

        if is_new_report and not report.version:
            report.version = report.revision or 'R0'

        submission_payload = {}
        for key in request.form.keys():
            if key == 'csrf_token':
                continue
            values = request.form.getlist(key)
            cleaned = [value.strip() if isinstance(value, str) else value for value in values]
            submission_payload[key] = cleaned[0] if len(cleaned) == 1 else [value for value in cleaned if value]

        submission_payload['submission_id'] = submission_id
        submission_payload['saved_at'] = datetime.utcnow().isoformat()
        submission_payload['saved_by'] = current_user.email

        def extract_value(field_name):
            value = submission_payload.get(field_name)
            if isinstance(value, list):
                return ', '.join([item for item in value if item])
            return value or ''

        site_survey = SiteSurveyReport.query.filter_by(report_id=submission_id).first()
        if not site_survey:
            site_survey = SiteSurveyReport(report_id=submission_id)
            db.session.add(site_survey)

        site_survey.site_name = extract_value('site_name') or site_survey.site_name
        site_survey.site_location = extract_value('location_address') or site_survey.site_location
        site_survey.site_access_details = extract_value('site_access_details') or site_survey.site_access_details
        site_survey.area_engineer = extract_value('area_engineer') or site_survey.area_engineer
        site_survey.site_caretaker = extract_value('site_caretaker') or site_survey.site_caretaker
        site_survey.survey_completed_by = extract_value('prepared_by_name') or site_survey.survey_completed_by
        site_survey.network_configuration = extract_value('network_configuration') or site_survey.network_configuration
        site_survey.mobile_signal_strength = extract_value('mobile_signal_strength') or site_survey.mobile_signal_strength
        site_survey.local_scada_details = extract_value('local_scada_details') or site_survey.local_scada_details
        site_survey.verification_checklist = extract_value('verification_checklist') or site_survey.verification_checklist
        site_survey.data_json = json.dumps(submission_payload)

        db.session.commit()

        response_payload = {
            "success": True,
            "message": "Site survey draft saved successfully.",
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
        current_app.logger.error(f"Error saving site survey report: {exc}", exc_info=True)
        db.session.rollback()
        error_message = 'Failed to save Site Survey report.'
        wants_json = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
        )
        if wants_json:
            return jsonify({"success": False, "message": error_message}), 500

        flash(error_message, 'error')
        return redirect(url_for('reports.new_site_survey'))


