from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Report, SATReport, User, SavedSearch
from sqlalchemy import or_, and_, func
import json
from datetime import datetime, timedelta

search_bp = Blueprint('search', __name__)

@search_bp.route('/advanced')
@login_required
def advanced_search():
    """Advanced search interface"""
    try:
        # Get saved searches for current user
        saved_searches = SavedSearch.query.filter(
            or_(
                SavedSearch.user_email == current_user.email,
                SavedSearch.is_public == True
            )
        ).order_by(SavedSearch.last_used.desc()).all()
        
        # Get unique values for filters
        clients = db.session.query(Report.client_name).distinct().all()
        project_refs = db.session.query(Report.project_reference).distinct().all()
        statuses = ['DRAFT', 'SUBMITTED', 'TECH_APPROVED', 'PM_APPROVED', 'COMPLETED', 'REJECTED']
        report_types = ['SAT', 'FDS', 'HDS', 'FAT', 'Commissioning']
        
        return render_template('advanced_search.html',
                             saved_searches=saved_searches,
                             clients=[c[0] for c in clients if c[0]],
                             project_refs=[p[0] for p in project_refs if p[0]],
                             statuses=statuses,
                             report_types=report_types,
                             current_user=current_user)
    except Exception as e:
        current_app.logger.error(f"Error loading advanced search: {e}")
        return jsonify({'error': str(e)}), 500

