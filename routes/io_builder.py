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
            # Save to DB for future consistency if vendor is provided
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

        # Tier 3: Web Scraping Lookup
        if vendor:
            module_info = attempt_web_lookup(vendor, model)
            if module_info:
                # Data validation before saving
                if not any(module_info.get(key, 0) > 0 for key in ['digital_inputs', 'digital_outputs', 'analog_inputs', 'analog_outputs']):
                    current_app.logger.warning(f"Web lookup for {vendor} {model} returned data with no I/O points. Discarding.")
                    return jsonify({'success': False, 'message': f'Module {vendor} {model} found, but no valid I/O specs could be parsed.'}), 404

                # Save the validated, scraped data to the database
                new_module = ModuleSpec(
                    company=vendor, model=model,
                    description=module_info.get('description', f'{vendor} {model} - Scraped'),
                    digital_inputs=module_info.get('digital_inputs', 0),
                    digital_outputs=module_info.get('digital_outputs', 0),
                    analog_inputs=module_info.get('analog_inputs', 0),
                    analog_outputs=module_info.get('analog_outputs', 0),
                    voltage_range=module_info.get('voltage_range'),
                    current_range=module_info.get('current_range'),
                    verified=False  # Scraped data is never considered verified
                )
                db.session.add(new_module)
                db.session.commit()
                current_app.logger.info(f"Successfully fetched, validated, and saved new module: {vendor} {model}")
                return jsonify({'success': True, 'module': module_info, 'source': 'web'})

        # If all lookups fail
        message = f'Module "{vendor} {model}" not found in any database, and web lookup was unsuccessful.' if vendor else f'Module "{model}" not found.'
        return jsonify({'success': False, 'message': message}), 404

    except Exception as e:
        current_app.logger.error(f"Critical error in module_lookup: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'An unexpected internal server error occurred. Please check the logs.'}), 500

def attempt_web_lookup(company, model):
    """
    Attempt to find module specifications online using DuckDuckGo search.
    This version includes more robust error handling, smarter link selection,
    and validates parsed data before returning.
    """
    try:
        current_app.logger.info(f"Starting robust web lookup for {company} {model}")

        # Prioritize queries that are more likely to yield direct results
        search_queries = [
            f'"{company} {model}" datasheet pdf',
            f'"{company} {model}" technical specifications',
            f"{company} {model} manual",
            f"{model} industrial I/O module specifications"
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/'
        }

        for query in search_queries:
            try:
                current_app.logger.info(f"Searching online with query: '{query}'")
                search_url = f"https://duckduckgo.com/html/?q={quote(query)}"
                
                # Make the search request with a timeout and error handling
                response = requests.get(search_url, headers=headers, timeout=15)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                soup = BeautifulSoup(response.content, 'html.parser')

                # Smarter link filtering
                links = soup.find_all('a', href=True)
                relevant_links = []
                for link in links:
                    href = link.get('href', '')
                    # Prioritize official-looking domains and direct PDF links
                    if 'http' in href and not any(junk in href for junk in ['duckduckgo.com', 'google.com', 'bing.com']):
                        if company.lower() in href.lower() or '.pdf' in href.lower() or 'datasheet' in href.lower():
                            relevant_links.append(href)
                
                # Limit to the top 3 most promising links
                for link_url in relevant_links[:3]:
                    try:
                        current_app.logger.info(f"Scraping promising link: {link_url}")
                        link_response = requests.get(link_url, headers=headers, timeout=10)
                        link_response.raise_for_status()

                        # Check if content is PDF, if so, we can't parse it with BeautifulSoup
                        if 'application/pdf' in link_response.headers.get('Content-Type', ''):
                            current_app.logger.warning(f"Link {link_url} is a PDF, which cannot be parsed for detailed specs.")
                            continue # Move to the next link

                        link_soup = BeautifulSoup(link_response.content, 'html.parser')
                        parsed_spec = parse_specifications_from_content(link_soup, company, model)

                        # Validate that the parsed data is reasonable
                        if parsed_spec and (parsed_spec.get('digital_inputs', 0) > 0 or
                                           parsed_spec.get('digital_outputs', 0) > 0 or
                                           parsed_spec.get('analog_inputs', 0) > 0 or
                                           parsed_spec.get('analog_outputs', 0) > 0):
                            current_app.logger.info(f"Successfully parsed valid specs from {link_url}")
                            return parsed_spec
                            
                    except requests.exceptions.RequestException as link_error:
                        current_app.logger.warning(f"Failed to fetch or process link {link_url}: {link_error}")
                    except Exception as e:
                        current_app.logger.error(f"An unexpected error occurred while processing link {link_url}: {e}")

            except requests.exceptions.RequestException as search_error:
                current_app.logger.error(f"Web search failed for query '{query}': {search_error}")
            except Exception as e:
                current_app.logger.error(f"An unexpected error occurred during web search: {e}")

        current_app.logger.warning(f"Web lookup completed for {company} {model} with no definitive results.")
        return None

    except Exception as e:
        current_app.logger.error(f"A critical error occurred in attempt_web_lookup: {e}")
        return None

def parse_specifications_from_content(soup, company, model):
    """
    Parse module specifications from HTML content with improved robustness.
    Looks for specification tables and uses more flexible regex.
    """
    try:
        # Initial spec with defaults
        spec = {
            'description': f'{company.upper()} {model.upper()} - Scraped',
            'digital_inputs': 0, 'digital_outputs': 0,
            'analog_inputs': 0, 'analog_outputs': 0,
            'voltage_range': None, 'current_range': None,
            'signal_type': 'Unknown', 'verified': False
        }

        # Try to find a specification table first
        tables = soup.find_all('table')
        text_content = ""
        if tables:
            for table in tables:
                # Check if the table seems relevant based on headers
                if any(header in table.get_text().lower() for header in ['specification', 'technical data', 'i/o']):
                    text_content += table.get_text().lower() + "\n"
        
        # If no relevant table found, use the whole body text
        if not text_content:
            text_content = soup.body.get_text().lower() if soup.body else soup.get_text().lower()

        # Define more specific and flexible regex patterns
        io_patterns = {
            'digital_inputs': [r'(\d+)\s*(?:-channel)?\s*digital\s*input[s]?'],
            'digital_outputs': [r'(\d+)\s*(?:-channel)?\s*digital\s*output[s]?'],
            'analog_inputs': [r'(\d+)\s*(?:-channel)?\s*analog\s*input[s]?'],
            'analog_outputs': [r'(\d+)\s*(?:-channel)?\s*analog\s*output[s]?']
        }

        # Extract I/O counts
        for io_type, patterns in io_patterns.items():
            for pattern in patterns:
                matches = re.search(pattern, text_content, re.IGNORECASE)
                if matches:
                    try:
                        value = int(matches.group(1))
                        if 0 < value < 256: # Basic sanity check
                            spec[io_type] = value
                            current_app.logger.info(f"Found {io_type}: {value} from web scrape")
                            # Don't break, allow later patterns to override if they are more specific (though not in this simple setup)
                    except (ValueError, IndexError):
                        continue
        
        # Simple voltage/current parsing (can be expanded)
        if not spec['voltage_range']:
            voltage_match = re.search(r'(\d+\s*VDC)', text_content, re.IGNORECASE)
            if voltage_match:
                spec['voltage_range'] = voltage_match.group(1).upper()

        if not spec['current_range']:
            current_match = re.search(r'((?:4-20|0-20)\s*mA)', text_content, re.IGNORECASE)
            if current_match:
                spec['current_range'] = current_match.group(1)

        # Determine signal type
        if (spec['digital_inputs'] > 0 or spec['digital_outputs'] > 0) and \
           (spec['analog_inputs'] > 0 or spec['analog_outputs'] > 0):
            spec['signal_type'] = 'Mixed'
        elif spec['digital_inputs'] > 0 or spec['digital_outputs'] > 0:
            spec['signal_type'] = 'Digital'
        elif spec['analog_inputs'] > 0 or spec['analog_outputs'] > 0:
            spec['signal_type'] = 'Analog'

        # Only return a spec if it has at least one I/O point identified
        if spec['signal_type'] != 'Unknown':
            current_app.logger.info("Successfully parsed a valid-looking specification from web content.")
            return spec

        current_app.logger.warning("Could not parse any valid I/O points from the provided web content.")
        return None

    except Exception as e:
        current_app.logger.error(f"Error parsing specifications from web content: {e}")
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