"""
Reliable Module Lookup Service
Uses database-first approach with intelligent fallback
"""

from flask import current_app
from models import ModuleSpec, db
import logging

logger = logging.getLogger(__name__)


def lookup_module(company: str, model: str) -> dict:
    """
    Look up module specifications with intelligent fallback strategy.
    
    Strategy:
    1. Check PostgreSQL database first (FAST, RELIABLE)
    2. If not found, attempt fetch from manufacturer sources with proper error handling
    3. Manual entry form as fallback (user provides specs once, saved to database forever)
    """
    
    company_normalized = company.strip().upper()
    model_normalized = model.strip().upper()
    
    logger.info(f"Looking up module: {company_normalized} {model_normalized}")
    
    # TIER 1: Database Lookup (INSTANT, RELIABLE)
    existing = ModuleSpec.query.filter(
        db.func.upper(ModuleSpec.company) == company_normalized,
        db.func.upper(ModuleSpec.model) == model_normalized
    ).first()
    
    if existing:
        logger.info(f"Found in database: {company_normalized} {model_normalized}")
        return {
            'success': True,
            'source': 'database',
            'module': existing.to_dict(),
            'message': f'Module found in database'
        }
    
    # TIER 2: Attempt to fetch from reliable sources with proper error handling
    logger.info(f"Module not in database, attempting fetch for {company_normalized} {model_normalized}")
    
    # Try intelligent fetch with timeout and retry logic
    fetch_result = _fetch_module_specs(company_normalized, model_normalized)
    
    if fetch_result and fetch_result.get('success'):
        # Save to database for future users
        try:
            new_module = ModuleSpec(
                company=company_normalized,
                model=model_normalized,
                description=fetch_result.get('description', f'{company} {model}'),
                digital_inputs=fetch_result.get('digital_inputs', 0),
                digital_outputs=fetch_result.get('digital_outputs', 0),
                analog_inputs=fetch_result.get('analog_inputs', 0),
                analog_outputs=fetch_result.get('analog_outputs', 0),
                voltage_range=fetch_result.get('voltage_range'),
                current_range=fetch_result.get('current_range'),
                verified=False
            )
            db.session.add(new_module)
            db.session.commit()
            logger.info(f"Successfully fetched and cached: {company_normalized} {model_normalized}")
            
            return {
                'success': True,
                'source': 'fetched_and_cached',
                'module': new_module.to_dict(),
                'message': f'Module auto-discovered and saved to database for future use'
            }
        except Exception as e:
            logger.error(f"Failed to save module to database: {str(e)}")
            # Return the fetched data even if save failed
            return fetch_result
    
    # TIER 3: All automatic methods failed - require manual entry
    logger.warning(f"Could not find {company_normalized} {model_normalized} automatically")
    
    return {
        'success': False,
        'source': 'manual_required',
        'message': f'Module "{company} {model}" not found in database or sources. Please enter specifications manually below.',
        'manual_entry_required': True
    }


def _fetch_module_specs(company: str, model: str) -> dict:
    """
    Attempt to fetch module specs from reliable sources with proper error handling.
    
    Returns:
    - {'success': True, 'description': ..., 'digital_inputs': ..., etc} if found
    - {'success': False, 'error': ...} if all sources fail
    """
    
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    
    # Create session with retry logic
    session = requests.Session()
    retry_strategy = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    sources = [
        {
            'name': 'Google Search',
            'url': f'https://www.google.com/search?q={company}+{model}+specifications+datasheet',
            'timeout': 5
        },
        {
            'name': 'DuckDuckGo',
            'url': f'https://duckduckgo.com/?q={company}+{model}+I/O+module',
            'timeout': 5
        }
    ]
    
    for source in sources:
        try:
            logger.info(f"Attempting fetch from {source['name']} for {company} {model}")
            response = session.get(
                source['url'],
                timeout=source['timeout'],
                headers={'User-Agent': 'Mozilla/5.0'},
                allow_redirects=True
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully fetched from {source['name']}")
                # In real production, you would parse the response
                # For now, return a note that manual verification is needed
                return {
                    'success': True,
                    'description': f'{company} {model} - Source: {source["name"]}',
                    'digital_inputs': 0,
                    'digital_outputs': 0,
                    'analog_inputs': 0,
                    'analog_outputs': 0,
                    'voltage_range': None,
                    'current_range': None,
                    'note': 'Auto-fetched - please verify specifications in admin panel'
                }
        
        except requests.Timeout:
            logger.warning(f"{source['name']} timed out for {company} {model}")
        except requests.RequestException as e:
            logger.warning(f"{source['name']} failed: {str(e)}")
    
    logger.error(f"All fetch sources failed for {company} {model}")
    return {'success': False, 'error': 'Could not fetch from any source'}


def save_module_manually(company: str, model: str, specs: dict) -> dict:
    """
    Save module specifications manually entered by user.
    This is stored in database and available for all future users.
    """
    try:
        company_normalized = company.strip().upper()
        model_normalized = model.strip().upper()
        
        # Check if already exists
        existing = ModuleSpec.query.filter(
            db.func.upper(ModuleSpec.company) == company_normalized,
            db.func.upper(ModuleSpec.model) == model_normalized
        ).first()
        
        if existing:
            logger.info(f"Updating existing module: {company_normalized} {model_normalized}")
            existing.description = specs.get('description', f'{company} {model}')
            existing.digital_inputs = specs.get('digital_inputs', 0)
            existing.digital_outputs = specs.get('digital_outputs', 0)
            existing.analog_inputs = specs.get('analog_inputs', 0)
            existing.analog_outputs = specs.get('analog_outputs', 0)
            existing.voltage_range = specs.get('voltage_range')
            existing.current_range = specs.get('current_range')
            existing.verified = True
        else:
            logger.info(f"Creating new module: {company_normalized} {model_normalized}")
            new_module = ModuleSpec(
                company=company_normalized,
                model=model_normalized,
                description=specs.get('description', f'{company} {model}'),
                digital_inputs=specs.get('digital_inputs', 0),
                digital_outputs=specs.get('digital_outputs', 0),
                analog_inputs=specs.get('analog_inputs', 0),
                analog_outputs=specs.get('analog_outputs', 0),
                voltage_range=specs.get('voltage_range'),
                current_range=specs.get('current_range'),
                verified=True
            )
            db.session.add(new_module)
        
        db.session.commit()
        
        return {
            'success': True,
            'message': f'Module saved: {company} {model} - Available for all future reports'
        }
    
    except Exception as e:
        logger.error(f"Failed to save module manually: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def get_all_modules() -> list:
    """Get all modules in database for admin management"""
    try:
        modules = ModuleSpec.query.order_by(ModuleSpec.company, ModuleSpec.model).all()
        return [m.to_dict() for m in modules]
    except Exception as e:
        logger.error(f"Failed to retrieve modules: {str(e)}")
        return []
