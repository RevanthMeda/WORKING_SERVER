
import json
from flask import current_app
from services.ai_service import fetch_datasheet

def generate_fds_from_sat(sat_report_data: dict) -> dict:
    """
    Generates a Functional Design Specification (FDS) from a System Acceptance Test (SAT) report.

    Args:
        sat_report_data: A dictionary containing the SAT report data.

    Returns:
        A dictionary representing the generated FDS.
    """
    current_app.logger.info("Starting FDS generation from SAT data.")

    fds_data = {
        "document_header": {},
        "system_overview": {},
        "equipment_and_hardware": {
            "equipment_list": [],
        },
        "io_signal_mapping": {
            "digital_signals": [],
            "analog_signals": [],
        },
        "communication_and_modbus": {
            "modbus_digital_registers": [],
            "modbus_analog_registers": [],
        },
        "ai_enhancements": {}
    }

    context = sat_report_data.get("context", {})

    # 1. Core Document Information Fields
    fds_data["document_header"] = {
        "project_reference": context.get("PROJECT_REFERENCE"),
        "document_title": f"Functional Design Specification for {context.get('PROJECT_REFERENCE', '')}",
        "date": "System-generated current date",  # Placeholder
        "prepared_for": context.get("CLIENT_NAME"),
        "prepared_by": context.get("PREPARED_BY"),
        "reviewers": context.get("REVIEWED_BY_TECH_LEAD"), # Simplified for now
    }

    # 2. System Overview Fields
    fds_data["system_overview"] = {
        "purpose": context.get("PURPOSE"),
        "scope_of_work": context.get("SCOPE"),
        "system_architecture": "Based on SAT asset register and network configuration", # Placeholder
    }

    # 3. Equipment and Hardware Integration
    key_components = context.get("KEY_COMPONENTS", [])
    for idx, component in enumerate(key_components, start=1):
        model_number = (
            component.get("model_number")
            or component.get("Model")
            or component.get("MODEL")
            or component.get("model")
        )
        datasheet_url = fetch_datasheet(model_number)
        fds_data["equipment_and_hardware"]["equipment_list"].append({
            "S_No": component.get("S_No") or component.get("s_no") or str(idx),
            "model_number": model_number,
            "description": component.get("description") or component.get("Description"),
            "quantity": component.get("quantity") or component.get("Quantity") or "",
            "remarks": component.get("remarks") or component.get("Remarks") or "Generated from SAT",
            "datasheet_url": datasheet_url,
        })

    # 4. I/O Signal Mapping
    digital_signals = context.get("DIGITAL_SIGNALS", [])
    fds_data["io_signal_mapping"]["digital_signals"] = digital_signals

    analog_inputs = context.get("ANALOGUE_INPUT_SIGNALS", [])
    analog_outputs = context.get("ANALOGUE_OUTPUT_SIGNALS", [])
    fds_data["io_signal_mapping"]["analog_signals"] = analog_inputs + analog_outputs

    # 5. Communication and Modbus Integration
    modbus_digital = context.get("MODBUS_DIGITAL_SIGNALS", [])
    fds_data["communication_and_modbus"]["modbus_digital_registers"] = modbus_digital

    modbus_analog = context.get("MODBUS_ANALOGUE_SIGNALS", [])
    fds_data["communication_and_modbus"]["modbus_analog_registers"] = modbus_analog
    
    current_app.logger.info("FDS generation complete.")
    return fds_data
