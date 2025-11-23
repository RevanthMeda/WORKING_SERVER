"""
Intelligent Search API endpoints for SAT Report Generator
Provides unified search interface for templates, signals, components, etc.
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from services.intelligent_lookup import get_intelligent_lookup

search_bp = Blueprint('intelligent_search', __name__, url_prefix='/api/search')


@search_bp.route('/templates', methods=['POST'])
@login_required
def search_templates():
    """Search for SAT report templates"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'message': 'Search query required'}), 400
        
        lookup = get_intelligent_lookup('template')
        result = lookup.search(query)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 404
    
    except Exception as e:
        current_app.logger.error(f"Template search error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Search failed'}), 500


@search_bp.route('/signals', methods=['POST'])
@login_required
def search_signals():
    """Search for standard signal definitions"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'message': 'Search query required'}), 400
        
        lookup = get_intelligent_lookup('signal')
        result = lookup.search(query)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 404
    
    except Exception as e:
        current_app.logger.error(f"Signal search error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Search failed'}), 500


@search_bp.route('/components', methods=['POST'])
@login_required
def search_components():
    """Search for standard components"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'message': 'Search query required'}), 400
        
        lookup = get_intelligent_lookup('component')
        result = lookup.search(query)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 404
    
    except Exception as e:
        current_app.logger.error(f"Component search error: {e}", exc_info=True)
        return jsonify({'success': False, 'message': 'Search failed'}), 500


@search_bp.route('/add-template', methods=['POST'])
@login_required
def add_template_manual():
    """Manual entry for templates"""
    try:
        data = request.get_json()
        lookup = get_intelligent_lookup('template')
        result = lookup.add_manual_entry(data)
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        current_app.logger.error(f"Template manual entry error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save template'}), 500


@search_bp.route('/add-signal', methods=['POST'])
@login_required
def add_signal_manual():
    """Manual entry for signals"""
    try:
        data = request.get_json()
        lookup = get_intelligent_lookup('signal')
        result = lookup.add_manual_entry(data)
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        current_app.logger.error(f"Signal manual entry error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save signal'}), 500


@search_bp.route('/add-component', methods=['POST'])
@login_required
def add_component_manual():
    """Manual entry for components"""
    try:
        data = request.get_json()
        lookup = get_intelligent_lookup('component')
        result = lookup.add_manual_entry(data)
        return jsonify(result), 200 if result['success'] else 400
    except Exception as e:
        current_app.logger.error(f"Component manual entry error: {e}")
        return jsonify({'success': False, 'message': 'Failed to save component'}), 500
