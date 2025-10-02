"""
Files API endpoints.
"""
from flask import request, send_file, current_app
from flask_restx import Namespace, Resource, fields
from flask_login import current_user
from werkzeug.utils import secure_filename
import os
import uuid
from datetime import datetime

from models import db
from security.authentication import enhanced_login_required
from security.validation import FileUploadSchema, validate_request_data, InputValidator
from security.audit import get_audit_logger
from monitoring.logging_config import audit_logger as app_logger

# Create namespace
files_ns = Namespace('files', description='File management operations')

# Request/Response models
file_upload_response_model = files_ns.model('FileUploadResponse', {
    'file_id': fields.String(description='Unique file identifier'),
    'filename': fields.String(description='Original filename'),
    'file_size': fields.Integer(description='File size in bytes'),
    'file_type': fields.String(description='MIME type'),
    'upload_date': fields.DateTime(description='Upload timestamp'),
    'url': fields.String(description='File access URL')
})

file_info_model = files_ns.model('FileInfo', {
    'file_id': fields.String(description='Unique file identifier'),
    'filename': fields.String(description='Original filename'),
    'file_size': fields.Integer(description='File size in bytes'),
    'file_type': fields.String(description='MIME type'),
    'upload_date': fields.DateTime(description='Upload timestamp'),
    'uploaded_by': fields.String(description='User who uploaded the file'),
    'url': fields.String(description='File access URL')
})

file_list_model = files_ns.model('FileList', {
    'files': fields.List(fields.Nested(file_info_model)),
    'total': fields.Integer(description='Total number of files'),
    'page': fields.Integer(description='Current page'),
    'per_page': fields.Integer(description='Files per page'),
    'pages': fields.Integer(description='Total pages')
})


class FileManager:
    """File management utilities."""
    
    def __init__(self):
        try:
            self.upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
            self.max_file_size = current_app.config.get('MAX_FILE_SIZE', 16 * 1024 * 1024)  # 16MB
        except RuntimeError:
            # Outside application context, use defaults
            self.upload_folder = 'uploads'
            self.max_file_size = 16 * 1024 * 1024  # 16MB
        self.allowed_extensions = {
            'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'xlsx', 'txt', 'csv'
        }
        self.allowed_mime_types = {
            'image/png', 'image/jpeg', 'image/gif',
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain', 'text/csv'
        }
    
    def is_allowed_file(self, filename, mime_type):
        """Check if file is allowed."""
        if not filename or '.' not in filename:
            return False, "File must have an extension"
        
        extension = filename.rsplit('.', 1)[1].lower()
        
        if extension not in self.allowed_extensions:
            return False, f"File type not allowed. Allowed types: {', '.join(self.allowed_extensions)}"
        
        if mime_type not in self.allowed_mime_types:
            return False, f"MIME type not allowed: {mime_type}"
        
        return True, None
    
    def save_file(self, file, report_id=None):
        """Save uploaded file."""
        if not file or not file.filename:
            return None, "No file provided"
        
        # Validate file
        is_valid, error = self.is_allowed_file(file.filename, file.content_type)
        if not is_valid:
            return None, error
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > self.max_file_size:
            return None, f"File size exceeds maximum allowed size of {self.max_file_size // (1024*1024)}MB"
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit('.', 1)[1].lower()
        stored_filename = f"{file_id}.{extension}"
        
        # Create upload directory if it doesn't exist
        upload_path = os.path.join(current_app.root_path, self.upload_folder)
        if report_id:
            upload_path = os.path.join(upload_path, 'reports', str(report_id))
        
        os.makedirs(upload_path, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_path, stored_filename)
        file.save(file_path)
        
        # Store file metadata (in a real implementation, this would go to database)
        file_metadata = {
            'file_id': file_id,
            'original_filename': original_filename,
            'stored_filename': stored_filename,
            'file_path': file_path,
            'file_size': file_size,
            'mime_type': file.content_type,
            'upload_date': datetime.utcnow(),
            'uploaded_by': current_user.id,
            'report_id': report_id
        }
        
        return file_metadata, None
    
    def get_file_path(self, file_id, report_id=None):
        """Get file path by file ID."""
        # In a real implementation, this would query the database
        # For now, we'll construct the path based on the pattern
        upload_path = os.path.join(current_app.root_path, self.upload_folder)
        if report_id:
            upload_path = os.path.join(upload_path, 'reports', str(report_id))
        
        # Find file with matching ID
        if os.path.exists(upload_path):
            for filename in os.listdir(upload_path):
                if filename.startswith(file_id):
                    return os.path.join(upload_path, filename)
        
        return None
    
    def delete_file(self, file_id, report_id=None):
        """Delete file by file ID."""
        file_path = self.get_file_path(file_id, report_id)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False


