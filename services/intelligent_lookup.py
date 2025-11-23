"""
Generic Intelligent Lookup Service
Implements Tier 1→2→3 search pattern for any searchable resource
Tier 1: Database lookup
Tier 2: Internal cached database
Tier 3: AI-powered search
Tier 4: Manual entry fallback
"""

from flask import current_app
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class IntelligentLookup:
    """
    Generic lookup service that can search for any resource type
    with a tiered approach: Database → Internal Cache → AI → Manual
    """
    
    def __init__(self, resource_type: str):
        """
        Initialize lookup service for a specific resource type
        resource_type: 'module', 'template', 'signal', 'component', etc.
        """
        self.resource_type = resource_type
        self.tiers_tried = []
    
    def search(self, query: str, vendor: str = None) -> Dict[str, Any]:
        """
        Execute tiered search for a resource
        Returns: {'success': bool, 'data': dict, 'source': 'database|internal|ai|manual', 'manual_required': bool}
        """
        if not query or not isinstance(query, str):
            return {'success': False, 'message': 'Invalid query'}
        
        query = query.strip().upper()
        
        # Tier 1: Database Lookup
        tier1_result = self._tier1_database_lookup(query, vendor)
        if tier1_result:
            self.tiers_tried.append('database')
            logger.info(f"Tier 1 (Database) SUCCESS for {self.resource_type}: {query}")
            return {
                'success': True,
                'data': tier1_result,
                'source': 'database',
                'manual_required': False
            }
        
        # Tier 2: Internal Cached Database
        tier2_result = self._tier2_internal_cache(query, vendor)
        if tier2_result:
            self.tiers_tried.append('internal_cache')
            logger.info(f"Tier 2 (Internal Cache) SUCCESS for {self.resource_type}: {query}")
            # Also save to database for future reference
            self._save_to_database(tier2_result)
            return {
                'success': True,
                'data': tier2_result,
                'source': 'internal_cache',
                'manual_required': False
            }
        
        # Tier 3: AI-Powered Search
        tier3_result = self._tier3_ai_search(query, vendor)
        if tier3_result:
            self.tiers_tried.append('ai')
            logger.info(f"Tier 3 (AI) SUCCESS for {self.resource_type}: {query}")
            # Save to database for future reference
            self._save_to_database(tier3_result)
            return {
                'success': True,
                'data': tier3_result,
                'source': 'ai',
                'manual_required': False
            }
        
        # All tiers failed - need manual entry
        self.tiers_tried.append('all_failed')
        logger.warning(f"All lookup tiers failed for {self.resource_type}: {query}")
        return {
            'success': False,
            'message': f'{self.resource_type.title()} "{query}" not found. Please enter details manually.',
            'source': 'none',
            'manual_required': True,
            'tiers_tried': self.tiers_tried
        }
    
    def _tier1_database_lookup(self, query: str, vendor: str = None) -> Optional[Dict]:
        """Tier 1: Search database for exact match"""
        from models import db
        
        try:
            # This would be implemented per resource type
            # For now, return None - subclasses override this
            return None
        except Exception as e:
            logger.warning(f"Tier 1 database lookup failed: {e}")
            return None
    
    def _tier2_internal_cache(self, query: str, vendor: str = None) -> Optional[Dict]:
        """Tier 2: Search internal cached database of common items"""
        # Override in subclasses with hardcoded common data
        return None
    
    def _tier3_ai_search(self, query: str, vendor: str = None) -> Optional[Dict]:
        """Tier 3: Use AI to search for information online"""
        # Override in subclasses with AI integration
        return None
    
    def _save_to_database(self, data: Dict):
        """Save discovered data to database for future lookups"""
        # Override in subclasses with proper save logic
        pass
    
    def add_manual_entry(self, data: Dict) -> Dict[str, Any]:
        """Tier 4: Manual entry fallback - user provides details"""
        try:
            result = self._save_to_database(data)
            logger.info(f"Manual entry saved for {self.resource_type}: {data}")
            return {
                'success': True,
                'message': f'{self.resource_type.title()} saved successfully',
                'data': data,
                'source': 'manual'
            }
        except Exception as e:
            logger.error(f"Error saving manual entry: {e}")
            return {
                'success': False,
                'message': 'Failed to save entry. Please check the logs.',
                'source': 'manual'
            }


class TemplateLookup(IntelligentLookup):
    """Intelligent lookup for SAT report templates"""
    
    def __init__(self):
        super().__init__('template')
        self.templates = {
            'SAT_BASIC': {
                'name': 'SAT_BASIC',
                'description': 'Basic SAT Report Template',
                'sections': ['introduction', 'test_cases', 'results'],
                'verified': True
            },
            'SAT_ADVANCED': {
                'name': 'SAT_ADVANCED',
                'description': 'Advanced SAT Report with detailed analysis',
                'sections': ['introduction', 'scope', 'test_cases', 'results', 'analysis', 'recommendations'],
                'verified': True
            }
        }
    
    def _tier2_internal_cache(self, query: str, vendor: str = None) -> Optional[Dict]:
        """Search hardcoded template list"""
        if query in self.templates:
            return self.templates[query]
        # Fuzzy search
        for key, template in self.templates.items():
            if query in key or query in template['name']:
                return template
        return None


class SignalLookup(IntelligentLookup):
    """Intelligent lookup for standard signal definitions"""
    
    def __init__(self):
        super().__init__('signal')
        self.signals = {
            'PUMP_RUN': {
                'tag': 'PUMP_RUN',
                'description': 'Pump Running Status',
                'type': 'digital_input',
                'voltage': '24VDC',
                'verified': True
            },
            'MOTOR_START': {
                'tag': 'MOTOR_START',
                'description': 'Motor Start Command',
                'type': 'digital_output',
                'voltage': '24VDC',
                'verified': True
            },
            'TEMP_AI': {
                'tag': 'TEMP_AI',
                'description': 'Temperature Analog Input',
                'type': 'analog_input',
                'range': '0-10V / 4-20mA',
                'verified': True
            }
        }
    
    def _tier2_internal_cache(self, query: str, vendor: str = None) -> Optional[Dict]:
        """Search hardcoded signal list"""
        if query in self.signals:
            return self.signals[query]
        # Fuzzy search by description
        for tag, signal in self.signals.items():
            if query in tag or query in signal['description'].upper():
                return signal
        return None


class ComponentLookup(IntelligentLookup):
    """Intelligent lookup for standard components"""
    
    def __init__(self):
        super().__init__('component')
        self.components = {
            'PLC_S71200': {
                'name': 'Siemens S7-1200',
                'type': 'PLC',
                'inputs': 64,
                'outputs': 32,
                'analog_in': 8,
                'analog_out': 8,
                'verified': True
            },
            'PANEL_ENCLOSURE': {
                'name': 'Standard Control Panel',
                'type': 'enclosure',
                'description': 'IP65 rated steel panel enclosure',
                'verified': True
            }
        }
    
    def _tier2_internal_cache(self, query: str, vendor: str = None) -> Optional[Dict]:
        """Search hardcoded component list"""
        for key, component in self.components.items():
            if query in key or query in component['name'].upper():
                return component
        return None


def get_intelligent_lookup(resource_type: str) -> IntelligentLookup:
    """Factory function to get the right lookup service"""
    if resource_type == 'template':
        return TemplateLookup()
    elif resource_type == 'signal':
        return SignalLookup()
    elif resource_type == 'component':
        return ComponentLookup()
    else:
        return IntelligentLookup(resource_type)
