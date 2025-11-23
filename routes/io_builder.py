from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_required, current_user
import requests
from bs4 import BeautifulSoup
import re
from models import db, ModuleSpec
import time
from urllib.parse import quote
import logging

io_builder_bp = Blueprint('io_builder', __name__)

def get_unread_count():
    """Get unread notifications count with error handling"""
    try:
        from models import Notification
        return Notification.query.filter_by(
            user_email=current_user.email, 
            read=False
        ).count()
    except Exception as e:
        current_app.logger.warning(f"Could not get unread count: {e}")
        return 0

@io_builder_bp.route('/')
@login_required
def index():
    """IO Builder main page"""
    try:
        unread_count = get_unread_count()
        return render_template('io_builder.html', unread_count=unread_count)
    except Exception as e:
        current_app.logger.error(f"Error rendering io_builder index: {e}")
        return render_template('io_builder.html', unread_count=0)

def get_comprehensive_module_database():
    """Comprehensive database of industrial I/O modules"""
    return {
        # ABB Modules - Comprehensive List
        'ABB_DA501': {
            'description': 'ABB DA501 - 16 Channel Digital Input, 24VDC; 4 Analog Input, U, I, RTD; 2 Analog Output, U, I; 8 Configurable DI/DO, 24VDC 0.5A',
            'digital_inputs': 24,  # 16 fixed DI + 8 configurable as DI
            'digital_outputs': 8,  # 8 configurable as DO
            'analog_inputs': 4,
            'analog_outputs': 2,
            'voltage_range': '24 VDC',
            'current_range': '4-20mA',
            'signal_type': 'Mixed',
            'verified': True
        },
        'DA501': {
            'description': 'DA501 - 16 Channel Digital Input, 24VDC; 4 Analog Input, U, I, RTD; 2 Analog Output, U, I; 8 Configurable DI/DO, 24VDC 0.5A',
            'digital_inputs': 24,
            'digital_outputs': 8,
            'analog_inputs': 4,
            'analog_outputs': 2,
            'voltage_range': '24 VDC',
            'current_range': '4-20mA',
            'signal_type': 'Mixed',
            'verified': True
        },
        'ABB_DI810': {
            'description': 'ABB DI810 - 16-channel 24 VDC Digital Input Module',
            'digital_inputs': 16,
            'digital_outputs': 0,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': True
        },
        'DI810': {
            'description': 'DI810 - 16-channel 24 VDC Digital Input Module',
            'digital_inputs': 16,
            'digital_outputs': 0,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': True
        },
        'ABB_DO810': {
            'description': 'ABB DO810 - 16-channel 24 VDC Digital Output Module',
            'digital_inputs': 0,
            'digital_outputs': 16,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': True
        },
        'DO810': {
            'description': 'DO810 - 16-channel 24 VDC Digital Output Module',
            'digital_inputs': 0,
            'digital_outputs': 16,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': True
        },
        'ABB_AI810': {
            'description': 'ABB AI810 - 8-channel Analog Input Module',
            'digital_inputs': 0,
            'digital_outputs': 0,
            'analog_inputs': 8,
            'analog_outputs': 0,
            'voltage_range': '0-10V',
            'current_range': '4-20mA',
            'resolution': '12-bit',
            'signal_type': 'Analog',
            'verified': True
        },
        'AI810': {
            'description': 'AI810 - 8-channel Analog Input Module',
            'digital_inputs': 0,
            'digital_outputs': 0,
            'analog_inputs': 8,
            'analog_outputs': 0,
            'voltage_range': '0-10V',
            'current_range': '4-20mA',
            'resolution': '12-bit',
            'signal_type': 'Analog',
            'verified': True
        },
        'ABB_AO810': {
            'description': 'ABB AO810 - 8-channel Analog Output Module',
            'digital_inputs': 0,
            'digital_outputs': 0,
            'analog_inputs': 0,
            'analog_outputs': 8,
            'voltage_range': '0-10V',
            'current_range': '4-20mA',
            'resolution': '12-bit',
            'signal_type': 'Analog',
            'verified': True
        },
        'AO810': {
            'description': 'AO810 - 8-channel Analog Output Module',
            'digital_inputs': 0,
            'digital_outputs': 0,
            'analog_inputs': 0,
            'analog_outputs': 8,
            'voltage_range': '0-10V',
            'current_range': '4-20mA',
            'resolution': '12-bit',
            'signal_type': 'Analog',
            'verified': True
        },
        'ABB_DC523': {
            'description': 'ABB DC523 - 8-channel 24VDC Digital Input Module with configurable outputs',
            'digital_inputs': 8,
            'digital_outputs': 8,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': False
        },
        'DC523': {
            'description': 'DC523 - 8-channel 24VDC Digital Input Module with configurable outputs',
            'digital_inputs': 8,
            'digital_outputs': 8,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': False
        },

        # Siemens Modules
        'SIEMENS_SM1221': {
            'description': 'Siemens SM1221 - 16-channel Digital Input Module',
            'digital_inputs': 16,
            'digital_outputs': 0,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': True
        },
        'SM1221': {
            'description': 'SM1221 - 16-channel Digital Input Module',
            'digital_inputs': 16,
            'digital_outputs': 0,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': True
        },
        'SIEMENS_SM1222': {
            'description': 'Siemens SM1222 - 16-channel Digital Output Module',
            'digital_inputs': 0,
            'digital_outputs': 16,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': True
        },
        'SM1222': {
            'description': 'SM1222 - 16-channel Digital Output Module',
            'digital_inputs': 0,
            'digital_outputs': 16,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'signal_type': 'Digital',
            'verified': True
        },
        'SIEMENS_SM1231': {
            'description': 'Siemens SM1231 - 8-channel Analog Input Module',
            'digital_inputs': 0,
            'digital_outputs': 0,
            'analog_inputs': 8,
            'analog_outputs': 0,
            'voltage_range': '0-10V',
            'current_range': '4-20mA',
            'resolution': '16-bit',
            'signal_type': 'Analog',
            'verified': True
        },
        'SM1231': {
            'description': 'SM1231 - 8-channel Analog Input Module',
            'digital_inputs': 0,
            'digital_outputs': 0,
            'analog_inputs': 8,
            'analog_outputs': 0,
            'voltage_range': '0-10V',
            'current_range': '4-20mA',
            'resolution': '16-bit',
            'signal_type': 'Analog',
            'verified': True
        }
    }

