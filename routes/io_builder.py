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

@io_builder_bp.route('/api/module-lookup', methods=['POST'])
def module_lookup():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400

        # Accept both vendor and company field names for compatibility
        vendor = data.get('company', data.get('vendor', '')).strip().upper()
        model = data.get('model', '').strip().upper()

        # Allow searching by model only if vendor is not provided
        if not model:
            return jsonify({'success': False, 'message': 'Model is required'}), 400

        # Try to find in database first using ModuleSpec model
        if vendor:
            module = ModuleSpec.query.filter_by(company=vendor, model=model).first()
        else:
            # If no vendor specified, search by model only (case-insensitive)
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
                    'current_range': module.current_range
                },
                'source': 'database'
            })

        # Try to find in comprehensive module database
        module_db = get_comprehensive_module_database()
        
        # Check various key patterns with case-insensitive matching
        test_keys = []
        if vendor:
            test_keys.extend([
                f"{vendor}_{model}",
                f"{vendor.upper()}_{model.upper()}",
                f"{vendor}_{model.replace('-', '_')}",
                f"{vendor}_{model.replace(' ', '_')}"
            ])
        # Always check model alone for flexibility
        test_keys.extend([
            model,
            model.upper(),
            model.replace('-', '_'),
            model.replace(' ', '_')
        ])
        
        # Also check with case-insensitive matching
        for key in test_keys:
            # Direct key match
            if key in module_db:
                module_info = module_db[key]
                current_app.logger.info(f"Found module in comprehensive database: {key}")
                
                # Save to database for future use if vendor is provided
                if vendor:
                    new_module = ModuleSpec(
                        company=vendor,
                        model=model,
                        description=module_info.get('description', ''),
                        digital_inputs=module_info.get('digital_inputs', 0),
                        digital_outputs=module_info.get('digital_outputs', 0),
                        analog_inputs=module_info.get('analog_inputs', 0),
                        analog_outputs=module_info.get('analog_outputs', 0),
                        voltage_range=module_info.get('voltage_range'),
                        current_range=module_info.get('current_range'),
                        verified=module_info.get('verified', False)
                    )
                    
                    db.session.add(new_module)
                    db.session.commit()
                
                return jsonify({
                    'success': True,
                    'module': module_info,
                    'source': 'database'
                })

        # If not found in databases, try partial matching in comprehensive database
        # Check for partial matches (case-insensitive)
        for db_key, db_module in module_db.items():
            if model.upper() in db_key.upper() or db_key.upper() in model.upper():
                current_app.logger.info(f"Found partial match in comprehensive database: {db_key}")
                return jsonify({
                    'success': True,
                    'module': db_module,
                    'source': 'database'
                })
        
        # If still not found and vendor is provided, try web lookup
        if vendor:
            module_info = attempt_web_lookup(vendor, model)
        else:
            module_info = None

        if module_info:
            # Save to database for future use
            new_module = ModuleSpec(
                company=vendor,
                model=model,
                description=module_info.get('description', ''),
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

            current_app.logger.info(f"Fetched and saved module: {vendor} {model}")
            return jsonify({
                'success': True,
                'module': module_info,
                'source': 'web'
            })

        if vendor:
            return jsonify({'success': False, 'message': f'Module {vendor} {model} not found'}), 404
        else:
            return jsonify({'success': False, 'message': f'Module {model} not found'}), 404

    except Exception as e:
        current_app.logger.error(f"Error in module lookup: {str(e)}")
        return jsonify({'success': False, 'message': 'Internal server error'}), 500

def attempt_web_lookup(company, model):
    """Attempt to find module specifications online"""
    try:
        current_app.logger.info(f"Starting web lookup for {company} {model}")

        # Search queries
        search_queries = [
            f"{company} {model} datasheet",
            f"{company} {model} specifications",
            f"{company} {model} I/O module",
            f"{model} industrial automation module"
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

        for query in search_queries:
            try:
                current_app.logger.info(f"Searching: {query}")
                search_url = f"https://duckduckgo.com/html/?q={quote(query)}"

                response = requests.get(search_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')

                    # Extract links
                    links = soup.find_all('a', href=True)
                    relevant_links = []

                    for link in links:
                        href = link.get('href', '')
                        if any(domain in href.lower() for domain in [company.lower(), 'automation', 'industrial', 'datasheet']):
                            if 'http' in href:
                                relevant_links.append(href)
                                if len(relevant_links) >= 2:
                                    break

                    # Try to scrape relevant links
                    for link_url in relevant_links:
                        try:
                            link_response = requests.get(link_url, headers=headers, timeout=8)
                            if link_response.status_code == 200:
                                link_soup = BeautifulSoup(link_response.content, 'html.parser')
                                parsed_spec = parse_specifications_from_content(link_soup, company, model)
                                if parsed_spec:
                                    current_app.logger.info(f"Successfully parsed specs from {link_url}")
                                    return parsed_spec
                        except Exception as link_error:
                            current_app.logger.warning(f"Error processing link {link_url}: {link_error}")
                            continue

            except Exception as search_error:
                current_app.logger.warning(f"Search failed for '{query}': {search_error}")
                continue

        return None

    except Exception as e:
        current_app.logger.error(f"Web lookup error: {e}")
        return None

def parse_specifications_from_content(soup, company, model):
    """Parse module specifications from HTML content"""
    try:
        text_content = soup.get_text().lower()

        spec = {
            'description': f'{company} {model}',
            'digital_inputs': 0,
            'digital_outputs': 0,
            'analog_inputs': 0,
            'analog_outputs': 0,
            'voltage_range': '24 VDC',
            'current_range': '4-20mA',
            'signal_type': 'Unknown',
            'verified': True
        }

        # Enhanced regex patterns for I/O detection
        io_patterns = {
            'digital_inputs': [
                r'(\d+)\s*(?:ch|channel[s]?)\s*(?:24\s*v\s*)?digital\s*input[s]?',
                r'digital\s*input[s]?[:\s]*(\d+)\s*(?:ch|channel[s]?)?',
                r'(\d+)\s*di\b',
                r'(\d+)\s*x\s*di\b',
                r'di\s*(\d+)',
                r'(\d+)\s*digital\s*in'
            ],
            'digital_outputs': [
                r'(\d+)\s*(?:ch|channel[s]?)\s*(?:24\s*v\s*)?digital\s*output[s]?',
                r'digital\s*output[s]?[:\s]*(\d+)\s*(?:ch|channel[s]?)?',
                r'(\d+)\s*do\b',
                r'(\d+)\s*x\s*do\b',
                r'do\s*(\d+)',
                r'(\d+)\s*digital\s*out'
            ],
            'analog_inputs': [
                r'(\d+)\s*(?:ch|channel[s]?)\s*analog\s*input[s]?',
                r'analog\s*input[s]?[:\s]*(\d+)\s*(?:ch|channel[s]?)?',
                r'(\d+)\s*ai\b',
                r'(\d+)\s*x\s*ai\b',
                r'ai\s*(\d+)',
                r'(\d+)\s*analog\s*in'
            ],
            'analog_outputs': [
                r'(\d+)\s*(?:ch|channel[s]?)\s*analog\s*output[s]?',
                r'analog\s*output[s]?[:\s]*(\d+)\s*(?:ch|channel[s]?)?',
                r'(\d+)\s*ao\b',
                r'(\d+)\s*x\s*ao\b',
                r'ao\s*(\d+)',
                r'(\d+)\s*analog\s*out'
            ]
        }

        # Extract I/O counts
        for io_type, patterns in io_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, text_content, re.IGNORECASE)
                if matches:
                    try:
                        value = int(matches[0])
                        if value > 0:
                            spec[io_type] = value
                            current_app.logger.info(f"Found {io_type}: {value}")
                            break
                    except (ValueError, IndexError):
                        continue

        # Extract voltage and current ranges
        voltage_matches = re.findall(r'(\d+(?:\.\d+)?)\s*[-–to]\s*(\d+(?:\.\d+)?)\s*v', text_content, re.IGNORECASE)
        if voltage_matches:
            spec['voltage_range'] = f"{voltage_matches[0][0]}-{voltage_matches[0][1]}V"

        current_matches = re.findall(r'(\d+(?:\.\d+)?)\s*[-–to]\s*(\d+(?:\.\d+)?)\s*ma', text_content, re.IGNORECASE)
        if current_matches:
            spec['current_range'] = f"{current_matches[0][0]}-{current_matches[0][1]}mA"

        # Determine signal type
        total_digital = spec['digital_inputs'] + spec['digital_outputs']
        total_analog = spec['analog_inputs'] + spec['analog_outputs']

        if total_digital > 0 and total_analog > 0:
            spec['signal_type'] = 'Mixed'
        elif total_digital > 0:
            spec['signal_type'] = 'Digital'
        elif total_analog > 0:
            spec['signal_type'] = 'Analog'

        # Only return if we found valid I/O data
        if any(spec[key] > 0 for key in ['digital_inputs', 'digital_outputs', 'analog_inputs', 'analog_outputs']):
            current_app.logger.info(f"Successfully parsed web specifications")
            return spec

        return None

    except Exception as e:
        current_app.logger.error(f"Error parsing specifications: {e}")
        return None

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