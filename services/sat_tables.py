from __future__ import annotations

from typing import Dict, List, Any

from werkzeug.datastructures import ImmutableMultiDict

from utils import process_table_rows

TableRow = Dict[str, str]
UITableMap = Dict[str, List[TableRow]]
DocTableMap = Dict[str, List[TableRow]]


TABLE_CONFIG = [
    {
        "ui_section": "RELATED_DOCUMENTS",
        "doc_section": "RELATED_DOCUMENTS",
        "fields": [
            {"form": "doc_ref[]", "ui": "Document_Reference", "doc": "Document_Reference"},
            {"form": "doc_title[]", "ui": "Document_Title", "doc": "Document_Title"},
        ],
    },
    {
        "ui_section": "PRE_EXECUTION_APPROVAL",
        "doc_section": "PRE_APPROVALS",
        "fields": [
            {"form": "pre_approval_print_name[]", "ui": "Print_Name", "doc": "Print_Name"},
            {"form": "pre_approval_signature[]", "ui": "Signature", "doc": "Signature"},
            {"form": "pre_approval_date[]", "ui": "Date", "doc": "Date"},
            {"form": "pre_approval_initial[]", "ui": "Initial", "doc": "Initial"},
            {"form": "pre_approval_company[]", "ui": "Company", "doc": "Company"},
        ],
    },
    {
        "ui_section": "POST_EXECUTION_APPROVAL",
        "doc_section": "POST_APPROVALS",
        "fields": [
            {"form": "post_approval_print_name[]", "ui": "Print_Name", "doc": "Print_Name"},
            {"form": "post_approval_signature[]", "ui": "Signature", "doc": "Signature"},
            {"form": "post_approval_date[]", "ui": "Date", "doc": "Date"},
            {"form": "post_approval_initial[]", "ui": "Initial", "doc": "Initial"},
            {"form": "post_approval_company[]", "ui": "Company", "doc": "Company"},
        ],
    },
    {
        "ui_section": "PRE_TEST_REQUIREMENTS",
        "doc_section": "PRE_TEST_REQUIREMENTS",
        "fields": [
            {"form": "pretest_item[]", "ui": "Item", "doc": "Item"},
            {"form": "pretest_test[]", "ui": "Test", "doc": "Test"},
            {"form": "pretest_method[]", "ui": "Method_Test_Steps", "doc": "Method/Test Steps", "aliases": ["Method_Test_Steps"]},
            {"form": "pretest_acceptance[]", "ui": "Acceptance_Criteria", "doc": "Acceptance Criteria", "aliases": ["Acceptance_Criteria"]},
            {"form": "pretest_result[]", "ui": "Result", "doc": "Result"},
            {"form": "pretest_punch[]", "ui": "Punch_Item", "doc": "Punch Item", "aliases": ["Punch_Item"]},
            {"form": "pretest_verified_by[]", "ui": "Verified_by", "doc": "Verified by", "aliases": ["Verified_by"]},
            {"form": "pretest_comment[]", "ui": "Comment", "doc": "Comment"},
        ],
    },
    {
        "ui_section": "KEY_COMPONENTS",
        "doc_section": "KEY_COMPONENTS",
        "fields": [
            {"form": "component_sno[]", "ui": "S_No", "doc": "S_no", "aliases": ["S.no", "S. no", "S. No.", "S_No"]},
            {"form": "component_model[]", "ui": "Model", "doc": "Model"},
            {"form": "component_description[]", "ui": "Description", "doc": "Description"},
            {"form": "component_remarks[]", "ui": "Remarks", "doc": "Remarks"},
        ],
    },
    {
        "ui_section": "IP_RECORDS",
        "doc_section": "IP_RECORDS",
        "fields": [
            {"form": "ip_device[]", "ui": "Device_Name", "doc": "Device_Name"},
            {"form": "ip_address[]", "ui": "IP_Address", "doc": "IP_Address"},
            {"form": "ip_comment[]", "ui": "Comment", "doc": "Comment"},
        ],
    },
    {
        "ui_section": "DIGITAL_SIGNALS",
        "doc_section": "SIGNAL_LISTS",
        "fields": [
            {"form": "digital_s_no[]", "ui": "S_No", "doc": "S. No.", "aliases": ["S.no", "S_No"]},
            {"form": "digital_rack[]", "ui": "Rack", "doc": "Rack No.", "aliases": ["Rack No.", "Rack_No"]},
            {"form": "digital_pos[]", "ui": "Pos", "doc": "Module Position", "aliases": ["Module Position", "Position"]},
            {"form": "digital_signal_tag[]", "ui": "Signal_TAG", "doc": "Signal TAG", "aliases": ["Signal_TAG", "Signal Tag"]},
            {"form": "digital_description[]", "ui": "Description", "doc": "Signal Description", "aliases": ["Signal Description"]},
            {"form": "digital_result[]", "ui": "Result", "doc": "Result"},
            {"form": "digital_punch[]", "ui": "Punch", "doc": "Punch Item", "aliases": ["Punch Item", "Punch_Item"]},
            {"form": "digital_verified[]", "ui": "Verified", "doc": "Verified By", "aliases": ["Verified By", "Verified_by"]},
            {"form": "digital_comment[]", "ui": "Comment", "doc": "Comment"},
        ],
    },
    {
        "ui_section": "ANALOGUE_INPUT_SIGNALS",
        "doc_section": "ANALOGUE_LISTS",
        "fields": [
            {"form": "analogue_input_s_no[]", "ui": "S_No", "doc": "S. No.", "aliases": ["S.no", "S_No"]},
            {"form": "analogue_input_rack_no[]", "ui": "Rack_No", "doc": "Rack No.", "aliases": ["Rack No."]},
            {"form": "analogue_input_module_position[]", "ui": "Module_Position", "doc": "Module Position", "aliases": ["Module Position"]},
            {"form": "analogue_input_signal_tag[]", "ui": "Signal_TAG", "doc": "Signal TAG", "aliases": ["Signal TAG"]},
            {"form": "analogue_input_description[]", "ui": "Description", "doc": "Signal Description", "aliases": ["Signal Description"]},
            {"form": "analogue_input_result[]", "ui": "Result", "doc": "Result"},
            {"form": "analogue_input_punch_item[]", "ui": "Punch_Item", "doc": "Punch Item", "aliases": ["Punch Item"]},
            {"form": "analogue_input_verified_by[]", "ui": "Verified_by", "doc": "Verified By", "aliases": ["Verified By"]},
            {"form": "analogue_input_comment[]", "ui": "Comment", "doc": "Comment"},
        ],
    },
    {
        "ui_section": "ANALOGUE_OUTPUT_SIGNALS",
        "doc_section": "ANALOGUE_OUTPUT_LISTS",
        "fields": [
            {"form": "analogue_output_s_no[]", "ui": "S_No", "doc": "S. No.", "aliases": ["S_No", "S.no", "S. No."]},
            {"form": "analogue_output_rack_no[]", "ui": "Rack_No", "doc": "Rack No.", "aliases": ["Rack_No", "Rack No."]},
            {"form": "analogue_output_module_position[]", "ui": "Module_Position", "doc": "Module Position", "aliases": ["Module_Position", "Module Position"]},
            {"form": "analogue_output_signal_tag[]", "ui": "Signal_TAG", "doc": "Signal TAG", "aliases": ["Signal_TAG", "Signal TAG"]},
            {"form": "analogue_output_description[]", "ui": "Description", "doc": "Signal Description", "aliases": ["Description", "Signal Description"]},
            {"form": "analogue_output_result[]", "ui": "Result", "doc": "Result"},
            {"form": "analogue_output_punch_item[]", "ui": "Punch_Item", "doc": "Punch Item", "aliases": ["Punch_Item", "Punch Item"]},
            {"form": "analogue_output_verified_by[]", "ui": "Verified_by", "doc": "Verified By", "aliases": ["Verified_by", "Verified By"]},
            {"form": "analogue_output_comment[]", "ui": "Comment", "doc": "Comment"},
        ],
    },
    {
        "ui_section": "DIGITAL_OUTPUT_SIGNALS",
        "doc_section": "DIGITAL_OUTPUT_LISTS",
        "doc_section_aliases": ["DIGITAL_OUTPUT_SIGNALS"],
        "fields": [
            {"form": "digital_output_s_no[]", "ui": "S_No", "doc": "S. No.", "aliases": ["S_No", "S.no", "S. No."]},
            {"form": "digital_output_rack_no[]", "ui": "Rack_No", "doc": "Rack No.", "aliases": ["Rack_No", "Rack No."]},
            {"form": "digital_output_module_position[]", "ui": "Module_Position", "doc": "Module Position", "aliases": ["Module_Position", "Module Position"]},
            {"form": "digital_output_signal_tag[]", "ui": "Signal_TAG", "doc": "Signal TAG", "aliases": ["Signal_TAG", "Signal TAG"]},
            {"form": "digital_output_description[]", "ui": "Description", "doc": "Signal Description", "aliases": ["Description", "Signal Description"]},
            {"form": "digital_output_result[]", "ui": "Result", "doc": "Result"},
            {"form": "digital_output_punch_item[]", "ui": "Punch_Item", "doc": "Punch Item", "aliases": ["Punch_Item", "Punch Item"]},
            {"form": "digital_output_verified_by[]", "ui": "Verified_by", "doc": "Verified By", "aliases": ["Verified_by", "Verified By"]},
            {"form": "digital_output_comment[]", "ui": "Comment", "doc": "Comment"},
        ],
    },
    {
        "ui_section": "MODBUS_DIGITAL_SIGNALS",
        "doc_section": "MODBUS_DIGITAL_LISTS",
        "fields": [
            {"form": "modbus_digital_address[]", "ui": "Address", "doc": "Address"},
            {"form": "modbus_digital_description[]", "ui": "Description", "doc": "Description"},
            {"form": "modbus_digital_remarks[]", "ui": "Remarks", "doc": "Remarks"},
            {"form": "modbus_digital_result[]", "ui": "Result", "doc": "Result"},
            {"form": "modbus_digital_punch_item[]", "ui": "Punch_Item", "doc": "Punch Item", "aliases": ["Punch Item"]},
            {"form": "modbus_digital_verified_by[]", "ui": "Verified_by", "doc": "Verified By", "aliases": ["Verified By"]},
            {"form": "modbus_digital_comment[]", "ui": "Comment", "doc": "Comment"},
        ],
    },
    {
        "ui_section": "MODBUS_ANALOGUE_SIGNALS",
        "doc_section": "MODBUS_ANALOGUE_LISTS",
        "fields": [
            {"form": "modbus_analogue_address[]", "ui": "Address", "doc": " Address", "aliases": ["Address", " Address"]},
            {"form": "modbus_analogue_description[]", "ui": "Description", "doc": "Description"},
            {"form": "modbus_analogue_range[]", "ui": "Range", "doc": "Range"},
            {"form": "modbus_analogue_result[]", "ui": "Result", "doc": "Result"},
            {"form": "modbus_analogue_punch_item[]", "ui": "Punch_Item", "doc": "Punch Item", "aliases": ["Punch Item", "Punch_Item"]},
            {"form": "modbus_analogue_verified_by[]", "ui": "Verified_by", "doc": "Verified By", "aliases": ["Verified By", "Verified_by"]},
            {"form": "modbus_analogue_comment[]", "ui": "Comment", "doc": "Comment"},
        ],
    },
    {
        "ui_section": "DATA_VALIDATION",
        "doc_section": "DATA_VALIDATION",
        "fields": [
            {"form": "data_validation_tag[]", "ui": "Tag", "doc": "Tag"},
            {"form": "data_validation_range[]", "ui": "Range", "doc": "Range"},
            {"form": "data_validation_scada_value[]", "ui": "SCADA Value", "doc": "SCADA Value", "aliases": ["SCADA_Value"]},
            {"form": "data_validation_hmi_value[]", "ui": "HMI Value", "doc": "HMI Value", "aliases": ["HMI_Value"]},
        ],
    },
    {
        "ui_section": "PROCESS_TEST",
        "doc_section": "PROCESS_TEST",
        "fields": [
            {"form": "Process_Item[]", "ui": "Item", "doc": "Item"},
            {"form": "Process_Action[]", "ui": "Action", "doc": "Action"},
            {"form": "Process_Expected / Required Result[]", "ui": "Expected / Required Result", "doc": "Expected / Required Result"},
            {"form": "Process_Pass/Fail[]", "ui": "Pass/Fail", "doc": " Pass/Fail ", "aliases": ["Pass/Fail", " Pass/Fail "]},
            {"form": "Process_Comments[]", "ui": "Comments", "doc": " Comments ", "aliases": ["Comments", " Comments "]},
        ],
    },
    {
        "ui_section": "SCADA_VERIFICATION",
        "doc_section": "SCADA_VERIFICATION",
        "fields": [
            {"form": "SCADA_Task[]", "ui": "Task", "doc": "Task"},
            {"form": "SCADA_Expected_Result[]", "ui": "Expected Result", "doc": "Expected Result"},
            {"form": "SCADA_Pass/Fail[]", "ui": "Pass/Fail", "doc": "Pass/Fail"},
            {"form": "SCADA_Comments[]", "ui": "Comments", "doc": "Comments"},
        ],
    },
    {
        "ui_section": "TRENDS_TESTING",
        "doc_section": "TRENDS_TESTING",
        "fields": [
            {"form": "Trend[]", "ui": "Trend", "doc": "Trend"},
            {"form": "Expected Behavior[]", "ui": "Expected Behavior", "doc": "Expected Behavior"},
            {"form": "Pass/Fail Trend[]", "ui": "Pass/Fail", "doc": "Pass/Fail"},
            {"form": "Comments Trend[]", "ui": "Comments", "doc": "Comments"},
        ],
    },
    {
        "ui_section": "ALARM_LIST",
        "doc_section": "ALARM_LIST",
        "fields": [
            {"form": "Alarm_Type[]", "ui": "Alarm Type", "doc": "Alarm Type"},
            {"form": "Expected / Required Result[]", "ui": "Expected / Required Result", "doc": " Expected / Required Result"},
            {"form": "Pass/Fail []", "ui": "Pass/Fail", "doc": " Pass/Fail ", "aliases": ["Pass/Fail"]},
            {"form": "Comments []", "ui": "Comments", "doc": " Comments ", "aliases": ["Comments"]},
        ],
    },
]


