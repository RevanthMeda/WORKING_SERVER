"""
Optimized dashboard routes with caching and eager loading
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, make_response
from flask_login import login_required, current_user
from auth import admin_required, role_required
from models import db, User, Report, Notification, SystemSettings, SATReport
from utils import get_unread_count
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import and_, or_, func
from functools import wraps, lru_cache
import json
from datetime import datetime, timedelta
from database.query_cache import cache_manager, cache_system_stats, cache_user_reports

def no_cache(f):
    """Decorator to prevent caching of routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    return decorated_function

# Helper function for caching user notification counts
@lru_cache(maxsize=128, typed=False)
def get_cached_unread_count(user_email: str, cache_buster: int) -> int:
    """Get cached unread notification count with 5-minute TTL"""
    try:
        return Notification.query.filter_by(
            user_email=user_email,
            read=False
        ).count()
    except Exception:
        return 0

def get_unread_count_with_cache(user_email: str) -> int:
    """Get unread count with automatic cache invalidation every 5 minutes"""
    cache_buster = int(datetime.now().timestamp() // 300)  # Changes every 5 minutes
    return get_cached_unread_count(user_email, cache_buster)

class OptimizedDashboard:
    """Optimized dashboard queries with eager loading and caching"""
    
    @staticmethod
    def get_admin_stats():
        """Get admin dashboard statistics with optimized queries"""
        try:
            # Use single aggregated query for user stats
            user_stats = db.session.query(
                func.count(User.id).label('total'),
                func.sum(func.cast(User.status == 'Active', db.Integer)).label('active'),
                func.sum(func.cast(User.status == 'Pending', db.Integer)).label('pending')
            ).first()
            
            # Get report count
            total_reports = db.session.query(func.count(Report.id)).scalar() or 0
            
            return {
                'total_users': user_stats.total or 0,
                'active_users': user_stats.active or 0,
                'pending_users': user_stats.pending or 0,
                'total_reports': total_reports
            }
        except Exception as e:
            current_app.logger.error(f"Error getting admin stats: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'pending_users': 0,
                'total_reports': 0
            }
    
    @staticmethod
    def get_recent_reports_optimized(limit=5):
        """Get recent reports with eager loading to prevent N+1 queries"""
        try:
            # Eager load SAT reports to prevent N+1 queries
            reports = Report.query.options(
                joinedload(Report.sat_report)
            ).order_by(
                Report.created_at.desc()
            ).limit(limit).all()
            
            # Process reports with pre-loaded data
            for report in reports:
                if not report.status:
                    report.status = 'draft'
                
                # Use pre-loaded sat_report data
                if report.sat_report and report.sat_report.data_json:
                    try:
                        data = json.loads(report.sat_report.data_json)
                        context_data = data.get('context', {})
                        report.document_title = context_data.get('DOCUMENT_TITLE', report.document_title or 'Untitled Report')
                        report.project_reference = context_data.get('PROJECT_REFERENCE', report.project_reference or 'N/A')
                    except:
                        report.document_title = report.document_title or 'Untitled Report'
                        report.project_reference = report.project_reference or 'N/A'
                else:
                    report.document_title = report.document_title or 'Untitled Report'
                    report.project_reference = report.project_reference or 'N/A'
                
                report.status = report.status.lower() if report.status else 'draft'
            
            return reports
        except Exception as e:
            current_app.logger.error(f"Error getting recent reports: {e}")
            return []
    
    @staticmethod
    def get_pending_reports_for_user(user_email: str, stage: int):
        """Get pending reports for a specific user and approval stage"""
        try:
            # Use database filtering instead of Python filtering
            # This query uses JSON operations if the database supports it
            reports = Report.query.filter(
                Report.status == 'PENDING',
                Report.approvals_json.like(f'%"approver_email": "{user_email}"%'),
                Report.approvals_json.like(f'%"stage": {stage}%'),
                Report.approvals_json.like('%"status": "pending"%')
            ).options(
                joinedload(Report.sat_report)
            ).all()
            
            # Process the reports
            result = []
            for report in reports:
                # Parse approvals to verify the stage
                if report.approvals_json:
                    try:
                        approvals = json.loads(report.approvals_json)
                        
                        # For stage 2 (PM), check if stage 1 is approved
                        if stage == 2:
                            stage1_approved = any(
                                a.get('stage') == 1 and a.get('status') == 'approved' 
                                for a in approvals
                            )
                            if not stage1_approved:
                                continue
                        
                        # Verify this user has pending approval at this stage
                        has_pending = any(
                            a.get('stage') == stage and 
                            a.get('approver_email') == user_email and 
                            a.get('status') == 'pending'
                            for a in approvals
                        )
                        
                        if has_pending:
                            # Use pre-loaded sat_report data
                            if report.sat_report and report.sat_report.data_json:
                                try:
                                    data = json.loads(report.sat_report.data_json)
                                    context_data = data.get('context', {})
                                    report.document_title = context_data.get('DOCUMENT_TITLE', report.document_title or 'Untitled')
                                    report.project_reference = context_data.get('PROJECT_REFERENCE', report.project_reference or 'N/A')
                                    report.client_name = context_data.get('CLIENT_NAME', report.client_name or 'N/A')
                                    report.prepared_by = context_data.get('PREPARED_BY', report.prepared_by or 'N/A')
                                except:
                                    pass
                            
                            report.approval_stage = stage
                            report.approval_url = url_for('approval.approve_submission', 
                                                         submission_id=report.id, 
                                                         stage=stage)
                            result.append(report)
                    except Exception as e:
                        current_app.logger.warning(f"Error processing approvals for report {report.id}: {e}")
            
            return result
        except Exception as e:
            current_app.logger.error(f"Error getting pending reports: {e}")
            return []
    
    @staticmethod
    def get_engineer_reports(user_email: str, limit=10):
        """Get engineer's reports with optimized query"""
        try:
            reports = Report.query.filter_by(
                user_email=user_email
            ).options(
                joinedload(Report.sat_report)
            ).order_by(
                Report.created_at.desc()
            ).limit(limit).all()
            
            # Process reports
            for report in reports:
                # Calculate edit availability
                can_edit = True
                if report.approvals_json:
                    try:
                        approvals = json.loads(report.approvals_json)
                        tm_approved = any(
                            a.get("status") == "approved" and a.get("stage") == 1 
                            for a in approvals
                        )
                        can_edit = not tm_approved
                    except:
                        can_edit = True
                
                report.can_edit = can_edit
                
                # Use pre-loaded sat_report data
                if report.sat_report and report.sat_report.data_json:
                    try:
                        data = json.loads(report.sat_report.data_json)
                        context_data = data.get('context', {})
                        report.document_title = context_data.get('DOCUMENT_TITLE', report.document_title or 'Untitled')
                        report.project_reference = context_data.get('PROJECT_REFERENCE', report.project_reference or 'N/A')
                    except:
                        pass
            
            return reports
        except Exception as e:
            current_app.logger.error(f"Error getting engineer reports: {e}")
            return []