"""
Report Types Configuration System
Defines all supported report types and their characteristics
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

class ReportType(Enum):
    """Enumeration of all supported report types"""
    SAT = "SAT"  # Site Acceptance Testing
    FAT = "FAT"  # Factory Acceptance Testing
    FDS = "FDS"  # Functional Design Specification
    HDS = "HDS"  # Hardware Design Specification
    SDS = "SDS"  # Software Design Specification
    SITE_SURVEY = "SITE_SURVEY"  # Site Survey Report
    ITP = "ITP"  # Inspection and Test Plan
    COMMISSIONING = "COMMISSIONING"  # Commissioning Report
    MAINTENANCE = "MAINTENANCE"  # Maintenance Report
    TRAINING = "TRAINING"  # Training Report

@dataclass
class ReportTypeConfig:
    """Configuration for a specific report type"""
    name: str
    display_name: str
    description: str
    category: str
    icon: str
    color: str
    required_fields: List[str]
    optional_fields: List[str]
    template_path: Optional[str]
    workflow_stages: List[str]
    approval_levels: int
    estimated_completion_time: int  # in hours
    complexity_level: str  # "Simple", "Medium", "Complex"
    industry_standards: List[str]
    related_documents: List[str]

# Report type configurations
REPORT_TYPE_CONFIGS: Dict[str, ReportTypeConfig] = {
    "SAT": ReportTypeConfig(
        name="SAT",
        display_name="Site Acceptance Testing",
        description="Validates system functionality and performance at the deployment site",
        category="Testing & Validation",
        icon="🔍",
        color="#4CAF50",
        required_fields=["document_title", "client_name", "project_reference", "purpose", "scope"],
        optional_fields=["prepared_by", "user_email", "document_reference", "revision"],
        template_path="templates/SAT_Template.docx",
        workflow_stages=["Planning", "Execution", "Documentation", "Review", "Approval"],
        approval_levels=2,
        estimated_completion_time=24,
        complexity_level="Medium",
        industry_standards=["IEC 61131", "IEC 61850", "IEEE 802.11"],
        related_documents=["FAT", "FDS", "HDS", "Commissioning"]
    ),
    
    "FAT": ReportTypeConfig(
        name="FAT",
        display_name="Factory Acceptance Testing",
        description="Validates system functionality in controlled factory environment before deployment",
        category="Testing & Validation",
        icon="🏭",
        color="#FF9800",
        required_fields=["document_title", "client_name", "project_reference", "test_location", "acceptance_criteria"],
        optional_fields=["test_equipment", "prepared_by", "user_email", "document_reference"],
        template_path="templates/FAT_Template.docx",
        workflow_stages=["Preparation", "Testing", "Documentation", "Review", "Approval"],
        approval_levels=2,
        estimated_completion_time=16,
        complexity_level="Medium",
        industry_standards=["IEC 61131", "ISO 9001"],
        related_documents=["SAT", "FDS", "HDS"]
    ),
    
    "FDS": ReportTypeConfig(
        name="FDS",
        display_name="Functional Design Specification",
        description="Defines functional requirements and system behavior specifications",
        category="Design Documentation",
        icon="📋",
        color="#2196F3",
        required_fields=["document_title", "client_name", "project_reference", "functional_requirements", "process_description"],
        optional_fields=["control_philosophy", "prepared_by", "user_email", "document_reference"],
        template_path="templates/FDS_Template.docx",
        workflow_stages=["Requirements Gathering", "Design", "Documentation", "Review", "Approval"],
        approval_levels=3,
        estimated_completion_time=40,
        complexity_level="Complex",
        industry_standards=["IEC 61131", "ISA-88", "ISA-95"],
        related_documents=["HDS", "SDS", "SAT", "FAT"]
    ),
    
    "HDS": ReportTypeConfig(
        name="HDS",
        display_name="Hardware Design Specification",
        description="Specifies hardware architecture, components, and network design",
        category="Design Documentation",
        icon="🔧",
        color="#9C27B0",
        required_fields=["document_title", "client_name", "project_reference", "system_description", "hardware_components"],
        optional_fields=["network_architecture", "prepared_by", "user_email", "document_reference"],
        template_path="templates/HDS_Template.docx",
        workflow_stages=["Architecture Design", "Component Selection", "Documentation", "Review", "Approval"],
        approval_levels=3,
        estimated_completion_time=32,
        complexity_level="Complex",
        industry_standards=["IEC 61131", "IEC 61850", "IEEE 802.3"],
        related_documents=["FDS", "SDS", "SAT", "Commissioning"]
    ),
    
    "SDS": ReportTypeConfig(
        name="SDS",
        display_name="Software Design Specification",
        description="Details software architecture, algorithms, and implementation specifications",
        category="Design Documentation",
        icon="💻",
        color="#607D8B",
        required_fields=["document_title", "client_name", "project_reference", "software_architecture", "implementation_details"],
        optional_fields=["algorithms", "interfaces", "prepared_by", "user_email"],
        template_path="templates/SDS_Template.docx",
        workflow_stages=["Architecture Design", "Algorithm Design", "Documentation", "Review", "Approval"],
        approval_levels=3,
        estimated_completion_time=48,
        complexity_level="Complex",
        industry_standards=["IEC 61131-3", "IEC 61499", "ISO/IEC 12207"],
        related_documents=["FDS", "HDS", "SAT", "FAT"]
    ),
    
    "SITE_SURVEY": ReportTypeConfig(
        name="SITE_SURVEY",
        display_name="Site Survey Report",
        description="Documents site conditions, infrastructure, and requirements for system deployment",
        category="Site Assessment",
        icon="📍",
        color="#795548",
        required_fields=["site_name", "site_location", "survey_completed_by", "site_access_details"],
        optional_fields=["area_engineer", "site_caretaker", "network_configuration", "mobile_signal_strength"],
        template_path="templates/SiteSurvey_Template.docx",
        workflow_stages=["Site Visit", "Assessment", "Documentation", "Review", "Approval"],
        approval_levels=2,
        estimated_completion_time=8,
        complexity_level="Simple",
        industry_standards=["IEEE 802.11", "IEC 61850"],
        related_documents=["HDS", "Commissioning", "Installation"]
    ),
    
    "ITP": ReportTypeConfig(
        name="ITP",
        display_name="Inspection and Test Plan",
        description="Defines inspection points and testing procedures for quality assurance",
        category="Quality Assurance",
        icon="✅",
        color="#4CAF50",
        required_fields=["document_title", "client_name", "project_reference", "inspection_points", "test_procedures"],
        optional_fields=["acceptance_criteria", "hold_points", "prepared_by", "user_email"],
        template_path="templates/ITP_Template.docx",
        workflow_stages=["Planning", "Definition", "Documentation", "Review", "Approval"],
        approval_levels=2,
        estimated_completion_time=16,
        complexity_level="Medium",
        industry_standards=["ISO 9001", "IEC 61131"],
        related_documents=["SAT", "FAT", "Commissioning"]
    ),
    
    "COMMISSIONING": ReportTypeConfig(
        name="COMMISSIONING",
        display_name="Commissioning Report",
        description="Documents system commissioning activities and results",
        category="Installation & Commissioning",
        icon="⚡",
        color="#FF5722",
        required_fields=["document_title", "client_name", "project_reference", "commissioning_activities", "results"],
        optional_fields=["issues_encountered", "recommendations", "prepared_by", "user_email"],
        template_path="templates/Commissioning_Template.docx",
        workflow_stages=["Pre-commissioning", "Commissioning", "Testing", "Documentation", "Handover"],
        approval_levels=2,
        estimated_completion_time=20,
        complexity_level="Medium",
        industry_standards=["IEC 61850", "IEEE 1547"],
        related_documents=["SAT", "HDS", "Site Survey", "ITP"]
    ),
    
    "MAINTENANCE": ReportTypeConfig(
        name="MAINTENANCE",
        display_name="Maintenance Report",
        description="Documents maintenance activities, schedules, and procedures",
        category="Operations & Maintenance",
        icon="🔧",
        color="#607D8B",
        required_fields=["document_title", "client_name", "project_reference", "maintenance_activities", "schedule"],
        optional_fields=["spare_parts", "procedures", "prepared_by", "user_email"],
        template_path="templates/Maintenance_Template.docx",
        workflow_stages=["Planning", "Scheduling", "Documentation", "Review", "Approval"],
        approval_levels=1,
        estimated_completion_time=12,
        complexity_level="Simple",
        industry_standards=["ISO 55000", "IEC 62061"],
        related_documents=["Commissioning", "Training", "Operations Manual"]
    ),
    
    "TRAINING": ReportTypeConfig(
        name="TRAINING",
        display_name="Training Report",
        description="Documents training programs, materials, and completion records",
        category="Training & Documentation",
        icon="🎓",
        color="#3F51B5",
        required_fields=["document_title", "client_name", "project_reference", "training_program", "participants"],
        optional_fields=["materials", "assessment_results", "prepared_by", "user_email"],
        template_path="templates/Training_Template.docx",
        workflow_stages=["Program Design", "Material Preparation", "Delivery", "Assessment", "Documentation"],
        approval_levels=1,
        estimated_completion_time=8,
        complexity_level="Simple",
        industry_standards=["ISO 10015", "IEC 61511"],
        related_documents=["Operations Manual", "Maintenance", "User Guide"]
    )
}

def get_report_type_config(report_type: str) -> Optional[ReportTypeConfig]:
    """Get configuration for a specific report type"""
    return REPORT_TYPE_CONFIGS.get(report_type.upper())

def get_all_report_types() -> List[str]:
    """Get list of all supported report types"""
    return list(REPORT_TYPE_CONFIGS.keys())

def get_report_types_by_category() -> Dict[str, List[str]]:
    """Get report types grouped by category"""
    categories = {}
    for report_type, config in REPORT_TYPE_CONFIGS.items():
        category = config.category
        if category not in categories:
            categories[category] = []
        categories[category].append(report_type)
    return categories

def get_related_report_types(report_type: str) -> List[str]:
    """Get related report types for a given report type"""
    config = get_report_type_config(report_type)
    if config:
        return config.related_documents
    return []

def estimate_completion_time(report_type: str) -> int:
    """Get estimated completion time for a report type in hours"""
    config = get_report_type_config(report_type)
    if config:
        return config.estimated_completion_time
    return 8  # Default 8 hours

def get_complexity_level(report_type: str) -> str:
    """Get complexity level for a report type"""
    config = get_report_type_config(report_type)
    if config:
        return config.complexity_level
    return "Medium"

def get_required_fields(report_type: str) -> List[str]:
    """Get required fields for a report type"""
    config = get_report_type_config(report_type)
    if config:
        return config.required_fields
    return ["document_title", "client_name", "project_reference"]

def get_workflow_stages(report_type: str) -> List[str]:
    """Get workflow stages for a report type"""
    config = get_report_type_config(report_type)
    if config:
        return config.workflow_stages
    return ["Planning", "Documentation", "Review", "Approval"]

def get_industry_standards(report_type: str) -> List[str]:
    """Get relevant industry standards for a report type"""
    config = get_report_type_config(report_type)
    if config:
        return config.industry_standards
    return []

def validate_report_type(report_type: str) -> bool:
    """Validate if a report type is supported"""
    return report_type.upper() in REPORT_TYPE_CONFIGS

def get_report_type_summary() -> Dict[str, Any]:
    """Get summary of all report types for AI agent"""
    summary = {
        "total_types": len(REPORT_TYPE_CONFIGS),
        "categories": get_report_types_by_category(),
        "complexity_distribution": {},
        "average_completion_time": 0
    }
    
    # Calculate complexity distribution
    complexity_counts = {}
    total_time = 0
    
    for config in REPORT_TYPE_CONFIGS.values():
        complexity = config.complexity_level
        complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
        total_time += config.estimated_completion_time
    
    summary["complexity_distribution"] = complexity_counts
    summary["average_completion_time"] = total_time / len(REPORT_TYPE_CONFIGS)
    
    return summary