# Global file manager instance - lazy loaded
file_manager = None

def get_file_manager():
    """Get or create file manager instance."""
    global file_manager
    if file_manager is None:
        file_manager = FileManager()
    return file_manager


@files_ns.route('/upload')
class FileUploadResource(Resource):
    """File upload endpoint."""
    
    @files_ns.marshal_with(file_upload_response_model)
    @enhanced_login_required
    def post(self):
        """Upload a file."""
        if 'file' not in request.files:
            return {'message': 'No file provided'}, 400
        
        file = request.files['file']
        report_id = request.form.get('report_id')
        
        # Save file
        file_metadata, error = get_file_manager().save_file(file, report_id)
        
        if error:
            get_audit_logger().log_security_event(
                'file_upload_failed',
                severity='medium',
                details={'error': error, 'filename': file.filename}
            )
            return {'message': error}, 400
        
        # Log successful upload
        get_audit_logger().log_data_access(
            action='create',
            resource_type='file',
            resource_id=file_metadata['file_id'],
            details={
                'filename': file_metadata['original_filename'],
                'file_size': file_metadata['file_size'],
                'mime_type': file_metadata['mime_type'],
                'report_id': report_id
            }
        )
        
        return {
            'file_id': file_metadata['file_id'],
            'filename': file_metadata['original_filename'],
            'file_size': file_metadata['file_size'],
            'file_type': file_metadata['mime_type'],
            'upload_date': file_metadata['upload_date'].isoformat(),
            'url': f"/api/v1/files/{file_metadata['file_id']}"
        }, 201


@files_ns.route('/<string:file_id>')
class FileResource(Resource):
    """Individual file endpoint."""
    
    @enhanced_login_required
    def get(self, file_id):
        """Download file by ID."""
        report_id = request.args.get('report_id')
        
        # Get file path
        file_path = get_file_manager().get_file_path(file_id, report_id)
        
        if not file_path or not os.path.exists(file_path):
            return {'message': 'File not found'}, 404
        
        # Log file access
        get_audit_logger().log_data_access(
            action='read',
            resource_type='file',
            resource_id=file_id,
            details={'report_id': report_id}
        )
        
        try:
            return send_file(file_path, as_attachment=True)
        except Exception as e:
            app_logger.error(f"File download failed: {str(e)}")
            return {'message': 'File download failed'}, 500
    
    @enhanced_login_required
    def delete(self, file_id):
        """Delete file by ID."""
        report_id = request.args.get('report_id')
        
        # Check if file exists
        file_path = get_file_manager().get_file_path(file_id, report_id)
        if not file_path or not os.path.exists(file_path):
            return {'message': 'File not found'}, 404
        
        # Delete file
        if get_file_manager().delete_file(file_id, report_id):
            # Log file deletion
            get_audit_logger().log_data_access(
                action='delete',
                resource_type='file',
                resource_id=file_id,
                details={'report_id': report_id}
            )
            
            return {'message': 'File deleted successfully'}, 200
        else:
            return {'message': 'File deletion failed'}, 500


@files_ns.route('')
class FilesListResource(Resource):
    """Files list endpoint."""
    
    @files_ns.marshal_with(file_list_model)
    @enhanced_login_required
    def get(self):
        """Get list of uploaded files."""
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        report_id = request.args.get('report_id')
        
        # In a real implementation, this would query the database
        # For now, return a placeholder response
        files_data = []
        
        # Scan upload directory
        upload_path = os.path.join(current_app.root_path, get_file_manager().upload_folder)
        if report_id:
            upload_path = os.path.join(upload_path, 'reports', str(report_id))
        
        if os.path.exists(upload_path):
            for filename in os.listdir(upload_path):
                if os.path.isfile(os.path.join(upload_path, filename)):
                    file_id = filename.split('.')[0]
                    file_path = os.path.join(upload_path, filename)
                    file_stat = os.stat(file_path)
                    
                    files_data.append({
                        'file_id': file_id,
                        'filename': filename,
                        'file_size': file_stat.st_size,
                        'file_type': 'application/octet-stream',  # Would be stored in DB
                        'upload_date': datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                        'uploaded_by': current_user.id,  # Would be stored in DB
                        'url': f"/api/v1/files/{file_id}"
                    })
        
        # Simple pagination
        total = len(files_data)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_files = files_data[start:end]
        
        return {
            'files': paginated_files,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page
        }, 200


