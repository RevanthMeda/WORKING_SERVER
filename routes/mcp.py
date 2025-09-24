"""
MCP (Model Context Protocol) Integration Routes
Provides endpoints for MCP server functionality
"""

from flask import Blueprint, request, jsonify, current_app, session
from datetime import datetime, timezone
import logging
from typing import Dict, Any

from services.mcp_integration import (
    mcp_service, get_mcp_status, generate_intelligent_report,
    backup_report_with_mcp, schedule_reviews_with_mcp, fetch_standards_with_mcp,
    analyze_project_with_mcp
)
from services.ai_agent import process_ai_message
from flask_login import login_required

# Use login_required instead of require_auth for consistency
def require_auth(f):
    return login_required(f)

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
mcp_bp = Blueprint('mcp', __name__, url_prefix='/api/mcp')

@mcp_bp.route('/status', methods=['GET'])
@require_auth
def get_mcp_server_status():
    """Get status of all MCP servers"""
    try:
        status = get_mcp_status()
        return jsonify({
            "success": True,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"MCP status check failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/intelligent-report', methods=['POST'])
@require_auth
def create_intelligent_report():
    """Generate report using MCP sequential thinking"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        report_data = data.get('report_data', {})
        report_type = data.get('report_type', 'SAT')
        
        if not report_data:
            return jsonify({
                "success": False,
                "error": "Report data is required"
            }), 400
        
        # Generate intelligent report
        result = generate_intelligent_report(report_data, report_type)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Intelligent report generation failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/backup-report', methods=['POST'])
@require_auth
def backup_report():
    """Backup report data using MCP filesystem server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        report_id = data.get('report_id')
        report_data = data.get('report_data', {})
        
        if not report_id:
            return jsonify({
                "success": False,
                "error": "Report ID is required"
            }), 400
        
        # Backup report
        result = backup_report_with_mcp(report_id, report_data)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Report backup failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/schedule-reviews', methods=['POST'])
@require_auth
def schedule_report_reviews():
    """Schedule report reviews using MCP time server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        report_id = data.get('report_id')
        review_schedule = data.get('review_schedule', {})
        
        if not report_id or not review_schedule:
            return jsonify({
                "success": False,
                "error": "Report ID and review schedule are required"
            }), 400
        
        # Schedule reviews
        result = schedule_reviews_with_mcp(report_id, review_schedule)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Review scheduling failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/fetch-standards', methods=['POST'])
@require_auth
def fetch_external_standards():
    """Fetch external standards using MCP fetch server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        standard_type = data.get('standard_type')
        
        if not standard_type:
            return jsonify({
                "success": False,
                "error": "Standard type is required"
            }), 400
        
        # Fetch standards
        result = fetch_standards_with_mcp(standard_type)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Standards fetching failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/analyze-project', methods=['POST'])
@require_auth
def analyze_project():
    """Analyze project using MCP git and memory servers"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        project_id = data.get('project_id')
        
        if not project_id:
            return jsonify({
                "success": False,
                "error": "Project ID is required"
            }), 400
        
        # Analyze project
        result = analyze_project_with_mcp(project_id)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Project analysis failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/filesystem/upload', methods=['POST'])
@require_auth
def upload_file():
    """Upload file using MCP filesystem server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        file_path = data.get('file_path')
        file_content = data.get('file_content')
        metadata = data.get('metadata', {})
        
        if not file_path or not file_content:
            return jsonify({
                "success": False,
                "error": "File path and content are required"
            }), 400
        
        # Convert content to bytes if it's a string
        if isinstance(file_content, str):
            file_content = file_content.encode('utf-8')
        
        # Upload file
        result = mcp_service.upload_file(file_path, file_content, metadata)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/filesystem/download', methods=['POST'])
@require_auth
def download_file():
    """Download file using MCP filesystem server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({
                "success": False,
                "error": "File path is required"
            }), 400
        
        # Download file
        result = mcp_service.download_file(file_path)
        
        # Convert bytes to string for JSON response
        if result.get("success") and "data" in result.get("result", {}):
            try:
                result["result"]["data"] = result["result"]["data"].decode('utf-8')
            except UnicodeDecodeError:
                # If it's binary data, convert to base64
                import base64
                result["result"]["data"] = base64.b64encode(result["result"]["data"]).decode('utf-8')
                result["result"]["encoding"] = "base64"
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"File download failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/filesystem/list', methods=['POST'])
@require_auth
def list_files():
    """List files using MCP filesystem server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        directory_path = data.get('directory_path')
        
        if not directory_path:
            return jsonify({
                "success": False,
                "error": "Directory path is required"
            }), 400
        
        # List files
        result = mcp_service.list_files(directory_path)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"File listing failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/memory/store', methods=['POST'])
@require_auth
def store_memory():
    """Store data in MCP memory server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        key = data.get('key')
        value = data.get('value')
        tags = data.get('tags', [])
        
        if not key or value is None:
            return jsonify({
                "success": False,
                "error": "Key and value are required"
            }), 400
        
        # Store memory
        result = mcp_service.store_memory(key, value, tags)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Memory storage failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/memory/retrieve', methods=['POST'])
@require_auth
def retrieve_memory():
    """Retrieve data from MCP memory server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        key = data.get('key')
        
        if not key:
            return jsonify({
                "success": False,
                "error": "Key is required"
            }), 400
        
        # Retrieve memory
        result = mcp_service.retrieve_memory(key)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Memory retrieval failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/memory/search', methods=['POST'])
@require_auth
def search_memories():
    """Search memories using MCP memory server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        query = data.get('query')
        tags = data.get('tags', [])
        
        if not query:
            return jsonify({
                "success": False,
                "error": "Query is required"
            }), 400
        
        # Search memories
        result = mcp_service.search_memories(query, tags)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Memory search failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/sequential-thinking', methods=['POST'])
@require_auth
def execute_sequential_thinking():
    """Execute sequential thinking process using MCP server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        steps = data.get('steps', [])
        context = data.get('context', {})
        
        if not steps:
            return jsonify({
                "success": False,
                "error": "Steps are required"
            }), 400
        
        # Execute sequential thinking
        result = mcp_service.execute_sequential_thinking(steps, context)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Sequential thinking failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/time/convert', methods=['POST'])
@require_auth
def convert_timezone():
    """Convert time between timezones using MCP time server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        time_str = data.get('time')
        from_tz = data.get('from_tz', 'UTC')
        to_tz = data.get('to_tz')
        
        if not time_str or not to_tz:
            return jsonify({
                "success": False,
                "error": "Time and target timezone are required"
            }), 400
        
        # Convert timezone
        result = mcp_service.convert_timezone(time_str, from_tz, to_tz)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Timezone conversion failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/time/schedule', methods=['POST'])
@require_auth
def schedule_task():
    """Schedule task using MCP time server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        task_name = data.get('task_name')
        scheduled_time = data.get('scheduled_time')
        timezone_str = data.get('timezone', 'UTC')
        
        if not task_name or not scheduled_time:
            return jsonify({
                "success": False,
                "error": "Task name and scheduled time are required"
            }), 400
        
        # Schedule task
        result = mcp_service.schedule_task(task_name, scheduled_time, timezone_str)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Task scheduling failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/fetch/url', methods=['POST'])
@require_auth
def fetch_url():
    """Fetch content from URL using MCP fetch server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        url = data.get('url')
        headers = data.get('headers', {})
        
        if not url:
            return jsonify({
                "success": False,
                "error": "URL is required"
            }), 400
        
        # Fetch URL content
        result = mcp_service.fetch_url_content(url, headers)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"URL fetch failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@mcp_bp.route('/ai-enhanced-message', methods=['POST'])
@require_auth
def process_mcp_enhanced_message():
    """Process AI message with MCP enhancements"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No data provided"
            }), 400
        
        message = data.get('message')
        context_updates = data.get('context_updates', {})
        
        if not message:
            return jsonify({
                "success": False,
                "error": "Message is required"
            }), 400
        
        # Add MCP enhancement flag to context
        context_updates['mcp_enhanced'] = True
        context_updates['mcp_timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Process message with AI agent (now MCP-enhanced)
        result = process_ai_message(message, context_updates)
        
        return jsonify({
            "success": True,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"MCP-enhanced message processing failed: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Error handlers
@mcp_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "MCP endpoint not found"
    }), 404

@mcp_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Internal MCP server error"
    }), 500