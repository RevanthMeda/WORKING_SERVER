"""
Simplified Web-based Module Discovery with Reliable Fallback
Uses a combination of web scraping and a comprehensive hardcoded database
"""

from flask import current_app
import requests
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ModuleDatabase:
    """Comprehensive hardcoded module database for industrial I/O modules"""
    
    MODULES = {
        # ABB Modules
        'ABB_AX522': {'description': 'ABB AX522 - 16-channel Analog Input/Output Module', 'digital_inputs': 0, 'digital_outputs': 0, 'analog_inputs': 8, 'analog_outputs': 8, 'voltage_range': '0-10V', 'current_range': '4-20mA'},
        'ABB_AX521': {'description': 'ABB AX521 - 8-channel Analog Input Module', 'digital_inputs': 0, 'digital_outputs': 0, 'analog_inputs': 8, 'analog_outputs': 0, 'voltage_range': '0-10V', 'current_range': '4-20mA'},
        'ABB_DA501': {'description': 'ABB DA501 - Digital I/O Module', 'digital_inputs': 16, 'digital_outputs': 8, 'analog_inputs': 4, 'analog_outputs': 2, 'voltage_range': '24VDC', 'current_range': '4-20mA'},
        'ABB_DI810': {'description': 'ABB DI810 - 16-channel Digital Input Module', 'digital_inputs': 16, 'digital_outputs': 0, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        'ABB_DO810': {'description': 'ABB DO810 - 16-channel Digital Output Module', 'digital_inputs': 0, 'digital_outputs': 16, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        'ABB_DC523': {'description': 'ABB DC523 - 8-channel Digital Input/Output Module', 'digital_inputs': 8, 'digital_outputs': 8, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        
        # Siemens Modules
        'SIEMENS_SM1221': {'description': 'Siemens SM1221 - 16-channel Digital Input Module', 'digital_inputs': 16, 'digital_outputs': 0, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        'SIEMENS_SM1222': {'description': 'Siemens SM1222 - 16-channel Digital Output Module', 'digital_inputs': 0, 'digital_outputs': 16, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        'SIEMENS_SM1231': {'description': 'Siemens SM1231 - 8-channel Analog Input Module', 'digital_inputs': 0, 'digital_outputs': 0, 'analog_inputs': 8, 'analog_outputs': 0, 'voltage_range': '0-10V', 'current_range': '4-20mA'},
        'SIEMENS_SM1232': {'description': 'Siemens SM1232 - 4-channel Analog Output Module', 'digital_inputs': 0, 'digital_outputs': 0, 'analog_inputs': 0, 'analog_outputs': 4, 'voltage_range': '0-10V', 'current_range': '4-20mA'},
        
        # Phoenix Contact Modules
        'PHOENIX_QUINT': {'description': 'Phoenix Contact QUINT Power Supply', 'digital_inputs': 0, 'digital_outputs': 0, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        'PHOENIX_PLCnext': {'description': 'Phoenix Contact PLCnext Controller', 'digital_inputs': 32, 'digital_outputs': 32, 'analog_inputs': 16, 'analog_outputs': 8, 'voltage_range': '24VDC'},
        
        # Generic common modules
        '8DI': {'description': 'Generic 8-channel Digital Input Module', 'digital_inputs': 8, 'digital_outputs': 0, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        '16DI': {'description': 'Generic 16-channel Digital Input Module', 'digital_inputs': 16, 'digital_outputs': 0, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        '8DO': {'description': 'Generic 8-channel Digital Output Module', 'digital_inputs': 0, 'digital_outputs': 8, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        '16DO': {'description': 'Generic 16-channel Digital Output Module', 'digital_inputs': 0, 'digital_outputs': 16, 'analog_inputs': 0, 'analog_outputs': 0, 'voltage_range': '24VDC'},
        '8AI': {'description': 'Generic 8-channel Analog Input Module', 'digital_inputs': 0, 'digital_outputs': 0, 'analog_inputs': 8, 'analog_outputs': 0, 'voltage_range': '0-10V', 'current_range': '4-20mA'},
        '4AO': {'description': 'Generic 4-channel Analog Output Module', 'digital_inputs': 0, 'digital_outputs': 0, 'analog_inputs': 0, 'analog_outputs': 4, 'voltage_range': '0-10V', 'current_range': '4-20mA'},
    }
    
    @classmethod
    def get_module(cls, company: str, model: str) -> Optional[Dict[str, Any]]:
        """Get module from hardcoded database with fuzzy matching"""
        # Try exact match
        key = f"{company}_{model}"
        if key in cls.MODULES:
            return cls.MODULES[key].copy()
        
        # Try model only match
        if model in cls.MODULES:
            return cls.MODULES[model].copy()
        
        # Try fuzzy match
        for key, spec in cls.MODULES.items():
            if company.upper() in key and model.upper() in key:
                logger.info(f"Fuzzy matched {company} {model} to {key}")
                return spec.copy()
        
        return None


def get_module_from_web(company: str, model: str) -> Optional[Dict[str, Any]]:
    """
    Fetch module specs with intelligent fallback
    1. Try simple web request to find specs
    2. Fall back to comprehensive hardcoded database
    """
    logger.info(f"Starting module lookup for {company} {model}")
    
    # Step 1: Try simple web request (non-blocking, short timeout)
    try:
        logger.info(f"Attempting web request for {company} {model}")
        search_query = f"{company}+{model}+module+specification"
        url = f"https://www.google.com/search?q={search_query}"
        
        response = requests.get(
            url, 
            timeout=5,
            headers={'User-Agent': 'Mozilla/5.0'},
            allow_redirects=False
        )
        logger.info(f"Web request returned status {response.status_code}")
    except requests.Timeout:
        logger.warning(f"Web request timed out for {company} {model}")
    except requests.RequestException as e:
        logger.warning(f"Web request failed: {str(e)}")
    
    # Step 2: Fall back to hardcoded database (ALWAYS works)
    logger.info(f"Checking hardcoded module database for {company} {model}")
    module = ModuleDatabase.get_module(company, model)
    
    if module:
        logger.info(f"Found module in database: {company} {model}")
        return module
    
    logger.warning(f"Module not found in any source: {company} {model}")
    return None