@files_ns.route('/validate')
class FileValidationResource(Resource):
    """File validation endpoint."""
    
    @enhanced_login_required
    def post(self):
        """Validate file before upload."""
        data = request.get_json()
        
        filename = data.get('filename')
        file_size = data.get('file_size')
        file_type = data.get('file_type')
        
        if not filename or not file_size or not file_type:
            return {'message': 'Filename, file_size, and file_type are required'}, 400
        
        # Validate filename
        is_valid, error = InputValidator.validate_filename(filename)
        if not is_valid:
            return {'valid': False, 'error': error}, 200
        
        # Validate file type
        is_valid, error = get_file_manager().is_allowed_file(filename, file_type)
        if not is_valid:
            return {'valid': False, 'error': error}, 200
        
        # Validate file size
        is_valid, error = InputValidator.validate_file_size(file_size)
        if not is_valid:
            return {'valid': False, 'error': error}, 200
        
        return {'valid': True, 'message': 'File validation passed'}, 200


@files_ns.route('/stats')
class FileStatsResource(Resource):
    """File statistics endpoint."""
    
    @enhanced_login_required
    def get(self):
        """Get file statistics."""
        # In a real implementation, this would query the database
        # For now, scan the upload directory
        
        total_files = 0
        total_size = 0
        file_types = {}
        
        upload_path = os.path.join(current_app.root_path, get_file_manager().upload_folder)
        
        if os.path.exists(upload_path):
            for root, dirs, files in os.walk(upload_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    if os.path.isfile(file_path):
                        total_files += 1
                        file_stat = os.stat(file_path)
                        total_size += file_stat.st_size
                        
                        # Get file extension
                        extension = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'unknown'
                        file_types[extension] = file_types.get(extension, 0) + 1
        
        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'file_types': file_types,
            'allowed_extensions': list(get_file_manager().allowed_extensions),
            'max_file_size_mb': get_file_manager().max_file_size // (1024 * 1024)
        }, 200

@files_ns.route('/delete_image')
class DeleteImageResource(Resource):
    """Delete image by URL."""

    @enhanced_login_required
    def post(self):
        """Delete an image file based on its URL."""
        data = request.get_json()
        image_url = data.get('image_url')

        if not image_url:
            return {'success': False, 'message': 'Image URL is required'}, 400

        try:
            # The URL is expected to be a path like /uploads/screenshots/some_image.png
            # Based on the configuration, this is relative to the 'static' folder.
            
            # Sanitize the image_url to prevent directory traversal attacks
            if not image_url.startswith('/uploads/'):
                get_audit_logger().log_security_event(
                    'invalid_image_delete_request',
                    severity='high',
                    details={'image_url': image_url, 'reason': 'Invalid URL prefix'}
                )
                return {'success': False, 'message': 'Invalid image URL'}, 400

            # Get the relative path from the URL, stripping the leading '/'
            relative_path = image_url.lstrip('/')
            
            # Get the absolute path to the static folder
            static_folder_path = os.path.join(current_app.root_path, 'static')
            
            # Construct the full path to the image
            file_path = os.path.join(static_folder_path, relative_path)
            
            # Normalize the path to prevent traversal attacks
            normalized_path = os.path.normpath(file_path)
            
            # Security check: ensure the path is within the static folder
            if not normalized_path.startswith(os.path.normpath(static_folder_path)):
                get_audit_logger().log_security_event(
                    'directory_traversal_attempt',
                    severity='high',
                    details={'image_url': image_url, 'resolved_path': normalized_path}
                )
                return {'success': False, 'message': 'Directory traversal attempt detected'}, 403

            if os.path.exists(normalized_path):
                os.remove(normalized_path)
                get_audit_logger().log_data_access(
                    action='delete',
                    resource_type='file',
                    resource_id=image_url,
                    details={'path': normalized_path}
                )
                return {'success': True, 'message': 'Image deleted successfully'}, 200
            else:
                # Log if the file was not found, as it might indicate an issue
                app_logger.warning(f"Attempted to delete a non-existent image: {normalized_path}")
                return {'success': False, 'message': 'Image not found'}, 404

        except Exception as e:
            app_logger.error(f"Error deleting image {image_url}: {str(e)}")
            return {'success': False, 'message': 'An unexpected error occurred'}, 500