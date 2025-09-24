"""
Background task management API endpoints.
"""
from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
from flask_login import current_user
from typing import Dict, Any, List
from datetime import datetime

from security.authentication import enhanced_login_required, role_required_api
from api.errors import APIError
from tasks import (
    send_email_task, send_bulk_email_task, send_notification_email_task,
    generate_report_task, process_report_approval_task, batch_report_generation_task,
    cleanup_old_files_task, backup_database_task, optimize_database_task,
    collect_metrics_task, health_check_task, performance_analysis_task
)
from tasks.celery_app import get_celery_app

# Create namespace
tasks_ns = Namespace('tasks', description='Background task management')

# Response models
task_result_model = tasks_ns.model('TaskResult', {
    'task_id': fields.String(description='Task ID'),
    'status': fields.String(description='Task status'),
    'result': fields.Raw(description='Task result'),
    'error': fields.String(description='Error message if failed'),
    'created_at': fields.DateTime(description='Task creation time'),
    'completed_at': fields.DateTime(description='Task completion time')
})

task_status_model = tasks_ns.model('TaskStatus', {
    'task_id': fields.String(description='Task ID'),
    'status': fields.String(description='Task status'),
    'progress': fields.Integer(description='Task progress percentage'),
    'current_step': fields.String(description='Current step description'),
    'eta': fields.String(description='Estimated completion time')
})

email_request_model = tasks_ns.model('EmailRequest', {
    'to_email': fields.String(required=True, description='Recipient email'),
    'subject': fields.String(required=True, description='Email subject'),
    'body': fields.String(required=True, description='Email body'),
    'html_body': fields.String(description='HTML email body'),
    'template_data': fields.Raw(description='Template data for personalization')
})

bulk_email_request_model = tasks_ns.model('BulkEmailRequest', {
    'email_list': fields.List(fields.Raw, required=True, description='List of email recipients'),
    'subject': fields.String(required=True, description='Email subject'),
    'body': fields.String(required=True, description='Email body'),
    'html_body': fields.String(description='HTML email body'),
    'batch_size': fields.Integer(description='Batch size for sending')
})

report_generation_request_model = tasks_ns.model('ReportGenerationRequest', {
    'report_id': fields.String(required=True, description='Report ID'),
    'output_format': fields.String(description='Output format (pdf, docx, html)')
})

batch_report_request_model = tasks_ns.model('BatchReportRequest', {
    'report_ids': fields.List(fields.String, required=True, description='List of report IDs'),
    'output_format': fields.String(description='Output format for all reports')
})


@tasks_ns.route('/email/send')
class SendEmailResource(Resource):
    """Send single email task."""
    
    @tasks_ns.expect(email_request_model)
    @tasks_ns.marshal_with(task_result_model)
    @enhanced_login_required
    @role_required_api(['Admin', 'Engineer', 'PM'])
    def post(self):
        """Send email asynchronously."""
        try:
            data = request.get_json()
            
            # Validate required fields
            if not data.get('to_email') or not data.get('subject') or not data.get('body'):
                raise APIError("Missing required fields: to_email, subject, body", 400)
            
            # Start email task
            task = send_email_task.apply_async(
                args=[
                    data['to_email'],
                    data['subject'],
                    data['body']
                ],
                kwargs={
                    'html_body': data.get('html_body'),
                    'template_data': data.get('template_data')
                }
            )
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': f'Email task started for {data["to_email"]}'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start email task: {str(e)}", 500)