from services.ai_assistant import (_ensure_gemini_model,
                                _gemini_text_from_response,
                                _parse_json_from_text)
try:
    import google.generativeai as genai
except ImportError:
    genai = None


@io_builder_bp.route('/api/module-lookup', methods=['POST'])
def module_lookup():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        vendor = data.get('company', data.get('vendor', '')).strip().upper()
        model = data.get('model', '').strip().upper()

        if not model:
            return jsonify({'success': False, 'message': 'Model is required'}), 400

        # Tier 1: Database Lookup
        if vendor:
            module = ModuleSpec.query.filter_by(company=vendor, model=model).first()
        else:
            module = ModuleSpec.query.filter(ModuleSpec.model.ilike(f'%{model}%')).first()

        if module:
            current_app.logger.info(f"Found module in database: {vendor} {model}")
            return jsonify({
                'success': True,
                'module': {
                    'description': module.description,
                    'digital_inputs': module.digital_inputs,
                    'digital_outputs': module.digital_outputs,
                    'analog_inputs': module.analog_inputs,
                    'analog_outputs': module.analog_outputs,
                    'voltage_range': module.voltage_range,
                    'current_range': module.current_range,
                    'verified': module.verified
                },
                'source': 'database'
            })

        # Tier 2: Hardcoded Comprehensive Database
        module_db = get_comprehensive_module_database()
        search_key = f"{vendor}_{model}" if vendor else model
        module_info = module_db.get(search_key)

        if module_info:
            current_app.logger.info(f"Found module in internal database: {search_key}")
            if vendor:
                new_module = ModuleSpec(
                    company=vendor, model=model,
                    description=module_info.get('description', ''),
                    digital_inputs=module_info.get('digital_inputs', 0),
                    digital_outputs=module_info.get('digital_outputs', 0),
                    analog_inputs=module_info.get('analog_inputs', 0),
                    analog_outputs=module_info.get('analog_outputs', 0),
                    voltage_range=module_info.get('voltage_range'),
                    current_range=module_info.get('current_range'),
                    verified=module_info.get('verified', True)
                )
                db.session.add(new_module)
                db.session.commit()
            return jsonify({'success': True, 'module': module_info, 'source': 'internal_db'})

        # Tier 3: AI Lookup
        if vendor and genai and current_app.config.get('AI_ENABLED'):
            try:
                module_info = _get_specs_from_gemini(vendor, model)
                if module_info:
                    if not any(module_info.get(key, 0) > 0 for key in ['digital_inputs', 'digital_outputs', 'analog_inputs', 'analog_outputs']):
                        current_app.logger.warning(f"AI lookup for {vendor} {model} returned data with no I/O points. Discarding.")
                        return jsonify({'success': False, 'message': f'Module {vendor} {model} found, but no valid I/O specs could be parsed. Please enter specifications manually.', 'manual_entry_required': True}), 404

                    new_module = ModuleSpec(
                        company=vendor, model=model,
                        description=module_info.get('description', f'{vendor} {model} - AI Generated'),
                        digital_inputs=module_info.get('digital_inputs', 0),
                        digital_outputs=module_info.get('digital_outputs', 0),
                        analog_inputs=module_info.get('analog_inputs', 0),
                        analog_outputs=module_info.get('analog_outputs', 0),
                        voltage_range=module_info.get('voltage_range'),
                        current_range=module_info.get('current_range'),
                        verified=False
                    )
                    db.session.add(new_module)
                    db.session.commit()
                    current_app.logger.info(f"Successfully fetched, validated, and saved new module via AI: {vendor} {model}")
                    return jsonify({'success': True, 'module': module_info, 'source': 'ai'})
            except Exception as ai_error:
                current_app.logger.warning(f"AI lookup threw exception: {str(ai_error)}")

        # All tiers failed - provide helpful message
        message = f'Module "{vendor} {model}" not found in database or AI lookup failed. Please enter the specifications manually using the form below.'
        return jsonify({'success': False, 'message': message, 'manual_entry_required': True}), 404

    except Exception as e:
        current_app.logger.error(f"Critical error in module_lookup: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'An unexpected internal server error occurred. Please check the logs.'}), 500

def _get_specs_from_gemini(company: str, model: str):
    """
    Uses the Gemini AI with a multi-step, retry-enabled process to find specifications for an I/O module.
    """
    from typing import Dict, Any, Optional
    
    current_app.logger.info(f"Attempting advanced AI lookup for {company} {model}")
    gemini_model = _ensure_gemini_model()
    
    # --- Helper to validate the final JSON ---
    def _validate_spec_json(json_response):
        if not json_response or not isinstance(json_response, dict):
            return None
            
        # Basic validation: ensure some I/O points exist or a description is present.
        has_io = any(json_response.get(key, 0) > 0 for key in ['digital_inputs', 'digital_outputs', 'analog_inputs', 'analog_outputs'])
        has_desc = bool(json_response.get('description'))

        if not has_io and not has_desc:
            current_app.logger.warning(f"AI response for {company} {model} lacked I/O points and description. Discarding.")
            return None
        
        # Fill in missing keys with 0 (not strict about having ALL keys)
        json_response.setdefault('digital_inputs', 0)
        json_response.setdefault('digital_outputs', 0)
        json_response.setdefault('analog_inputs', 0)
        json_response.setdefault('analog_outputs', 0)
        json_response.setdefault('voltage_range', None)
        json_response.setdefault('current_range', None)

        current_app.logger.info(f"Successfully validated specs from AI for {company} {model}")
        return json_response

    # --- Strategy 1: Precise, one-shot JSON prompt ---
    current_app.logger.info(f"AI Lookup (Strategy 1: Precise JSON) for {company} {model}")
    prompt_1 = f"""
        Act as a helpful engineering assistant. I need to get the technical specifications for an industrial I/O module: '{company} {model}'.
        Please analyze available information for this module and provide a summary of its key specs.
        Your response must be a single, minified JSON object with no markdown. The JSON object must use these exact keys: "description", "digital_inputs", "digital_outputs", "analog_inputs", "analog_outputs", "voltage_range", "current_range".
        If you cannot find a specific value, use 0 for numeric fields and null for string fields. Do not add any extra explanation outside of the JSON.
        For example:
        {{"description":"8-channel 24VDC digital input module","digital_inputs":8,"digital_outputs":0,"analog_inputs":0,"analog_outputs":0,"voltage_range":"24 VDC","current_range":null}}
    """
    try:
        generation_config = genai.types.GenerationConfig(temperature=0.1, max_output_tokens=500)
        request_options = {"timeout": 45}
        response = gemini_model.generate_content(prompt_1, generation_config=generation_config, request_options=request_options)
        text_response = _gemini_text_from_response(response)
        current_app.logger.debug(f"Strategy 1 raw response: {text_response[:200] if text_response else 'None'}")
        if text_response:
            json_response = _parse_json_from_text(text_response)
            current_app.logger.debug(f"Strategy 1 parsed JSON: {json_response}")
            validated_json = _validate_spec_json(json_response)
            if validated_json:
                current_app.logger.info(f"Strategy 1 SUCCESS for {company} {model}")
                return validated_json
        else:
            current_app.logger.debug(f"Strategy 1: No text response from Gemini")
    except Exception as e:
        current_app.logger.warning(f"AI Strategy 1 failed for {company} {model}: {str(e)}", exc_info=True)

    # --- Strategy 2: Two-step prompt (Summarize then Extract) ---
    current_app.logger.info(f"AI Lookup (Strategy 2: Summarize-then-Extract) for {company} {model}")
    prompt_2a_summarize = f"""
        Provide a detailed text summary of the technical specifications for the industrial I/O module: '{company} {model}'.
        Focus on the number of inputs and outputs (digital and analog), voltage ratings, and current ratings.
        Do not use JSON or markdown formatting. Just provide a plain text paragraph.
    """
    try:
        generation_config = genai.types.GenerationConfig(temperature=0.3, max_output_tokens=1000)
        request_options = {"timeout": 60}
        summary_response = gemini_model.generate_content(prompt_2a_summarize, generation_config=generation_config, request_options=request_options)
        summary_text = _gemini_text_from_response(summary_response)
        current_app.logger.debug(f"Strategy 2 summary: {summary_text[:200] if summary_text else 'None'}")

        if summary_text and len(summary_text) > 20:
            current_app.logger.info(f"AI Strategy 2 got summary, now extracting JSON.")
            prompt_2b_extract = f"""
            Analyze the following text and extract the technical specifications into a single, minified JSON object.
            The JSON object must have these exact keys: "description", "digital_inputs", "digital_outputs", "analog_inputs", "analog_outputs", "voltage_range", "current_range".
            If a value is not found, set it to 0 for numeric fields and null for string fields.
            Do not add any explanation, just the JSON object.

            Text to analyze:
            ---
            {summary_text}
            ---
            """
            extract_config = genai.types.GenerationConfig(temperature=0.0, max_output_tokens=500)
            extract_response = gemini_model.generate_content(prompt_2b_extract, generation_config=extract_config, request_options={"timeout": 30})
            extract_text = _gemini_text_from_response(extract_response)
            current_app.logger.debug(f"Strategy 2 extracted JSON: {extract_text}")
            if extract_text:
                json_response = _parse_json_from_text(extract_text)
                validated_json = _validate_spec_json(json_response)
                if validated_json:
                    current_app.logger.info(f"Strategy 2 SUCCESS for {company} {model}")
                    return validated_json
        else:
            current_app.logger.debug(f"Strategy 2: Summary too short or empty")
    except Exception as e:
        current_app.logger.warning(f"AI Strategy 2 failed for {company} {model}: {str(e)}", exc_info=True)

    # --- Strategy 3: Simple question, then extract ---
    current_app.logger.info(f"AI Lookup (Strategy 3: Simple Query) for {company} {model}")
    prompt_3a_simple = f"{company} {model}"
    try:
        # Use a higher temperature to encourage a more conversational, less "recited" response
        generation_config = genai.types.GenerationConfig(temperature=0.4, max_output_tokens=1500)
        request_options = {"timeout": 60}
        simple_response = gemini_model.generate_content(prompt_3a_simple, generation_config=generation_config, request_options=request_options)
        simple_text = _gemini_text_from_response(simple_response)
        current_app.logger.debug(f"Strategy 3 simple response: {simple_text[:200] if simple_text else 'None'}")

        if simple_text and len(simple_text) > 20:
            current_app.logger.info(f"AI Strategy 3 got a text response, now extracting JSON.")
            # Use the same extractor as Strategy 2
            prompt_3b_extract = f"""
            Analyze the following text and extract the technical specifications into a single, minified JSON object.
            The JSON object must have these exact keys: "description", "digital_inputs", "digital_outputs", "analog_inputs", "analog_outputs", "voltage_range", "current_range".
            If a value is not found, set it to 0 for numeric fields and null for string fields. For configurable I/O, assign the total number of channels to the most likely category (e.g., digital_inputs).
            For the 'description', provide a concise, one-sentence summary.
            Do not add any explanation, just the JSON object.

            Text to analyze:
            ---
            {simple_text}
            ---
            """
            extract_config = genai.types.GenerationConfig(temperature=0.0, max_output_tokens=500)
            extract_response = gemini_model.generate_content(prompt_3b_extract, generation_config=extract_config, request_options={"timeout": 30})
            extract_text = _gemini_text_from_response(extract_response)
            if extract_text:
                json_response = _parse_json_from_text(extract_text)
                validated_json = _validate_spec_json(json_response)
                if validated_json:
                    # Special handling for configurable I/O like DC523
                    if "configurable" in simple_text.lower() and validated_json.get('digital_inputs', 0) == 0 and validated_json.get('digital_outputs', 0) == 0:
                        match = re.search(r'(\d+)\s*configurable', simple_text, re.IGNORECASE)
                        if match:
                            total_channels = int(match.group(1))
                            validated_json['digital_inputs'] = total_channels
                            validated_json['description'] += f" ({total_channels} configurable DI/DO)"
                            current_app.logger.info(f"Populated {total_channels} configurable channels for {company} {model}")
                    return validated_json
    except Exception as e:
        current_app.logger.warning(f"AI Strategy 3 failed for {company} {model}: {e}")

    current_app.logger.error(f"All AI lookup strategies failed for {company} {model}.")
    return None

def _handle_ai_failure(company: str, model: str, error_message: str = None):
    """
    Gracefully handle AI failures and return user-friendly message.
    If quota exceeded, user should use manual entry form.
    """
    if error_message and "quota" in error_message.lower():
        msg = f'Module "{company} {model}" not found in database. API quota exceeded. Please enter the specifications manually.'
    elif error_message and "429" in error_message:
        msg = f'Module "{company} {model}" not found in database. Too many requests. Please wait a moment or enter manually.'
    else:
        msg = f'Module "{company} {model}" not found in database. Please enter specifications manually.'
    return msg

@io_builder_bp.route('/api/module-manual-entry', methods=['POST'])
@login_required
def module_manual_entry():
    """Manual fallback endpoint for users to add module specs when AI fails"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        company = data.get('company', '').strip().upper()
        model = data.get('model', '').strip().upper()
        description = data.get('description', '').strip()
        digital_inputs = int(data.get('digital_inputs', 0))
        digital_outputs = int(data.get('digital_outputs', 0))
        analog_inputs = int(data.get('analog_inputs', 0))
        analog_outputs = int(data.get('analog_outputs', 0))
        voltage_range = data.get('voltage_range', '').strip()
        current_range = data.get('current_range', '').strip()
        
        # Validation
        if not company or not model:
            return jsonify({'success': False, 'message': 'Company and Model are required'}), 400
        if not description:
            return jsonify({'success': False, 'message': 'Description is required'}), 400
        if digital_inputs + digital_outputs + analog_inputs + analog_outputs == 0:
            return jsonify({'success': False, 'message': 'At least one I/O point must be specified'}), 400
        
        # Check if already exists
        existing = ModuleSpec.query.filter_by(company=company, model=model).first()
        if existing:
            # Update existing
            existing.description = description
            existing.digital_inputs = digital_inputs
            existing.digital_outputs = digital_outputs
            existing.analog_inputs = analog_inputs
            existing.analog_outputs = analog_outputs
            existing.voltage_range = voltage_range or None
            existing.current_range = current_range or None
            existing.verified = True  # User-verified
            db.session.commit()
            current_app.logger.info(f"Updated module in database: {company} {model}")
        else:
            # Create new
            new_module = ModuleSpec(
                company=company,
                model=model,
                description=description,
                digital_inputs=digital_inputs,
                digital_outputs=digital_outputs,
                analog_inputs=analog_inputs,
                analog_outputs=analog_outputs,
                voltage_range=voltage_range or None,
                current_range=current_range or None,
                verified=True  # User-verified
            )
            db.session.add(new_module)
            db.session.commit()
            current_app.logger.info(f"Saved new module to database via manual entry: {company} {model}")
        
        return jsonify({
            'success': True,
            'message': f'Module {company} {model} saved successfully',
            'module': {
                'description': description,
                'digital_inputs': digital_inputs,
                'digital_outputs': digital_outputs,
                'analog_inputs': analog_inputs,
                'analog_outputs': analog_outputs,
                'voltage_range': voltage_range or None,
                'current_range': current_range or None,
                'verified': True
            },
            'source': 'manual'
        })
    except Exception as e:
        current_app.logger.error(f"Error in module_manual_entry: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to save module. Check server logs.'}), 500

@io_builder_bp.route('/api/generate-io-table', methods=['POST'])
def generate_io_table():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        # Handle modules array from JavaScript
        modules = data.get('modules', [])
        if not modules:
            return jsonify({'success': False, 'message': 'No modules configured'}), 400

        tables = {
            'digital_inputs': [],
            'digital_outputs': [],
            'analog_inputs': [],
            'analog_outputs': []
        }

        current_sno = 1
        
        # Process each module
        for module_idx, module in enumerate(modules):
            rack_no = module.get('rack_no', module_idx)
            position = module.get('position', module_idx + 1)
            module_name = f"{module.get('company', '')} {module.get('model', '')}"
            
            # Generate Digital Inputs
            digital_inputs = module.get('digital_inputs', 0)
            for i in range(digital_inputs):
                tables['digital_inputs'].append({
                    'sno': current_sno,
                    'rack_no': rack_no,
                    'module_position': position,
                    'slot_no': position,
                    'signal_tag': f'DI_{rack_no:02d}_{position:02d}_{i+1:02d}',
                    'signal_description': f'{module_name} - Digital Input {i+1}',
                    'channel': i+1
                })
                current_sno += 1

            # Generate Digital Outputs
            digital_outputs = module.get('digital_outputs', 0)
            for i in range(digital_outputs):
                tables['digital_outputs'].append({
                    'sno': current_sno,
                    'rack_no': rack_no,
                    'module_position': position,
                    'slot_no': position,
                    'signal_tag': f'DO_{rack_no:02d}_{position:02d}_{i+1:02d}',
                    'signal_description': f'{module_name} - Digital Output {i+1}',
                    'channel': i+1
                })
                current_sno += 1

            # Generate Analog Inputs
            analog_inputs = module.get('analog_inputs', 0)
            for i in range(analog_inputs):
                tables['analog_inputs'].append({
                    'sno': current_sno,
                    'rack_no': rack_no,
                    'module_position': position,
                    'slot_no': position,
                    'signal_tag': f'AI_{rack_no:02d}_{position:02d}_{i+1:02d}',
                    'signal_description': f'{module_name} - Analog Input {i+1}',
                    'range': module.get('current_range', '4-20mA'),
                    'units': 'mA',
                    'channel': i+1
                })
                current_sno += 1

            # Generate Analog Outputs
            analog_outputs = module.get('analog_outputs', 0)
            for i in range(analog_outputs):
                tables['analog_outputs'].append({
                    'sno': current_sno,
                    'rack_no': rack_no,
                    'module_position': position,
                    'slot_no': position,
                    'signal_tag': f'AO_{rack_no:02d}_{position:02d}_{i+1:02d}',
                    'signal_description': f'{module_name} - Analog Output {i+1}',
                    'range': module.get('current_range', '4-20mA'),
                    'units': 'mA',
                    'channel': i+1
                })
                current_sno += 1

        # Calculate summary
        summary = {
            'total_points': current_sno - 1,
            'digital_inputs': len(tables['digital_inputs']),
            'digital_outputs': len(tables['digital_outputs']),
            'analog_inputs': len(tables['analog_inputs']),
            'analog_outputs': len(tables['analog_outputs'])
        }

        return jsonify({
            'success': True, 
            'tables': tables,
            'summary': summary
        })

    except Exception as e:
        current_app.logger.error(f"Error generating I/O table: {str(e)}")
        return jsonify({'success': False, 'error': str(e), 'message': 'Error generating I/O table'}), 500

@io_builder_bp.route('/api/save-custom-module', methods=['POST'])
@login_required
def save_custom_module():
    """Save custom module specification to database"""
    try:
        data = request.get_json()

        spec = ModuleSpec(
            company=data.get('company', '').upper(),
            model=data.get('model', '').upper(),
            description=data.get('description', ''),
            digital_inputs=data.get('digital_inputs', 0),
            digital_outputs=data.get('digital_outputs', 0),
            analog_inputs=data.get('analog_inputs', 0),
            analog_outputs=data.get('analog_outputs', 0),
            voltage_range=data.get('voltage_range'),
            current_range=data.get('current_range'),
            resolution=data.get('resolution'),
            signal_type=data.get('signal_type'),
            verified=True
        )

        existing_spec = ModuleSpec.query.filter_by(company=spec.company, model=spec.model).first()
        if existing_spec:
            for key, value in data.items():
                if hasattr(existing_spec, key) and value is not None:
                    setattr(existing_spec, key, value)
            existing_spec.verified = True
            db.session.commit()
            return jsonify({'success': True, 'message': 'Module specification updated successfully'})
        else:
            db.session.add(spec)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Module specification saved successfully'})

    except Exception as e:
        current_app.logger.error(f"Error saving custom module: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@io_builder_bp.route('/api/test-lookup/<company>/<model>')
@login_required
def test_lookup(company, model):
    """Test endpoint to verify module lookup functionality"""
    try:
        current_app.logger.info(f"=== TESTING LOOKUP FOR {company} {model} ===")

        # Get module database
        module_db = get_comprehensive_module_database()

        # Test all possible keys
        test_keys = [
            f"{company.upper()}_{model.upper()}",
            model.upper(),
            f"{company.upper()}_{model.upper().replace('-', '_')}",
            f"{company.upper()}_{model.upper().replace(' ', '_')}"
        ]

        results = {}
        for key in test_keys:
            if key in module_db:
                results[key] = module_db[key]
                current_app.logger.info(f"Found spec for key: {key}")
            else:
                current_app.logger.info(f"No spec for key: {key}")

        return jsonify({
            'success': True,
            'company': company,
            'model': model,
            'test_keys': test_keys,
            'found_specs': results,
            'total_modules_in_db': len(module_db)
        })

    except Exception as e:
        current_app.logger.error(f"Test lookup error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500