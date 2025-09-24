from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Report, ReportComment, User, Notification
import json
from datetime import datetime
import re

collaboration_bp = Blueprint('collaboration', __name__)

@collaboration_bp.route('/comments/<report_id>')
@login_required
def get_comments(report_id):
    """Get all comments for a report"""
    try:
        # Check permissions
        report = Report.query.get_or_404(report_id)
        
        # Get comments with replies
        comments = ReportComment.query.filter_by(
            report_id=report_id,
            parent_comment_id=None
        ).order_by(ReportComment.created_at.desc()).all()
        
        # Format comments for response
        comments_data = []
        for comment in comments:
            comment_data = {
                'id': comment.id,
                'user_name': comment.user_name,
                'user_email': comment.user_email,
                'text': comment.comment_text,
                'field_reference': comment.field_reference,
                'created_at': comment.created_at.isoformat(),
                'is_resolved': comment.is_resolved,
                'resolved_by': comment.resolved_by,
                'resolved_at': comment.resolved_at.isoformat() if comment.resolved_at else None,
                'replies': []
            }
            
            # Add replies
            for reply in comment.replies:
                comment_data['replies'].append({
                    'id': reply.id,
                    'user_name': reply.user_name,
                    'user_email': reply.user_email,
                    'text': reply.comment_text,
                    'created_at': reply.created_at.isoformat()
                })
            
            comments_data.append(comment_data)
        
        return jsonify({
            'success': True,
            'comments': comments_data
        })
    except Exception as e:
        current_app.logger.error(f"Error getting comments: {e}")
        return jsonify({'error': str(e)}), 500

@collaboration_bp.route('/api/add-comment', methods=['POST'])
@login_required
def add_comment():
    """Add a new comment to a report"""
    try:
        data = request.json
        report_id = data['report_id']
        comment_text = data['comment_text']
        field_reference = data.get('field_reference')
        parent_comment_id = data.get('parent_comment_id')
        
        # Check permissions
        report = Report.query.get_or_404(report_id)
        
        # Extract mentions from comment text
        mentions = extract_mentions(comment_text)
        
        # Create comment
        comment = ReportComment(
            report_id=report_id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            comment_text=comment_text,
            field_reference=field_reference,
            parent_comment_id=parent_comment_id,
            mentions_json=json.dumps(mentions) if mentions else None
        )
        
        db.session.add(comment)
        db.session.commit()
        
        # Send notifications to mentioned users
        if mentions:
            notify_mentioned_users(mentions, comment, report)
        
        # If this is a reply, notify the original comment author
        if parent_comment_id:
            parent_comment = ReportComment.query.get(parent_comment_id)
            if parent_comment and parent_comment.user_email != current_user.email:
                notify_reply(parent_comment, comment, report)
        
        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'user_name': comment.user_name,
                'text': comment.comment_text,
                'created_at': comment.created_at.isoformat()
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error adding comment: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@collaboration_bp.route('/api/resolve-comment/<int:comment_id>', methods=['POST'])
@login_required
def resolve_comment(comment_id):
    """Mark a comment as resolved"""
    try:
        comment = ReportComment.query.get_or_404(comment_id)
        
        # Check permissions (comment author or admin can resolve)
        if comment.user_email != current_user.email and current_user.role != 'Admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        comment.is_resolved = True
        comment.resolved_by = current_user.email
        comment.resolved_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Comment resolved successfully'
        })
    except Exception as e:
        current_app.logger.error(f"Error resolving comment: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@collaboration_bp.route('/api/unresolve-comment/<int:comment_id>', methods=['POST'])
@login_required
def unresolve_comment(comment_id):
    """Reopen a resolved comment"""
    try:
        comment = ReportComment.query.get_or_404(comment_id)
        
        # Check permissions
        if comment.user_email != current_user.email and current_user.role != 'Admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        comment.is_resolved = False
        comment.resolved_by = None
        comment.resolved_at = None
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Comment reopened successfully'
        })
    except Exception as e:
        current_app.logger.error(f"Error reopening comment: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@collaboration_bp.route('/api/delete-comment/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(comment_id):
    """Delete a comment"""
    try:
        comment = ReportComment.query.get_or_404(comment_id)
        
        # Check permissions (only comment author or admin can delete)
        if comment.user_email != current_user.email and current_user.role != 'Admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete replies first
        for reply in comment.replies:
            db.session.delete(reply)
        
        db.session.delete(comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Comment deleted successfully'
        })
    except Exception as e:
        current_app.logger.error(f"Error deleting comment: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@collaboration_bp.route('/api/get-users-for-mention')
@login_required
def get_users_for_mention():
    """Get list of users for @mention autocomplete"""
    try:
        query = request.args.get('q', '')
        
        users = User.query.filter(
            User.status == 'Active',
            User.full_name.ilike(f'%{query}%')
        ).limit(10).all()
        
        users_data = []
        for user in users:
            users_data.append({
                'email': user.email,
                'name': user.full_name,
                'display': f'@{user.full_name.replace(" ", "_")}'
            })
        
        return jsonify({
            'success': True,
            'users': users_data
        })
    except Exception as e:
        current_app.logger.error(f"Error getting users for mention: {e}")
        return jsonify({'error': str(e)}), 500

def extract_mentions(text):
    """Extract @mentions from comment text"""
    # Pattern to match @username mentions
    pattern = r'@(\w+(?:_\w+)*)'
    matches = re.findall(pattern, text)
    
    mentions = []
    for match in matches:
        # Convert username format back to full name
        full_name = match.replace('_', ' ')
        
        # Find user by full name
        user = User.query.filter_by(full_name=full_name).first()
        if user:
            mentions.append({
                'email': user.email,
                'name': user.full_name
            })
    
    return mentions

def notify_mentioned_users(mentions, comment, report):
    """Send notifications to mentioned users"""
    for mention in mentions:
        if mention['email'] != current_user.email:  # Don't notify self
            Notification.create_notification(
                user_email=mention['email'],
                title=f'You were mentioned in a comment',
                message=f'{current_user.full_name} mentioned you in a comment on report "{report.document_title}"',
                notification_type='mention',
                submission_id=report.id
            )

def notify_reply(parent_comment, reply_comment, report):
    """Send notification for comment reply"""
    Notification.create_notification(
        user_email=parent_comment.user_email,
        title=f'New reply to your comment',
        message=f'{current_user.full_name} replied to your comment on report "{report.document_title}"',
        notification_type='reply',
        submission_id=report.id
    )

@collaboration_bp.route('/live/<report_id>')
@login_required
def live_collaboration(report_id):
    """Live collaboration view for a report"""
    try:
        report = Report.query.get_or_404(report_id)
        
        # Get active users (mock for now - would use WebSocket in production)
        active_users = [
            {
                'name': current_user.full_name,
                'email': current_user.email,
                'avatar_color': get_avatar_color(current_user.email)
            }
        ]
        
        return render_template('live_collaboration.html',
                             report=report,
                             active_users=active_users,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error loading live collaboration: {e}")
        return jsonify({'error': str(e)}), 500

def get_avatar_color(email):
    """Generate consistent avatar color from email"""
    colors = ['#4DD0E1', '#26C6DA', '#00BCD4', '#00ACC1', '#0097A7', '#00838F']
    hash_value = sum(ord(c) for c in email)
    return colors[hash_value % len(colors)]