@tasks_ns.route('/email/bulk')
class BulkEmailResource(Resource):
    """Send bulk email task."""
    
    @tasks_ns.expect(bulk_email_request_model)
    @tasks_ns.marshal_with(task_result_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Send bulk emails asynchronously."""
        try:
            data = request.get_json()
            
            # Validate required fields
            if not data.get('email_list') or not data.get('subject') or not data.get('body'):
                raise APIError("Missing required fields: email_list, subject, body", 400)
            
            # Start bulk email task
            task = send_bulk_email_task.apply_async(
                args=[
                    data['email_list'],
                    data['subject'],
                    data['body']
                ],
                kwargs={
                    'html_body': data.get('html_body'),
                    'batch_size': data.get('batch_size', 50)
                }
            )
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': f'Bulk email task started for {len(data["email_list"])} recipients'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start bulk email task: {str(e)}", 500)


@tasks_ns.route('/reports/generate')
class GenerateReportResource(Resource):
    """Generate report task."""
    
    @tasks_ns.expect(report_generation_request_model)
    @tasks_ns.marshal_with(task_result_model)
    @enhanced_login_required
    @role_required_api(['Admin', 'Engineer', 'PM'])
    def post(self):
        """Generate report asynchronously."""
        try:
            data = request.get_json()
            
            if not data.get('report_id'):
                raise APIError("Missing required field: report_id", 400)
            
            # Get report data
            from models import Report
            report = Report.query.get(data['report_id'])
            if not report:
                raise APIError(f"Report {data['report_id']} not found", 404)
            
            # Check permissions
            if current_user.role not in ['Admin'] and report.user_email != current_user.email:
                raise APIError("Insufficient permissions to generate this report", 403)
            
            # Prepare report data
            report_data = {
                'id': report.id,
                'type': report.type,
                'document_title': report.document_title,
                'document_reference': report.document_reference,
                'project_reference': report.project_reference,
                'client_name': report.client_name,
                'revision': report.revision,
                'prepared_by': report.prepared_by,
                'user_email': report.user_email,
                'version': report.version
            }
            
            # Start report generation task
            task = generate_report_task.apply_async(
                args=[
                    data['report_id'],
                    report.type,
                    report_data
                ],
                kwargs={
                    'output_format': data.get('output_format', 'pdf')
                }
            )
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': f'Report generation started for {data["report_id"]}'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start report generation: {str(e)}", 500)


@tasks_ns.route('/reports/batch-generate')
class BatchGenerateReportResource(Resource):
    """Batch generate reports task."""
    
    @tasks_ns.expect(batch_report_request_model)
    @tasks_ns.marshal_with(task_result_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Generate multiple reports asynchronously."""
        try:
            data = request.get_json()
            
            if not data.get('report_ids'):
                raise APIError("Missing required field: report_ids", 400)
            
            # Start batch report generation task
            task = batch_report_generation_task.apply_async(
                args=[data['report_ids']],
                kwargs={
                    'output_format': data.get('output_format', 'pdf')
                }
            )
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': f'Batch report generation started for {len(data["report_ids"])} reports'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start batch report generation: {str(e)}", 500)


@tasks_ns.route('/maintenance/cleanup')
class CleanupTaskResource(Resource):
    """File cleanup task."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Start file cleanup task."""
        try:
            data = request.get_json() or {}
            max_age_days = data.get('max_age_days', 30)
            
            task = cleanup_old_files_task.apply_async(
                args=[max_age_days]
            )
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': f'File cleanup task started (max age: {max_age_days} days)'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start cleanup task: {str(e)}", 500)


@tasks_ns.route('/maintenance/backup')
class BackupTaskResource(Resource):
    """Database backup task."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Start database backup task."""
        try:
            data = request.get_json() or {}
            backup_type = data.get('backup_type', 'incremental')
            
            task = backup_database_task.apply_async(
                args=[backup_type]
            )
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': f'{backup_type.capitalize()} backup task started'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start backup task: {str(e)}", 500)


@tasks_ns.route('/maintenance/optimize')
class OptimizeTaskResource(Resource):
    """Database optimization task."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Start database optimization task."""
        try:
            task = optimize_database_task.apply_async()
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': 'Database optimization task started'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start optimization task: {str(e)}", 500)


@tasks_ns.route('/monitoring/collect-metrics')
class CollectMetricsResource(Resource):
    """Metrics collection task."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Start metrics collection task."""
        try:
            task = collect_metrics_task.apply_async()
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': 'Metrics collection task started'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start metrics collection: {str(e)}", 500)


@tasks_ns.route('/monitoring/health-check')
class HealthCheckResource(Resource):
    """Health check task."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Start health check task."""
        try:
            task = health_check_task.apply_async()
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': 'Health check task started'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start health check: {str(e)}", 500)


@tasks_ns.route('/monitoring/performance-analysis')
class PerformanceAnalysisResource(Resource):
    """Performance analysis task."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Start performance analysis task."""
        try:
            data = request.get_json() or {}
            analysis_period_hours = data.get('analysis_period_hours', 24)
            
            task = performance_analysis_task.apply_async(
                args=[analysis_period_hours]
            )
            
            return {
                'task_id': task.id,
                'status': 'pending',
                'message': f'Performance analysis task started ({analysis_period_hours}h period)'
            }, 202
            
        except Exception as e:
            raise APIError(f"Failed to start performance analysis: {str(e)}", 500)


@tasks_ns.route('/status/<string:task_id>')
class TaskStatusResource(Resource):
    """Get task status."""
    
    @tasks_ns.marshal_with(task_status_model)
    @enhanced_login_required
    def get(self, task_id):
        """Get task status and progress."""
        try:
            celery_app = get_celery_app()
            if not celery_app:
                raise APIError("Celery not available", 503)
            
            # Get task result
            result = celery_app.AsyncResult(task_id)
            
            response = {
                'task_id': task_id,
                'status': result.status,
                'progress': 0,
                'current_step': 'Unknown',
                'eta': None
            }
            
            if result.status == 'PENDING':
                response['current_step'] = 'Task is waiting to be processed'
            elif result.status == 'PROGRESS':
                if result.info:
                    response['progress'] = result.info.get('progress', 0)
                    response['current_step'] = result.info.get('status', 'Processing')
            elif result.status == 'SUCCESS':
                response['progress'] = 100
                response['current_step'] = 'Completed successfully'
            elif result.status == 'FAILURE':
                response['current_step'] = f'Failed: {str(result.info)}'
            
            return response, 200
            
        except Exception as e:
            raise APIError(f"Failed to get task status: {str(e)}", 500)


@tasks_ns.route('/result/<string:task_id>')
class TaskResultResource(Resource):
    """Get task result."""
    
    @tasks_ns.marshal_with(task_result_model)
    @enhanced_login_required
    def get(self, task_id):
        """Get task result."""
        try:
            celery_app = get_celery_app()
            if not celery_app:
                raise APIError("Celery not available", 503)
            
            # Get task result
            result = celery_app.AsyncResult(task_id)
            
            response = {
                'task_id': task_id,
                'status': result.status,
                'result': None,
                'error': None,
                'created_at': None,
                'completed_at': None
            }
            
            if result.status == 'SUCCESS':
                response['result'] = result.result
            elif result.status == 'FAILURE':
                response['error'] = str(result.info)
            
            # Get task info if available
            if hasattr(result, 'date_done') and result.date_done:
                response['completed_at'] = result.date_done.isoformat()
            
            return response, 200
            
        except Exception as e:
            raise APIError(f"Failed to get task result: {str(e)}", 500)


@tasks_ns.route('/active')
class ActiveTasksResource(Resource):
    """Get active tasks."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get list of active tasks."""
        try:
            celery_app = get_celery_app()
            if not celery_app:
                raise APIError("Celery not available", 503)
            
            # Get active tasks from all workers
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            
            if not active_tasks:
                return {'active_tasks': [], 'worker_count': 0}, 200
            
            # Format active tasks
            formatted_tasks = []
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    formatted_tasks.append({
                        'task_id': task['id'],
                        'task_name': task['name'],
                        'worker': worker,
                        'args': task.get('args', []),
                        'kwargs': task.get('kwargs', {}),
                        'time_start': task.get('time_start')
                    })
            
            return {
                'active_tasks': formatted_tasks,
                'worker_count': len(active_tasks),
                'total_active_tasks': len(formatted_tasks)
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get active tasks: {str(e)}", 500)


@tasks_ns.route('/workers')
class WorkersResource(Resource):
    """Get worker information."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get Celery worker information."""
        try:
            celery_app = get_celery_app()
            if not celery_app:
                raise APIError("Celery not available", 503)
            
            # Get worker stats
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            
            if not stats:
                return {'workers': [], 'total_workers': 0}, 200
            
            # Format worker information
            workers = []
            for worker_name, worker_stats in stats.items():
                workers.append({
                    'name': worker_name,
                    'status': 'online',
                    'pool': worker_stats.get('pool', {}),
                    'total_tasks': worker_stats.get('total', {}),
                    'rusage': worker_stats.get('rusage', {}),
                    'clock': worker_stats.get('clock')
                })
            
            return {
                'workers': workers,
                'total_workers': len(workers)
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get worker information: {str(e)}", 500)


@tasks_ns.route('/monitoring/metrics')
class TaskMetricsResource(Resource):
    """Get task execution metrics."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get comprehensive task metrics."""
        try:
            from tasks.monitoring import get_task_monitor
            
            # Get query parameters
            hours = request.args.get('hours', 24, type=int)
            
            monitor = get_task_monitor()
            
            # Get overall metrics
            overall_metrics = monitor.get_overall_metrics(hours)
            
            # Get task type metrics
            task_type_metrics = monitor.get_task_type_metrics(hours)
            
            # Get worker metrics
            worker_metrics = monitor.get_worker_metrics()
            
            return {
                'period_hours': hours,
                'overall_metrics': overall_metrics.to_dict(),
                'task_type_metrics': {
                    name: metrics.to_dict() 
                    for name, metrics in task_type_metrics.items()
                },
                'worker_metrics': [metrics.to_dict() for metrics in worker_metrics],
                'generated_at': datetime.utcnow().isoformat()
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get task metrics: {str(e)}", 500)


@tasks_ns.route('/monitoring/report')
class TaskMonitoringReportResource(Resource):
    """Get comprehensive task monitoring report."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get comprehensive monitoring report."""
        try:
            from tasks.monitoring import get_task_monitor
            
            # Get query parameters
            hours = request.args.get('hours', 24, type=int)
            
            monitor = get_task_monitor()
            report = monitor.get_comprehensive_report(hours)
            
            return report, 200
            
        except Exception as e:
            raise APIError(f"Failed to generate monitoring report: {str(e)}", 500)


@tasks_ns.route('/monitoring/trends')
class TaskTrendsResource(Resource):
    """Get task performance trends."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get task performance trends over time."""
        try:
            from tasks.monitoring import get_task_monitor
            
            # Get query parameters
            hours = request.args.get('hours', 24, type=int)
            interval_minutes = request.args.get('interval_minutes', 60, type=int)
            
            monitor = get_task_monitor()
            trends = monitor.get_performance_trends(hours, interval_minutes)
            
            return {
                'trends': trends,
                'period_hours': hours,
                'interval_minutes': interval_minutes,
                'generated_at': datetime.utcnow().isoformat()
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get performance trends: {str(e)}", 500)


@tasks_ns.route('/monitoring/failures')
class TaskFailuresResource(Resource):
    """Get task failure statistics."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get task failure statistics and analysis."""
        try:
            from tasks.failure_handler import get_failure_handler
            
            # Get query parameters
            hours = request.args.get('hours', 24, type=int)
            
            failure_handler = get_failure_handler()
            failure_stats = failure_handler.get_failure_statistics(hours)
            
            return failure_stats, 200
            
        except Exception as e:
            raise APIError(f"Failed to get failure statistics: {str(e)}", 500)


@tasks_ns.route('/cache/stats')
class TaskCacheStatsResource(Resource):
    """Get task result cache statistics."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get task result cache statistics."""
        try:
            from tasks.result_cache import get_task_result_cache
            
            cache = get_task_result_cache()
            stats = cache.get_cache_stats()
            
            return stats, 200
            
        except Exception as e:
            raise APIError(f"Failed to get cache statistics: {str(e)}", 500)


@tasks_ns.route('/cache/cleanup')
class TaskCacheCleanupResource(Resource):
    """Clean up expired task results from cache."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Clean up expired task results."""
        try:
            from tasks.result_cache import get_task_result_cache
            
            cache = get_task_result_cache()
            cleaned_count = cache.cleanup_expired_results()
            
            return {
                'status': 'success',
                'cleaned_results': cleaned_count,
                'message': f'Cleaned up {cleaned_count} expired task results'
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to cleanup cache: {str(e)}", 500)
