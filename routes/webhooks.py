from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Webhook
from auth import role_required
import requests
import json
from datetime import datetime
import threading

webhooks_bp = Blueprint('webhooks', __name__)

@webhooks_bp.route('/manage')
@login_required
@role_required(['Admin'])
def manage_webhooks():
    """Webhook management interface"""
    try:
        webhooks = Webhook.query.all()
        return render_template('webhook_manager.html',
                             webhooks=webhooks,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error loading webhooks: {e}")
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/create', methods=['POST'])
@login_required
@role_required(['Admin'])
def create_webhook():
    """Create a new webhook"""
    try:
        data = request.json
        
        webhook = Webhook(
            name=data['name'],
            url=data['url'],
            event_type=data['event_type'],
            headers_json=json.dumps(data.get('headers', {})),
            created_by=current_user.email,
            is_active=True
        )
        
        db.session.add(webhook)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'webhook': {
                'id': webhook.id,
                'name': webhook.name,
                'url': webhook.url,
                'event_type': webhook.event_type
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error creating webhook: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/update/<int:webhook_id>', methods=['PUT'])
@login_required
@role_required(['Admin'])
def update_webhook(webhook_id):
    """Update webhook configuration"""
    try:
        webhook = Webhook.query.get_or_404(webhook_id)
        data = request.json
        
        webhook.name = data.get('name', webhook.name)
        webhook.url = data.get('url', webhook.url)
        webhook.event_type = data.get('event_type', webhook.event_type)
        webhook.is_active = data.get('is_active', webhook.is_active)
        
        if 'headers' in data:
            webhook.headers_json = json.dumps(data['headers'])
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Webhook updated successfully'})
    except Exception as e:
        current_app.logger.error(f"Error updating webhook: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/delete/<int:webhook_id>', methods=['DELETE'])
@login_required
@role_required(['Admin'])
def delete_webhook(webhook_id):
    """Delete a webhook"""
    try:
        webhook = Webhook.query.get_or_404(webhook_id)
        db.session.delete(webhook)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Webhook deleted successfully'})
    except Exception as e:
        current_app.logger.error(f"Error deleting webhook: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@webhooks_bp.route('/api/test/<int:webhook_id>', methods=['POST'])
@login_required
@role_required(['Admin'])
def test_webhook(webhook_id):
    """Test a webhook with sample data"""
    try:
        webhook = Webhook.query.get_or_404(webhook_id)
        
        # Sample payload for testing
        test_payload = {
            'event': webhook.event_type,
            'test': True,
            'timestamp': datetime.utcnow().isoformat(),
            'message': f'Test webhook from SAT Report Generator',
            'report': {
                'id': 'test-123',
                'title': 'Test Report',
                'status': 'DRAFT'
            }
        }
        
        # Send test webhook
        result = send_webhook(webhook, test_payload)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Webhook test successful',
                'response': result.get('response')
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to send webhook')
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error testing webhook: {e}")
        return jsonify({'error': str(e)}), 500

def trigger_webhook(event_type, payload):
    """Trigger all active webhooks for an event type"""
    try:
        webhooks = Webhook.query.filter_by(event_type=event_type, is_active=True).all()
        
        for webhook in webhooks:
            # Send webhook in background thread to avoid blocking
            thread = threading.Thread(target=send_webhook_async, args=(webhook, payload))
            thread.daemon = True
            thread.start()
            
    except Exception as e:
        current_app.logger.error(f"Error triggering webhooks: {e}")

def send_webhook_async(webhook, payload):
    """Send webhook asynchronously"""
    with current_app.app_context():
        send_webhook(webhook, payload)

def send_webhook(webhook, payload):
    """Send a webhook request"""
    try:
        # Parse headers
        headers = json.loads(webhook.headers_json) if webhook.headers_json else {}
        headers['Content-Type'] = 'application/json'
        
        # Send request
        response = requests.post(
            webhook.url,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        # Update webhook stats
        webhook.last_triggered = datetime.utcnow()
        webhook.trigger_count += 1
        db.session.commit()
        
        if response.status_code == 200:
            return {
                'success': True,
                'response': response.text[:500]  # Limit response size
            }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text[:500]}'
            }
            
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'Request timeout'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': str(e)}
    except Exception as e:
        current_app.logger.error(f"Error sending webhook: {e}")
        return {'success': False, 'error': str(e)}

# Event trigger functions to be called from other parts of the application

def on_report_submitted(report):
    """Trigger webhooks when a report is submitted"""
    payload = {
        'event': 'submission',
        'timestamp': datetime.utcnow().isoformat(),
        'report': {
            'id': report.id,
            'type': report.type,
            'title': report.document_title,
            'reference': report.project_reference,
            'client': report.client_name,
            'submitted_by': report.user_email,
            'status': report.status
        }
    }
    trigger_webhook('submission', payload)

def on_report_approved(report, approver, stage):
    """Trigger webhooks when a report is approved"""
    payload = {
        'event': 'approval',
        'timestamp': datetime.utcnow().isoformat(),
        'report': {
            'id': report.id,
            'type': report.type,
            'title': report.document_title,
            'reference': report.project_reference,
            'status': report.status
        },
        'approval': {
            'stage': stage,
            'approver': approver,
            'timestamp': datetime.utcnow().isoformat()
        }
    }
    trigger_webhook('approval', payload)

def on_report_rejected(report, rejector, stage, reason):
    """Trigger webhooks when a report is rejected"""
    payload = {
        'event': 'rejection',
        'timestamp': datetime.utcnow().isoformat(),
        'report': {
            'id': report.id,
            'type': report.type,
            'title': report.document_title,
            'reference': report.project_reference,
            'status': report.status
        },
        'rejection': {
            'stage': stage,
            'rejector': rejector,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        }
    }
    trigger_webhook('rejection', payload)

def on_report_completed(report):
    """Trigger webhooks when a report is completed"""
    payload = {
        'event': 'completion',
        'timestamp': datetime.utcnow().isoformat(),
        'report': {
            'id': report.id,
            'type': report.type,
            'title': report.document_title,
            'reference': report.project_reference,
            'client': report.client_name,
            'status': 'COMPLETED',
            'completion_time': datetime.utcnow().isoformat()
        }
    }
    trigger_webhook('completion', payload)