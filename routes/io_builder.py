from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import login_required, current_user
import requests
from bs4 import BeautifulSoup
import re
from models import db, ModuleSpec
import time
from urllib.parse import quote
import logging
import json

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

# AI lookup disabled (Gemini removed); keep imports minimal
def _ai_lookup_module(company: str, model: str) -> dict | None:
    """Attempt to fetch module specs using the configured OpenRouter model."""
    api_key = current_app.config.get("OPENROUTER_API_KEY") or current_app.config.get("AI_API_KEY")
    model_id = current_app.config.get("OPENROUTER_MODEL") or "x-ai/grok-4.1-fast:free"
    if not api_key:
        current_app.logger.info("OpenRouter API key not configured; skipping AI lookup")
        return None

    prompt = f"""
    Provide a concise JSON object for industrial I/O module '{company} {model}'.
    Keys: "description", "digital_inputs", "digital_outputs", "analog_inputs", "analog_outputs", "voltage_range", "current_range".
    - description: one short sentence
    - counts must be integers (0 if unknown)
    - voltage/current strings may be null if unknown
    Respond with JSON only.
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt.strip()}],
        "temperature": 0.2,
        "max_tokens": 300,
    }
    try:
        current_app.logger.info(f"OpenRouter IO lookup: model={model_id}, key_len={len(api_key)} for {company} {model}")
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=25)
        if resp.status_code >= 400:
            current_app.logger.warning(f"OpenRouter IO lookup failed {resp.status_code}: {resp.text}")
            return None
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return None
        try:
            parsed = json.loads(content)
        except Exception:
            # try to extract JSON substring
            match = re.search(r"\{.*\}", content, re.DOTALL)
            parsed = json.loads(match.group(0)) if match else None
        if not isinstance(parsed, dict):
            return None
        # validate/normalize
        def _int(val):
            try:
                return int(val)
            except Exception:
                return 0
        validated = {
            "description": str(parsed.get("description") or f"{company} {model}"),
            "digital_inputs": _int(parsed.get("digital_inputs")),
            "digital_outputs": _int(parsed.get("digital_outputs")),
            "analog_inputs": _int(parsed.get("analog_inputs")),
            "analog_outputs": _int(parsed.get("analog_outputs")),
            "voltage_range": parsed.get("voltage_range"),
            "current_range": parsed.get("current_range"),
        }
        return validated
    except Exception as e:
        current_app.logger.error(f"OpenRouter IO lookup exception for {company} {model}: {e}", exc_info=True)
        return None


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

        # Tier 3: OpenRouter AI lookup
        ai_specs = _ai_lookup_module(vendor, model)
        if ai_specs:
            current_app.logger.info(f"OpenRouter AI provided specs for {vendor} {model}")
            try:
                new_module = ModuleSpec(
                    company=vendor or "UNKNOWN",
                    model=model,
                    description=ai_specs.get('description', ''),
                    digital_inputs=ai_specs.get('digital_inputs', 0),
                    digital_outputs=ai_specs.get('digital_outputs', 0),
                    analog_inputs=ai_specs.get('analog_inputs', 0),
                    analog_outputs=ai_specs.get('analog_outputs', 0),
                    voltage_range=ai_specs.get('voltage_range'),
                    current_range=ai_specs.get('current_range'),
                    verified=False
                )
                db.session.add(new_module)
                db.session.commit()
            except Exception as db_err:
                current_app.logger.warning(f"Could not persist AI specs for {vendor} {model}: {db_err}")
            return jsonify({'success': True, 'module': ai_specs, 'source': 'ai'})

        # Tier 3: Module not found - Manual entry required (saved to database for ALL future users)
        current_app.logger.info(f"Module {vendor} {model} not found - manual entry required")
        message = f'Module "{vendor} {model}" not in database. Please enter specifications below - they will be saved for all future reports.'
        return jsonify({'success': False, 'message': message, 'manual_entry_required': True}), 404

    except Exception as e:
        current_app.logger.error(f"Critical error in module_lookup: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'An unexpected internal server error occurred. Please check the logs.'}), 500


@io_builder_bp.route('/api/save-module', methods=['POST'])
@login_required
def save_module():
    """
    Save manually entered module specifications to database.
    Once saved, it's available for ALL future users and reports.
    This is the reliable, scalable solution.
    """
    try:
        data = request.get_json()
        company = data.get('company', '').strip().upper()
        model = data.get('model', '').strip().upper()
        
        if not company or not model:
            return jsonify({'success': False, 'error': 'Company and model are required'}), 400
        
        # Check if module already exists
        existing = ModuleSpec.query.filter(
            db.func.upper(ModuleSpec.company) == company,
            db.func.upper(ModuleSpec.model) == model
        ).first()
        
        specs = {
            'description': data.get('description', f'{company} {model}'),
            'digital_inputs': int(data.get('digital_inputs', 0)),
            'digital_outputs': int(data.get('digital_outputs', 0)),
            'analog_inputs': int(data.get('analog_inputs', 0)),
            'analog_outputs': int(data.get('analog_outputs', 0)),
            'voltage_range': data.get('voltage_range'),
            'current_range': data.get('current_range')
        }
        
        if existing:
            current_app.logger.info(f"Updating module: {company} {model}")
            for key, value in specs.items():
                setattr(existing, key, value)
            existing.verified = True
        else:
            current_app.logger.info(f"Creating new module: {company} {model}")
            new_module = ModuleSpec(
                company=company,
                model=model,
                **specs,
                verified=True
            )
            db.session.add(new_module)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Module {company} {model} saved successfully. Now available for all future reports!',
            'module': {
                'company': company,
                'model': model,
                **specs
            }
        })
    
    except Exception as e:
        current_app.logger.error(f"Error saving module: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


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
