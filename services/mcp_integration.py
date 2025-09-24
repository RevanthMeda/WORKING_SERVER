"""
MCP (Model Context Protocol) Integration Service
Integrates filesystem, git, fetch, memory, sequential thinking, and time MCP servers
"""

import json
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
import requests
from flask import current_app

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    """Configuration for MCP server connections"""
    name: str
    host: str
    port: int
    enabled: bool = True
    timeout: int = 30
    retry_attempts: int = 3

class MCPClient:
    """Enhanced MCP Client with error handling and connection management"""
    
    def __init__(self, server_url: str, timeout: int = 30):
        self.server_url = server_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'SAT-AI-Assistant/2.0'
        })
    
    def query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send query to MCP server with error handling"""
        try:
            response = self.session.post(
                f"{self.server_url}/query",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"MCP query failed: {e}")
            return {"error": str(e), "success": False}
    
    def health_check(self) -> bool:
        """Check if MCP server is healthy"""
        try:
            response = self.session.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

class MCPIntegrationService:
    """Main service for MCP server integration"""
    
    def __init__(self):
        self.servers = {
            'filesystem': MCPServerConfig('filesystem', 'localhost', 4312),
            'git': MCPServerConfig('git', 'localhost', 4322),
            'fetch': MCPServerConfig('fetch', 'localhost', 4332),
            'memory': MCPServerConfig('memory', 'localhost', 4342),
            'sequential': MCPServerConfig('sequential', 'localhost', 4352),
            'time': MCPServerConfig('time', 'localhost', 4362)
        }
        self.clients = {}
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize MCP clients for enabled servers"""
        for name, config in self.servers.items():
            if config.enabled:
                server_url = f"http://{config.host}:{config.port}"
                self.clients[name] = MCPClient(server_url, config.timeout)
                logger.info(f"Initialized MCP client for {name} at {server_url}")
    
    def get_server_status(self) -> Dict[str, bool]:
        """Get health status of all MCP servers"""
        status = {}
        for name, client in self.clients.items():
            status[name] = client.health_check()
        return status
    
    # Filesystem MCP Integration
    def upload_file(self, file_path: str, content: bytes, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Upload file using filesystem MCP server"""
        if 'filesystem' not in self.clients:
            return {"error": "Filesystem MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "filesystem.upload",
                "args": {
                    "path": file_path,
                    "data": content.hex(),  # Convert bytes to hex string
                    "metadata": metadata or {}
                }
            }
            result = self.clients['filesystem'].query(payload)
            logger.info(f"File uploaded to {file_path}")
            return result
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            return {"error": str(e), "success": False}
    
    def download_file(self, file_path: str) -> Dict[str, Any]:
        """Download file using filesystem MCP server"""
        if 'filesystem' not in self.clients:
            return {"error": "Filesystem MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "filesystem.download",
                "args": {"path": file_path}
            }
            result = self.clients['filesystem'].query(payload)
            
            if result.get('success') and 'data' in result.get('result', {}):
                # Convert hex string back to bytes
                result['result']['data'] = bytes.fromhex(result['result']['data'])
            
            return result
        except Exception as e:
            logger.error(f"File download failed: {e}")
            return {"error": str(e), "success": False}
    
    def list_files(self, directory_path: str) -> Dict[str, Any]:
        """List files in directory using filesystem MCP server"""
        if 'filesystem' not in self.clients:
            return {"error": "Filesystem MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "filesystem.list",
                "args": {"path": directory_path}
            }
            return self.clients['filesystem'].query(payload)
        except Exception as e:
            logger.error(f"File listing failed: {e}")
            return {"error": str(e), "success": False}
    
    # Git MCP Integration
    def get_commit_history(self, repo_name: str, branch: str = "main", limit: int = 10) -> Dict[str, Any]:
        """Get commit history using git MCP server"""
        if 'git' not in self.clients:
            return {"error": "Git MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "git.log",
                "args": {
                    "repo": repo_name,
                    "branch": branch,
                    "limit": limit
                }
            }
            return self.clients['git'].query(payload)
        except Exception as e:
            logger.error(f"Git history retrieval failed: {e}")
            return {"error": str(e), "success": False}
    
    def get_file_from_repo(self, repo_name: str, file_path: str, ref: str = "main") -> Dict[str, Any]:
        """Get file content from git repository"""
        if 'git' not in self.clients:
            return {"error": "Git MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "git.show_file",
                "args": {
                    "repo": repo_name,
                    "file_path": file_path,
                    "ref": ref
                }
            }
            return self.clients['git'].query(payload)
        except Exception as e:
            logger.error(f"Git file retrieval failed: {e}")
            return {"error": str(e), "success": False}
    
    def search_code(self, repo_name: str, query: str, file_pattern: str = None) -> Dict[str, Any]:
        """Search code in repository"""
        if 'git' not in self.clients:
            return {"error": "Git MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "git.search",
                "args": {
                    "repo": repo_name,
                    "query": query,
                    "file_pattern": file_pattern
                }
            }
            return self.clients['git'].query(payload)
        except Exception as e:
            logger.error(f"Code search failed: {e}")
            return {"error": str(e), "success": False}
    
    # Fetch MCP Integration
    def fetch_url_content(self, url: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Fetch content from URL using fetch MCP server"""
        if 'fetch' not in self.clients:
            return {"error": "Fetch MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "fetch.url",
                "args": {
                    "url": url,
                    "headers": headers or {}
                }
            }
            return self.clients['fetch'].query(payload)
        except Exception as e:
            logger.error(f"URL fetch failed: {e}")
            return {"error": str(e), "success": False}
    
    def fetch_api_data(self, api_url: str, method: str = "GET", data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Fetch data from API endpoint"""
        if 'fetch' not in self.clients:
            return {"error": "Fetch MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "fetch.api",
                "args": {
                    "url": api_url,
                    "method": method,
                    "data": data or {}
                }
            }
            return self.clients['fetch'].query(payload)
        except Exception as e:
            logger.error(f"API fetch failed: {e}")
            return {"error": str(e), "success": False}
    
    # Memory MCP Integration
    def store_memory(self, key: str, value: Any, tags: List[str] = None) -> Dict[str, Any]:
        """Store data in memory MCP server"""
        if 'memory' not in self.clients:
            return {"error": "Memory MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "memory.set",
                "args": {
                    "key": key,
                    "value": value,
                    "tags": tags or [],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
            return self.clients['memory'].query(payload)
        except Exception as e:
            logger.error(f"Memory storage failed: {e}")
            return {"error": str(e), "success": False}
    
    def retrieve_memory(self, key: str) -> Dict[str, Any]:
        """Retrieve data from memory MCP server"""
        if 'memory' not in self.clients:
            return {"error": "Memory MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "memory.get",
                "args": {"key": key}
            }
            return self.clients['memory'].query(payload)
        except Exception as e:
            logger.error(f"Memory retrieval failed: {e}")
            return {"error": str(e), "success": False}
    
    def search_memories(self, query: str, tags: List[str] = None) -> Dict[str, Any]:
        """Search memories by query and tags"""
        if 'memory' not in self.clients:
            return {"error": "Memory MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "memory.search",
                "args": {
                    "query": query,
                    "tags": tags or []
                }
            }
            return self.clients['memory'].query(payload)
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return {"error": str(e), "success": False}
    
    # Sequential Thinking MCP Integration
    def execute_sequential_thinking(self, steps: List[Dict[str, Any]], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute sequential thinking process"""
        if 'sequential' not in self.clients:
            return {"error": "Sequential thinking MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "sequentialthinking.run",
                "args": {
                    "steps": steps,
                    "context": context or {}
                }
            }
            return self.clients['sequential'].query(payload)
        except Exception as e:
            logger.error(f"Sequential thinking failed: {e}")
            return {"error": str(e), "success": False}
    
    def create_thinking_chain(self, task_description: str, complexity: str = "medium") -> List[Dict[str, Any]]:
        """Create a thinking chain for a given task"""
        if 'sequential' not in self.clients:
            return []
        
        try:
            payload = {
                "tool": "sequentialthinking.create_chain",
                "args": {
                    "task": task_description,
                    "complexity": complexity
                }
            }
            result = self.clients['sequential'].query(payload)
            return result.get('result', {}).get('steps', [])
        except Exception as e:
            logger.error(f"Thinking chain creation failed: {e}")
            return []
    
    # Time MCP Integration
    def convert_timezone(self, time_str: str, from_tz: str, to_tz: str) -> Dict[str, Any]:
        """Convert time between timezones"""
        if 'time' not in self.clients:
            return {"error": "Time MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "time.convert",
                "args": {
                    "time": time_str,
                    "from_tz": from_tz,
                    "to_tz": to_tz
                }
            }
            return self.clients['time'].query(payload)
        except Exception as e:
            logger.error(f"Time conversion failed: {e}")
            return {"error": str(e), "success": False}
    
    def schedule_task(self, task_name: str, scheduled_time: str, timezone_str: str = "UTC") -> Dict[str, Any]:
        """Schedule a task using time MCP server"""
        if 'time' not in self.clients:
            return {"error": "Time MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "time.schedule",
                "args": {
                    "task": task_name,
                    "time": scheduled_time,
                    "timezone": timezone_str
                }
            }
            return self.clients['time'].query(payload)
        except Exception as e:
            logger.error(f"Task scheduling failed: {e}")
            return {"error": str(e), "success": False}
    
    def get_current_time(self, timezone_str: str = "UTC") -> Dict[str, Any]:
        """Get current time in specified timezone"""
        if 'time' not in self.clients:
            return {"error": "Time MCP server not available", "success": False}
        
        try:
            payload = {
                "tool": "time.now",
                "args": {"timezone": timezone_str}
            }
            return self.clients['time'].query(payload)
        except Exception as e:
            logger.error(f"Time retrieval failed: {e}")
            return {"error": str(e), "success": False}

# Enhanced MCP Integration for SAT/AI Assistant
class SATMCPIntegration:
    """SAT-specific MCP integration with intelligent workflows"""
    
    def __init__(self, mcp_service: MCPIntegrationService):
        self.mcp = mcp_service
    
    def intelligent_report_generation(self, report_data: Dict[str, Any], report_type: str = "SAT") -> Dict[str, Any]:
        """Generate report using sequential thinking and memory"""
        
        # Step 1: Create thinking chain for report generation
        thinking_steps = self.mcp.create_thinking_chain(
            f"Generate comprehensive {report_type} report with validation and quality checks",
            complexity="high"
        )
        
        if not thinking_steps:
            thinking_steps = [
                {"step": "Validate input data completeness", "action": "validate_data"},
                {"step": "Check compliance with standards", "action": "check_compliance"},
                {"step": "Generate report sections", "action": "generate_sections"},
                {"step": "Perform quality review", "action": "quality_review"},
                {"step": "Finalize and format report", "action": "finalize_report"}
            ]
        
        # Step 2: Execute sequential thinking process
        context = {
            "report_type": report_type,
            "report_data": report_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        thinking_result = self.mcp.execute_sequential_thinking(thinking_steps, context)
        
        # Step 3: Store report generation memory
        memory_key = f"report_generation_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.mcp.store_memory(
            key=memory_key,
            value={
                "report_type": report_type,
                "thinking_process": thinking_result,
                "data_summary": self._summarize_report_data(report_data),
                "generation_timestamp": datetime.now(timezone.utc).isoformat()
            },
            tags=["report_generation", report_type.lower(), "ai_assisted"]
        )
        
        return {
            "success": True,
            "thinking_process": thinking_result,
            "memory_key": memory_key,
            "recommendations": self._generate_report_recommendations(report_data, report_type)
        }
    
    def fetch_external_standards(self, standard_type: str) -> Dict[str, Any]:
        """Fetch external standards and compliance information"""
        
        standards_urls = {
            "IEC_61131": "https://webstore.iec.ch/publication/4552",
            "IEC_61850": "https://webstore.iec.ch/publication/6028",
            "IEEE_802.11": "https://standards.ieee.org/standard/802_11-2020.html",
            "ISO_27001": "https://www.iso.org/standard/27001"
        }
        
        if standard_type in standards_urls:
            return self.mcp.fetch_url_content(standards_urls[standard_type])
        
        # Fallback: search for standards information
        search_query = f"{standard_type} automation standards compliance requirements"
        return self.mcp.fetch_url_content(f"https://www.google.com/search?q={search_query}")
    
    def analyze_project_history(self, project_id: str) -> Dict[str, Any]:
        """Analyze project history using git and memory"""
        
        # Get project memories
        project_memories = self.mcp.search_memories(
            query=project_id,
            tags=["project", "report_generation"]
        )
        
        # Get git history if available
        git_history = self.mcp.get_commit_history(
            repo_name=f"project_{project_id}",
            limit=20
        )
        
        # Analyze patterns using sequential thinking
        analysis_steps = [
            {"step": "Review project memory patterns", "data": project_memories},
            {"step": "Analyze git commit patterns", "data": git_history},
            {"step": "Identify success factors", "action": "pattern_analysis"},
            {"step": "Generate recommendations", "action": "recommendation_generation"}
        ]
        
        analysis_result = self.mcp.execute_sequential_thinking(
            analysis_steps,
            {"project_id": project_id, "analysis_type": "project_history"}
        )
        
        return {
            "project_id": project_id,
            "memory_insights": project_memories,
            "git_insights": git_history,
            "analysis": analysis_result,
            "recommendations": self._generate_project_recommendations(analysis_result)
        }
    
    def schedule_report_reviews(self, report_id: str, review_schedule: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule report reviews using time MCP server"""
        
        scheduled_tasks = []
        
        for review_type, schedule_info in review_schedule.items():
            task_result = self.mcp.schedule_task(
                task_name=f"{review_type}_review_{report_id}",
                scheduled_time=schedule_info["time"],
                timezone_str=schedule_info.get("timezone", "UTC")
            )
            
            if task_result.get("success"):
                scheduled_tasks.append({
                    "review_type": review_type,
                    "scheduled_time": schedule_info["time"],
                    "task_id": task_result.get("task_id")
                })
        
        # Store scheduling memory
        self.mcp.store_memory(
            key=f"review_schedule_{report_id}",
            value={
                "report_id": report_id,
                "scheduled_reviews": scheduled_tasks,
                "created_at": datetime.now(timezone.utc).isoformat()
            },
            tags=["scheduling", "reviews", "workflow"]
        )
        
        return {
            "success": True,
            "scheduled_tasks": scheduled_tasks,
            "total_reviews": len(scheduled_tasks)
        }
    
    def backup_report_data(self, report_id: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Backup report data using filesystem MCP server"""
        
        # Create backup file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"/backups/reports/{report_id}_{timestamp}.json"
        
        # Prepare backup data
        backup_data = {
            "report_id": report_id,
            "backup_timestamp": datetime.now(timezone.utc).isoformat(),
            "report_data": report_data,
            "metadata": {
                "version": "2.0",
                "backup_type": "automated",
                "system": "SAT_AI_Assistant"
            }
        }
        
        # Upload backup
        backup_content = json.dumps(backup_data, indent=2).encode('utf-8')
        upload_result = self.mcp.upload_file(
            file_path=backup_path,
            content=backup_content,
            metadata={"report_id": report_id, "backup_type": "automated"}
        )
        
        if upload_result.get("success"):
            # Store backup memory
            self.mcp.store_memory(
                key=f"backup_{report_id}_{timestamp}",
                value={
                    "report_id": report_id,
                    "backup_path": backup_path,
                    "backup_timestamp": datetime.now(timezone.utc).isoformat(),
                    "file_size": len(backup_content)
                },
                tags=["backup", "report_data", "automated"]
            )
        
        return upload_result
    
    def _summarize_report_data(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create summary of report data for memory storage"""
        return {
            "field_count": len(report_data),
            "has_client_info": bool(report_data.get("client_name")),
            "has_project_ref": bool(report_data.get("project_reference")),
            "completion_percentage": self._calculate_completion_percentage(report_data)
        }
    
    def _calculate_completion_percentage(self, report_data: Dict[str, Any]) -> float:
        """Calculate report completion percentage"""
        required_fields = ["client_name", "project_reference", "document_title", "purpose", "scope"]
        completed_fields = sum(1 for field in required_fields if report_data.get(field))
        return (completed_fields / len(required_fields)) * 100
    
    def _generate_report_recommendations(self, report_data: Dict[str, Any], report_type: str) -> List[str]:
        """Generate recommendations based on report data"""
        recommendations = []
        
        completion_pct = self._calculate_completion_percentage(report_data)
        
        if completion_pct < 100:
            recommendations.append("Complete all required fields before finalizing")
        
        if not report_data.get("scope"):
            recommendations.append("Define clear scope and objectives for better report quality")
        
        if report_type == "SAT" and not report_data.get("test_procedures"):
            recommendations.append("Include detailed test procedures for comprehensive SAT documentation")
        
        return recommendations
    
    def _generate_project_recommendations(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Generate project recommendations based on analysis"""
        recommendations = [
            "Continue following established project patterns",
            "Consider implementing automated quality checks",
            "Schedule regular project reviews for better outcomes"
        ]
        
        if analysis_result.get("success_rate", 0) < 0.8:
            recommendations.append("Review and improve project workflow processes")
        
        return recommendations

# Global MCP integration instance
mcp_service = MCPIntegrationService()
sat_mcp = SATMCPIntegration(mcp_service)

# Public interface functions
def get_mcp_status() -> Dict[str, Any]:
    """Get status of all MCP servers"""
    return {
        "servers": mcp_service.get_server_status(),
        "integration_active": True,
        "last_check": datetime.now(timezone.utc).isoformat()
    }

def generate_intelligent_report(report_data: Dict[str, Any], report_type: str = "SAT") -> Dict[str, Any]:
    """Generate report using MCP-enhanced intelligence"""
    return sat_mcp.intelligent_report_generation(report_data, report_type)

def backup_report_with_mcp(report_id: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
    """Backup report using MCP filesystem server"""
    return sat_mcp.backup_report_data(report_id, report_data)

def schedule_reviews_with_mcp(report_id: str, review_schedule: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule reviews using MCP time server"""
    return sat_mcp.schedule_report_reviews(report_id, review_schedule)

def fetch_standards_with_mcp(standard_type: str) -> Dict[str, Any]:
    """Fetch external standards using MCP fetch server"""
    return sat_mcp.fetch_external_standards(standard_type)

def analyze_project_with_mcp(project_id: str) -> Dict[str, Any]:
    """Analyze project using MCP git and memory servers"""
    return sat_mcp.analyze_project_history(project_id)