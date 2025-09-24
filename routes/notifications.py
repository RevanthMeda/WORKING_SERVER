from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import current_user
from models import db, Notification
from auth import login_required
import json
from datetime import datetime

try:
    from models import db, Notification
except ImportError as e:
    print(f"Warning: Could not import models: {e}")
    db = None
    Notification = None

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/api/notifications')
def get_notifications():
    """Get notifications for current user"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'notifications': [], 'total': 0, 'pages': 0, 'current_page': 1})

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        notifications = Notification.query.filter_by(
            user_id=current_user.id
        ).order_by(Notification.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'notifications': [{
                'id': n.id,
                'type': n.type,
                'title': n.title,
                'message': n.message,
                'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
                'metadata': n.metadata
            } for n in notifications.items],
            'total': notifications.total,
            'pages': notifications.pages,
            'current_page': notifications.page
        })
    except Exception as e:
        # Return empty list when database issues occur
        current_app.logger.warning(f"Notifications not available: {e}")
        return jsonify({
            'notifications': [],
            'total': 0,
            'pages': 0,
            'current_page': 1
        })

@notifications_bp.route('/api/notifications/unread-count')
@login_required
def get_unread_count_api():
    """Get unread notifications count for current user"""
    try:
        if not current_user.is_authenticated:
            return jsonify({'count': 0})

        unread_count = Notification.query.filter_by(
            user_email=current_user.email,
            read=False
        ).count()
        return jsonify({'count': unread_count})
    except Exception as e:
        current_app.logger.warning(f"Notifications not available: {e}")
        return jsonify({'count': 0})

@notifications_bp.route('/api/notifications/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        notification = Notification.query.get(notification_id)
        if not notification or notification.user_email != current_user.email:
            return jsonify({'success': False, 'error': 'Notification not found'}), 404

        notification.read = True
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@notifications_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read for current user"""
    try:
        Notification.query.filter_by(user_email=current_user.email, read=False)\
                         .update({'read': True})
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@notifications_bp.route('/notifications')
@login_required
def notification_center():
    """Notification center page"""
    notifications = Notification.query.filter_by(user_email=current_user.email)\
                                    .order_by(Notification.created_at.desc())\
                                    .limit(50).all()

    return render_template('notification_center.html', notifications=notifications)