@search_bp.route('/api/search', methods=['POST'])
@login_required
def search_reports():
    """Perform advanced search with multiple filters"""
    try:
        filters = request.json
        query = Report.query
        
        # Text search across multiple fields
        if filters.get('search_text'):
            search_text = f"%{filters['search_text']}%"
            query = query.filter(
                or_(
                    Report.document_title.ilike(search_text),
                    Report.project_reference.ilike(search_text),
                    Report.client_name.ilike(search_text),
                    Report.id.ilike(search_text)
                )
            )
        
        # Report type filter
        if filters.get('report_type'):
            query = query.filter(Report.type == filters['report_type'])
        
        # Status filter
        if filters.get('status'):
            if isinstance(filters['status'], list):
                query = query.filter(Report.status.in_(filters['status']))
            else:
                query = query.filter(Report.status == filters['status'])
        
        # Client filter
        if filters.get('client_name'):
            query = query.filter(Report.client_name == filters['client_name'])
        
        # Project reference filter
        if filters.get('project_reference'):
            query = query.filter(Report.project_reference == filters['project_reference'])
        
        # Date range filters
        if filters.get('date_from'):
            date_from = datetime.fromisoformat(filters['date_from'])
            query = query.filter(Report.created_at >= date_from)
        
        if filters.get('date_to'):
            date_to = datetime.fromisoformat(filters['date_to'])
            query = query.filter(Report.created_at <= date_to)
        
        # User filter (for admin/manager views)
        if filters.get('user_email') and current_user.role in ['Admin', 'Automation Manager']:
            query = query.filter(Report.user_email == filters['user_email'])
        elif current_user.role not in ['Admin', 'Automation Manager']:
            # Non-admin users only see their own reports
            query = query.filter(Report.user_email == current_user.email)
        
        # Revision filter
        if filters.get('revision'):
            query = query.filter(Report.revision == filters['revision'])
        
        # Approval status filters
        if filters.get('tm_approved') is not None:
            query = query.filter(Report.tm_approved == filters['tm_approved'])
        
        if filters.get('pm_approved') is not None:
            query = query.filter(Report.pm_approved == filters['pm_approved'])
        
        # Sorting
        sort_by = filters.get('sort_by', 'created_at')
        sort_order = filters.get('sort_order', 'desc')
        
        if hasattr(Report, sort_by):
            if sort_order == 'desc':
                query = query.order_by(getattr(Report, sort_by).desc())
            else:
                query = query.order_by(getattr(Report, sort_by))
        
        # Pagination
        page = filters.get('page', 1)
        per_page = filters.get('per_page', 20)
        
        # Execute query
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format results
        results = []
        for report in paginated.items:
            results.append({
                'id': report.id,
                'type': report.type,
                'document_title': report.document_title,
                'project_reference': report.project_reference,
                'client_name': report.client_name,
                'status': report.status,
                'revision': report.revision,
                'user_email': report.user_email,
                'created_at': report.created_at.isoformat(),
                'updated_at': report.updated_at.isoformat() if report.updated_at else None,
                'tm_approved': report.tm_approved,
                'pm_approved': report.pm_approved
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'total': paginated.total,
            'pages': paginated.pages,
            'current_page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        current_app.logger.error(f"Error searching reports: {e}")
        return jsonify({'error': str(e)}), 500

@search_bp.route('/api/save-search', methods=['POST'])
@login_required
def save_search():
    """Save a search filter for quick access"""
    try:
        data = request.json
        
        saved_search = SavedSearch(
            name=data['name'],
            user_email=current_user.email,
            filters_json=json.dumps(data['filters']),
            is_public=data.get('is_public', False)
        )
        
        db.session.add(saved_search)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'search_id': saved_search.id,
            'message': 'Search saved successfully'
        })
    except Exception as e:
        current_app.logger.error(f"Error saving search: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@search_bp.route('/api/load-search/<int:search_id>')
@login_required
def load_saved_search(search_id):
    """Load a saved search"""
    try:
        saved_search = SavedSearch.query.get_or_404(search_id)
        
        # Check permissions
        if not saved_search.is_public and saved_search.user_email != current_user.email:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update usage stats
        saved_search.last_used = datetime.utcnow()
        saved_search.use_count += 1
        db.session.commit()
        
        return jsonify({
            'success': True,
            'name': saved_search.name,
            'filters': json.loads(saved_search.filters_json)
        })
    except Exception as e:
        current_app.logger.error(f"Error loading saved search: {e}")
        return jsonify({'error': str(e)}), 500

@search_bp.route('/api/delete-search/<int:search_id>', methods=['DELETE'])
@login_required
def delete_saved_search(search_id):
    """Delete a saved search"""
    try:
        saved_search = SavedSearch.query.get_or_404(search_id)
        
        # Check permissions
        if saved_search.user_email != current_user.email and current_user.role != 'Admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(saved_search)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Search deleted successfully'})
    except Exception as e:
        current_app.logger.error(f"Error deleting saved search: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@search_bp.route('/api/quick-search')
@login_required
def quick_search():
    """Quick search for autocomplete/typeahead"""
    try:
        query_text = request.args.get('q', '')
        limit = int(request.args.get('limit', 10))
        
        if len(query_text) < 2:
            return jsonify({'results': []})
        
        search_pattern = f"%{query_text}%"
        
        # Search reports
        reports = Report.query.filter(
            and_(
                or_(
                    Report.document_title.ilike(search_pattern),
                    Report.project_reference.ilike(search_pattern),
                    Report.id.ilike(search_pattern)
                ),
                Report.user_email == current_user.email if current_user.role not in ['Admin', 'Automation Manager'] else True
            )
        ).limit(limit).all()
        
        results = []
        for report in reports:
            results.append({
                'type': 'report',
                'id': report.id,
                'title': report.document_title,
                'subtitle': f"{report.project_reference} - {report.client_name}",
                'status': report.status,
                'report_type': report.type
            })
        
        return jsonify({'results': results})
        
    except Exception as e:
        current_app.logger.error(f"Error in quick search: {e}")
        return jsonify({'error': str(e)}), 500

@search_bp.route('/api/analytics/search-stats')
@login_required
def search_analytics():
    """Get search usage analytics"""
    try:
        if current_user.role not in ['Admin', 'Automation Manager']:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Most used searches
        popular_searches = SavedSearch.query.order_by(
            SavedSearch.use_count.desc()
        ).limit(10).all()
        
        # Recent searches
        recent_searches = SavedSearch.query.order_by(
            SavedSearch.last_used.desc()
        ).limit(10).all()
        
        # Search stats
        total_searches = SavedSearch.query.count()
        public_searches = SavedSearch.query.filter_by(is_public=True).count()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_searches': total_searches,
                'public_searches': public_searches,
                'popular_searches': [
                    {
                        'name': s.name,
                        'use_count': s.use_count,
                        'created_by': s.user_email
                    } for s in popular_searches
                ],
                'recent_searches': [
                    {
                        'name': s.name,
                        'last_used': s.last_used.isoformat() if s.last_used else None,
                        'created_by': s.user_email
                    } for s in recent_searches
                ]
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error getting search analytics: {e}")
        return jsonify({'error': str(e)}), 500