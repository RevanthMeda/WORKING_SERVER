"""
Utility functions for handling file downloads with proper MIME types and error handling.
"""

import os
import mimetypes
from flask import current_app, send_file, Response, jsonify
from typing import Optional, Tuple


def get_file_mime_type(file_path: str) -> str:
    """
    Get the proper MIME type for a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string
    """
    # Define explicit MIME types for Office documents
    office_mime_types = {
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.doc': 'application/msword',
        '.xls': 'application/vnd.ms-excel',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.pdf': 'application/pdf',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.zip': 'application/zip'
    }
    
    # Get file extension
    _, ext = os.path.splitext(file_path.lower())
    
    # Return explicit MIME type if known
    if ext in office_mime_types:
        return office_mime_types[ext]
    
    # Fall back to mimetypes module
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type or 'application/octet-stream'


def validate_file_integrity(file_path: str) -> Tuple[bool, str]:
    """
    Validate that a file exists and has the expected format.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    if os.path.getsize(file_path) == 0:
        return False, "File is empty"
    
    # Check file signature for DOCX files
    if file_path.lower().endswith('.docx'):
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                current_app.logger.info(f"File header for {file_path}: {header}")
                
                if header != b'PK\x03\x04':  # ZIP/DOCX file signature
                    # Check if it might be HTML content
                    f.seek(0)
                    first_1024_bytes = f.read(1024)
                    try:
                        text_content = first_1024_bytes.decode('utf-8', errors='ignore')
                        current_app.logger.error(f"File {file_path} appears to contain text/HTML content: {text_content[:200]}...")
                        if '<html' in text_content.lower() or '<!doctype' in text_content.lower():
                            return False, "File contains HTML content instead of DOCX data"
                    except:
                        pass
                    
                    return False, f"File is not a valid DOCX document (header: {header})"
                
                # Additional validation - check for ZIP central directory
                f.seek(-22, 2)  # Go to end of file minus 22 bytes (ZIP end record)
                end_record = f.read(22)
                if not end_record.startswith(b'PK\x05\x06'):
                    current_app.logger.warning(f"File {file_path} missing ZIP end record")
                
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
    
    return True, ""


def safe_send_file(file_path: str, download_name: Optional[str] = None, 
                   as_attachment: bool = True) -> Response:
    """
    Safely send a file with proper error handling and MIME type detection.
    
    Args:
        file_path: Path to the file to send
        download_name: Name for the downloaded file (optional)
        as_attachment: Whether to send as attachment
        
    Returns:
        Flask Response object
    """
    try:
        # Validate file integrity
        is_valid, error_msg = validate_file_integrity(file_path)
        if not is_valid:
            current_app.logger.error(f"File validation failed for {file_path}: {error_msg}")
            return jsonify({'error': f'File validation failed: {error_msg}'}), 400
        
        # Get proper MIME type
        mime_type = get_file_mime_type(file_path)
        
        # Use provided download name or derive from file path
        if not download_name:
            download_name = os.path.basename(file_path)
        
        current_app.logger.info(f"Sending file: {file_path} as {download_name} (MIME: {mime_type})")
        
        # Try Flask's send_file first
        try:
            response = send_file(
                file_path,
                as_attachment=as_attachment,
                download_name=download_name,
                mimetype=mime_type
            )
            current_app.logger.info(f"Flask send_file successful for {file_path}")
            return response
        except Exception as send_file_error:
            current_app.logger.error(f"Flask send_file failed for {file_path}: {send_file_error}")
            
            # Fallback: create response manually
            current_app.logger.info(f"Attempting manual file response for {file_path}")
            
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            response = Response(
                file_content,
                mimetype=mime_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{download_name}"',
                    'Content-Length': str(len(file_content)),
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )
            
            current_app.logger.info(f"Manual file response created for {file_path} ({len(file_content)} bytes)")
            return response
        
    except Exception as e:
        current_app.logger.error(f"Error sending file {file_path}: {str(e)}", exc_info=True)
        return jsonify({'error': f'File download failed: {str(e)}'}), 500


def create_download_response(file_content: bytes, filename: str, 
                           mime_type: Optional[str] = None) -> Response:
    """
    Create a download response from file content in memory.
    
    Args:
        file_content: File content as bytes
        filename: Name for the downloaded file
        mime_type: MIME type (will be guessed if not provided)
        
    Returns:
        Flask Response object
    """
    if not mime_type:
        mime_type = get_file_mime_type(filename)
    
    response = Response(
        file_content,
        mimetype=mime_type,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(file_content)),
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )
    
    current_app.logger.info(f"Created download response for {filename} (MIME: {mime_type}, Size: {len(file_content)} bytes)")
    
    return response