def extract_ui_tables(form_data: ImmutableMultiDict[str, str]) -> UITableMap:
    tables: UITableMap = {}
    for section in TABLE_CONFIG:
        mapping = {field["form"]: field["ui"] for field in section["fields"]}
        rows = process_table_rows(form_data, mapping, add_placeholder=False)
        tables[section["ui_section"]] = rows
    return tables


def build_doc_tables(ui_tables: UITableMap) -> DocTableMap:
    doc_tables: DocTableMap = {}
    for section in TABLE_CONFIG:
        ui_section = section["ui_section"]
        doc_section = section["doc_section"]
        ui_rows = ui_tables.get(ui_section, [])
        if not ui_rows:
            continue

        converted: List[TableRow] = []
        for row in ui_rows:
            doc_row: TableRow = {}
            for field in section["fields"]:
                ui_key = field["ui"]
                doc_key = field["doc"]
                value = row.get(ui_key, "")
                doc_row[doc_key] = value
            if any(doc_row.values()):
                converted.append(doc_row)

        if not converted:
            continue

        doc_tables.setdefault(doc_section, [])
        doc_tables[doc_section].extend(converted)
    return doc_tables


def migrate_context_tables(context: Dict[str, Any]) -> Dict[str, Any]:
    if not context:
        return {}

    updated = dict(context)
    for section in TABLE_CONFIG:
        ui_section = section["ui_section"]
        doc_section = section["doc_section"]

        ui_rows = updated.get(ui_section)
        if ui_rows:
            updated[ui_section] = [_normalize_row(row, section) for row in ui_rows]
            continue

        doc_rows = updated.get(doc_section)
        if not doc_rows:
            for alias_section in section.get('doc_section_aliases', []):
                alias_rows = updated.get(alias_section)
                if alias_rows:
                    doc_rows = alias_rows
                    break
        if doc_rows:
            updated[ui_section] = [_convert_doc_row(row, section) for row in doc_rows]
            if section.get('doc_section_aliases') and doc_section not in updated:
                updated[doc_section] = doc_rows
        else:
            updated.setdefault(ui_section, [])

    return updated


def build_doc_tables_from_context(context: Dict[str, Any]) -> DocTableMap:
    ui_tables = migrate_context_tables(context)
    return build_doc_tables(ui_tables)


def _normalize_row(row: Dict[str, Any], section: Dict[str, Any]) -> TableRow:
    normalized: TableRow = {}
    for field in section["fields"]:
        ui_key = field["ui"]
        value = row.get(ui_key)
        if value is None:
            # Try doc key or aliases for legacy data
            value = row.get(field["doc"], "")
            for alias in field.get("aliases", []):
                if value:
                    break
                value = row.get(alias, "")
        normalized[ui_key] = _coerce_to_str(value)
    return normalized


def _convert_doc_row(row: Dict[str, Any], section: Dict[str, Any]) -> TableRow:
    converted: TableRow = {}
    for field in section["fields"]:
        value = row.get(field["doc"], "")
        if not value:
            value = row.get(field["ui"], "")
        if not value:
            for alias in field.get("aliases", []):
                value = row.get(alias, "")
                if value:
                    break
        converted[field["ui"]] = _coerce_to_str(value)
    return converted


def _coerce_to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)
