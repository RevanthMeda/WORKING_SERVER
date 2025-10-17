import os
import json
import re
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
import secrets

db = SQLAlchemy()

# Lazy loading flag to prevent heavy operations on import
_db_initialized = False

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=True)  # Admin, Engineer, Automation Manager, PM
    status = db.Column(db.String(20), default='Pending')  # Pending, Active, Disabled
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    requested_role = db.Column(db.String(20), nullable=True)
    # username = db.Column(db.String(50), unique=True, nullable=True) # Removed username field

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.status == 'Active'

    def __repr__(self):
        return f'<User {self.email}>'

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_setting(key, default=None):
        setting = SystemSettings.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set_setting(key, value):
        setting = SystemSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = SystemSettings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()
        return setting


class StorageConfig(db.Model):
    __tablename__ = 'storage_configs'

    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.String(64), nullable=False, default='default')
    environment = db.Column(db.String(32), nullable=False, default='production')
    upload_root = db.Column(db.String(255), nullable=False, default='static/uploads')
    image_storage_limit_gb = db.Column(db.Float, nullable=False, default=50.0)
    active_quality = db.Column(db.Integer, nullable=False, default=95)
    approved_quality = db.Column(db.Integer, nullable=False, default=80)
    archive_quality = db.Column(db.Integer, nullable=False, default=65)
    preferred_formats = db.Column(db.Text, nullable=False, default='["jpeg","png","webp"]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(120), nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)

    __table_args__ = (
        db.UniqueConstraint('org_id', 'environment', name='uq_storage_config_scope'),
    )

    def to_dict(self):
        preferred = []
        try:
            preferred = json.loads(self.preferred_formats) if self.preferred_formats else []
        except Exception:
            preferred = []
        return {
            'org_id': self.org_id,
            'environment': self.environment,
            'upload_root': self.upload_root,
            'image_storage_limit_gb': self.image_storage_limit_gb,
            'active_quality': self.active_quality,
            'approved_quality': self.approved_quality,
            'archive_quality': self.archive_quality,
            'preferred_formats': preferred,
            'version': self.version,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by': self.updated_by,
        }

    @classmethod
    def get_or_create(cls, org_id='default', environment='production'):
        instance = cls.query.filter_by(org_id=org_id, environment=environment).one_or_none()
        if instance:
            return instance
        instance = cls(org_id=org_id, environment=environment)
        db.session.add(instance)
        db.session.commit()
        return instance

    def apply_updates(self, data):
        fields = ['upload_root', 'image_storage_limit_gb', 'active_quality', 'approved_quality', 'archive_quality']
        for field in fields:
            if field in data:
                setattr(self, field, data[field])
        if 'preferred_formats' in data:
            preferred = data['preferred_formats'] or []
            self.preferred_formats = json.dumps(preferred)
        self.version = (self.version or 0) + 1


class StorageSettingsAudit(db.Model):
    __tablename__ = 'storage_settings_audit'

    id = db.Column(db.Integer, primary_key=True)
    storage_config_id = db.Column(db.Integer, db.ForeignKey('storage_configs.id'), nullable=False)
    actor_email = db.Column(db.String(120), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    changes_json = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    storage_config = db.relationship('StorageConfig', backref=db.backref('audit_entries', lazy='dynamic'))
    actor = db.relationship('User', backref=db.backref('storage_setting_audits', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'storage_config_id': self.storage_config_id,
            'actor_email': self.actor_email,
            'action': self.action,
            'changes': json.loads(self.changes_json) if self.changes_json else {},
            'ip_address': self.ip_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.String(36), primary_key=True)  # UUID
    type = db.Column(db.String(20), nullable=False)  # 'SAT', 'FDS', 'HDS', etc.
    status = db.Column(db.String(20), default='DRAFT')  # 'DRAFT', 'PENDING', 'APPROVED', etc.
    document_title = db.Column(db.String(200), nullable=True)
    document_reference = db.Column(db.String(100), nullable=True)
    project_reference = db.Column(db.String(100), nullable=True)
    client_name = db.Column(db.String(100), nullable=True)
    revision = db.Column(db.String(20), nullable=True)
    prepared_by = db.Column(db.String(100), nullable=True)
    user_email = db.Column(db.String(120), nullable=False)  # Creator
    version = db.Column(db.String(10), default='R0')  # Version tracking (R0, R1, R2, etc.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    locked = db.Column(db.Boolean, default=False)
    approvals_json = db.Column(db.Text, nullable=True)  # JSON string for approval workflow
    approval_notification_sent = db.Column(db.Boolean, default=False)
    
    # New fields for edit tracking
    submitted_at = db.Column(db.DateTime, nullable=True)  # When engineer submits to Automation Manager
    approved_at = db.Column(db.DateTime, nullable=True)  # When finally approved by Automation Manager
    approved_by = db.Column(db.String(120), nullable=True)  # Email of the approver
    edit_count = db.Column(db.Integer, default=0)  # Number of edits made

    # Relationships
    sat_report = db.relationship('SATReport', backref='parent_report', uselist=False, cascade='all, delete-orphan')
    fds_report = db.relationship('FDSReport', backref='parent_report', uselist=False, cascade='all, delete-orphan')
    hds_report = db.relationship('HDSReport', backref='parent_report', uselist=False, cascade='all, delete-orphan')
    site_survey_report = db.relationship('SiteSurveyReport', backref='parent_report', uselist=False, cascade='all, delete-orphan')
    sds_report = db.relationship('SDSReport', backref='parent_report', uselist=False, cascade='all, delete-orphan')
    fat_report = db.relationship('FATReport', backref='parent_report', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Report {self.id}: {self.type} - {self.document_title}>'

class SATReport(db.Model):
    __tablename__ = 'sat_reports'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False, unique=True)
    data_json = db.Column(db.Text, nullable=False)  # Full SAT form payload as JSON

    # Summary fields for quick access
    date = db.Column(db.String(20), nullable=True)
    purpose = db.Column(db.Text, nullable=True)
    scope = db.Column(db.Text, nullable=True)

    # Image URL storage
    scada_image_urls = db.Column(db.Text, nullable=True)  # JSON array
    trends_image_urls = db.Column(db.Text, nullable=True)  # JSON array
    alarm_image_urls = db.Column(db.Text, nullable=True)  # JSON array

    def __repr__(self):
        return f'<SATReport {self.report_id}>'

# Future report type tables (empty for now)
class FDSReport(db.Model):
    __tablename__ = 'fds_reports'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False, unique=True)
    data_json = db.Column(db.Text, nullable=False)
    system_architecture_json = db.Column(db.Text, nullable=True)
    
    # FDS specific fields
    functional_requirements = db.Column(db.Text, nullable=True)
    process_description = db.Column(db.Text, nullable=True)
    control_philosophy = db.Column(db.Text, nullable=True)

    def get_system_architecture(self):
        """Return parsed architecture layout JSON."""
        if not self.system_architecture_json:
            return None
        try:
            return json.loads(self.system_architecture_json)
        except Exception:
            return None

    def set_system_architecture(self, payload):
        """Persist architecture layout JSON."""
        if payload is None:
            self.system_architecture_json = None
            return
        if isinstance(payload, (dict, list)):
            self.system_architecture_json = json.dumps(payload)
        else:
            self.system_architecture_json = payload


class EquipmentAsset(db.Model):
    """Cached mapping between equipment models and representative imagery."""
    __tablename__ = 'equipment_assets'

    id = db.Column(db.Integer, primary_key=True)
    model_key = db.Column(db.String(200), nullable=False, unique=True)
    display_name = db.Column(db.String(200), nullable=True)
    manufacturer = db.Column(db.String(120), nullable=True)
    image_url = db.Column(db.String(500), nullable=True)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    local_path = db.Column(db.String(500), nullable=True)
    asset_source = db.Column(db.String(120), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    fetched_at = db.Column(db.DateTime, nullable=True)
    is_user_override = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_equipment_assets_model_key', 'model_key'),
    )

    def to_dict(self):
        payload = {
            "id": self.id,
            "model_key": self.model_key,
            "display_name": self.display_name,
            "manufacturer": self.manufacturer,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "local_path": self.local_path,
            "asset_source": self.asset_source,
            "confidence": self.confidence,
            "is_user_override": self.is_user_override,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.metadata_json:
            try:
                payload["metadata"] = json.loads(self.metadata_json)
            except Exception:
                payload["metadata_raw"] = self.metadata_json
        return payload

    @classmethod
    def normalize_model_key(cls, raw_model: str) -> str:
        if not raw_model:
            return ''
        normalized = re.sub(r'[^a-z0-9]+', '-', raw_model.strip().lower())
        return normalized.strip('-')

    @classmethod
    def get_or_create(cls, model_key: str) -> "EquipmentAsset":
        """Fetch cached asset for model key or create placeholder."""
        if not model_key:
            raise ValueError("model_key is required")
        asset = cls.query.filter_by(model_key=model_key).first()
        if asset:
            return asset
        asset = cls(model_key=model_key)
        db.session.add(asset)
        db.session.commit()
        return asset

class HDSReport(db.Model):
    __tablename__ = 'hds_reports'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False, unique=True)
    data_json = db.Column(db.Text, nullable=False)
    
    # HDS specific fields
    system_description = db.Column(db.Text, nullable=True)
    hardware_components = db.Column(db.Text, nullable=True)  # JSON array
    network_architecture = db.Column(db.Text, nullable=True)

class SiteSurveyReport(db.Model):
    __tablename__ = 'site_survey_reports'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False, unique=True)
    data_json = db.Column(db.Text, nullable=False)
    
    # SCADA Migration specific fields
    site_name = db.Column(db.String(200), nullable=True)
    site_location = db.Column(db.Text, nullable=True)
    site_access_details = db.Column(db.Text, nullable=True)
    area_engineer = db.Column(db.String(200), nullable=True)
    site_caretaker = db.Column(db.String(200), nullable=True)
    survey_completed_by = db.Column(db.String(200), nullable=True)
    
    # Hardware details
    plc_details = db.Column(db.Text, nullable=True)  # JSON for PLC specifications
    hmi_details = db.Column(db.Text, nullable=True)  # JSON for HMI specifications
    router_details = db.Column(db.Text, nullable=True)  # JSON for router specifications
    network_equipment = db.Column(db.Text, nullable=True)  # JSON for additional network equipment
    
    # Communications
    network_configuration = db.Column(db.Text, nullable=True)  # JSON for IP, ports, gateways
    mobile_signal_strength = db.Column(db.Text, nullable=True)  # JSON for signal measurements
    
    # Plant SCADA details
    local_scada_details = db.Column(db.Text, nullable=True)  # JSON for local SCADA system info
    
    # Pre-departure checklist
    verification_checklist = db.Column(db.Text, nullable=True)  # JSON for checklist items

class SDSReport(db.Model):
    __tablename__ = 'sds_reports'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False, unique=True)
    data_json = db.Column(db.Text, nullable=False)

class FATReport(db.Model):
    __tablename__ = 'fat_reports'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False, unique=True)
    data_json = db.Column(db.Text, nullable=False)
    
    # FAT specific fields
    test_location = db.Column(db.String(200), nullable=True)
    test_equipment = db.Column(db.Text, nullable=True)  # JSON array
    acceptance_criteria = db.Column(db.Text, nullable=True)

class CullyStatistics(db.Model):
    """Model to store Cully website statistics that auto-sync"""
    __tablename__ = 'cully_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    instruments_count = db.Column(db.String(10), default='22k')
    engineers_count = db.Column(db.String(10), default='46')
    experience_years = db.Column(db.String(10), default='600+')
    water_plants = db.Column(db.String(10), default='250')
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    fetch_successful = db.Column(db.Boolean, default=True)
    error_message = db.Column(db.String(500), nullable=True)
    
    def to_dict(self) -> Dict[str, Optional[str]]:
        """Convert to dictionary for easy template rendering"""
        return {
            'instruments': self.instruments_count,
            'engineers': self.engineers_count,
            'experience': self.experience_years,
            'plants': self.water_plants,
            'last_updated': self.last_updated.strftime('%Y-%m-%d %H:%M:%S') if self.last_updated else None
        }

    @staticmethod
    def get_current_statistics() -> Dict[str, Optional[str]]:
        """Get current statistics from database"""
        try:
            # First ensure the table exists
            try:
                db.create_all()
            except Exception:
                pass  # Ignore table creation errors
            
            stats_record = CullyStatistics.query.first()
            if stats_record:
                return stats_record.to_dict()
            else:
                # Return defaults if no record exists
                default_stats = {
                    'instruments': '22k',
                    'engineers': '46',
                    'experience': '600+',
                    'plants': '250',
                    'last_updated': None
                }
                
                # Try to create a default record
                try:
                    new_stats = CullyStatistics()
                    db.session.add(new_stats)
                    db.session.commit()
                    current_app.logger.info("Created default Cully statistics record")
                except Exception as create_error:
                    current_app.logger.warning(f"Could not create default statistics: {create_error}")
                    db.session.rollback()
                
                return default_stats
                
        except Exception as e:
            current_app.logger.error(f"Error getting statistics: {str(e)}")
            return {
                'instruments': '22k',
                'engineers': '46', 
                'experience': '600+',
                'plants': '250',
                'last_updated': None
            }

    @staticmethod
    def fetch_and_update_from_cully() -> bool:
        """Fetch current statistics from Cully.ie website and update database"""
        try:
            response = requests.get(
                "https://www.cully.ie/",
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            response.raise_for_status()
            
            # Extract statistics from HTML content
            text_content = response.text
            
            # Default values
            stats = {
                'instruments': '22k',
                'engineers': '46',
                'experience': '600+',
                'plants': '250'
            }
            
            # Extract numbers using regex patterns
            instruments_match = re.search(r'(\d+k?)\s*.*(?:instruments|Instruments)', text_content, re.IGNORECASE)
            if instruments_match:
                stats['instruments'] = instruments_match.group(1)
            
            engineers_match = re.search(r'(\d+)\s*.*(?:engineers|Engineers)', text_content, re.IGNORECASE) 
            if engineers_match:
                stats['engineers'] = engineers_match.group(1)
                
            experience_match = re.search(r'(\d+\+?)\s*.*(?:years|Years)', text_content, re.IGNORECASE)
            if experience_match:
                stats['experience'] = experience_match.group(1)
                
            plants_match = re.search(r'(\d+)\s*.*(?:water plants|Water plants)', text_content, re.IGNORECASE)
            if plants_match:
                stats['plants'] = plants_match.group(1)
            
            # Update or create statistics record
            existing = CullyStatistics.query.first()
            if existing:
                existing.instruments_count = stats['instruments']
                existing.engineers_count = stats['engineers']
                existing.experience_years = stats['experience']
                existing.water_plants = stats['plants']
                existing.last_updated = datetime.utcnow()
                existing.fetch_successful = True
                existing.error_message = None
            else:
                new_stats = CullyStatistics(
                    instruments_count=stats['instruments'],
                    engineers_count=stats['engineers'],
                    experience_years=stats['experience'],
                    water_plants=stats['plants'],
                    fetch_successful=True
                )
                db.session.add(new_stats)
            
            db.session.commit()
            current_app.logger.info(f"Successfully updated Cully statistics: {stats}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error fetching/updating Cully statistics: {str(e)}")
            # Update error status but keep existing data
            existing = CullyStatistics.query.first()
            if existing:
                existing.fetch_successful = False
                existing.error_message = str(e)
                existing.last_updated = datetime.utcnow()
                db.session.commit()
            return False


class ReportTemplate(db.Model):
    """Store and manage report templates with versioning"""
    __tablename__ = 'report_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # SAT, FDS, HDS, FAT, etc.
    version = db.Column(db.String(10), nullable=False, default='1.0')
    description = db.Column(db.Text, nullable=True)
    template_file = db.Column(db.String(200), nullable=True)  # Path to docx template
    fields_json = db.Column(db.Text, nullable=True)  # JSON array of required fields
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    usage_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<ReportTemplate {self.name} v{self.version}>'

class UserAnalytics(db.Model):
    """Track user performance metrics and KPIs"""
    __tablename__ = 'user_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    date = db.Column(db.Date, nullable=False)
    reports_created = db.Column(db.Integer, default=0)
    reports_approved = db.Column(db.Integer, default=0)
    reports_rejected = db.Column(db.Integer, default=0)
    avg_completion_time = db.Column(db.Float, default=0.0)  # in hours
    approval_cycle_time = db.Column(db.Float, default=0.0)  # in hours
    on_time_percentage = db.Column(db.Float, default=100.0)
    
    # JSON field for additional custom metrics
    custom_metrics = db.Column(db.Text, nullable=True)
    
    def __repr__(self):
        return f'<UserAnalytics {self.user_email} - {self.date}>'

class ReportVersion(db.Model):
    """Track document versions and changes"""
    __tablename__ = 'report_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False)
    version_number = db.Column(db.String(10), nullable=False)  # R0, R1, R2, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(120), nullable=False)
    change_summary = db.Column(db.Text, nullable=True)
    data_snapshot = db.Column(db.Text, nullable=False)  # JSON snapshot of report data
    file_path = db.Column(db.String(200), nullable=True)  # Path to generated document
    is_current = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<ReportVersion {self.report_id} - {self.version_number}>'

class ReportComment(db.Model):
    """Comments and collaboration on reports"""
    __tablename__ = 'report_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    comment_text = db.Column(db.Text, nullable=False)
    field_reference = db.Column(db.String(100), nullable=True)  # Which field/section comment refers to
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_resolved = db.Column(db.Boolean, default=False)
    resolved_by = db.Column(db.String(120), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey('report_comments.id'), nullable=True)
    mentions_json = db.Column(db.Text, nullable=True)  # JSON array of mentioned users
    
    # Self-referential relationship for comment threads
    replies = db.relationship('ReportComment', backref=db.backref('parent', remote_side=[id]))
    
    def __repr__(self):
        return f'<ReportComment {self.id} on {self.report_id}>'

class Webhook(db.Model):
    """Store webhook configurations for workflow automation"""
    __tablename__ = 'webhooks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # submission, approval, rejection, completion
    is_active = db.Column(db.Boolean, default=True)
    headers_json = db.Column(db.Text, nullable=True)  # JSON for custom headers
    created_by = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_triggered = db.Column(db.DateTime, nullable=True)
    trigger_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<Webhook {self.name} - {self.event_type}>'

class SavedSearch(db.Model):
    """Store saved search filters for quick access"""
    __tablename__ = 'saved_searches'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)
    filters_json = db.Column(db.Text, nullable=False)  # JSON of search criteria
    is_public = db.Column(db.Boolean, default=False)  # Share with team
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used = db.Column(db.DateTime, nullable=True)
    use_count = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<SavedSearch {self.name} by {self.user_email}>'


class ReportArchive(db.Model):
    """Archive old reports based on retention policies"""
    __tablename__ = 'report_archives'
    
    id = db.Column(db.Integer, primary_key=True)
    original_report_id = db.Column(db.String(36), nullable=False)
    report_type = db.Column(db.String(20), nullable=False)
    document_title = db.Column(db.String(200), nullable=False)
    project_reference = db.Column(db.String(100), nullable=False)
    client_name = db.Column(db.String(100), nullable=False)
    archived_data = db.Column(db.Text, nullable=False)  # Compressed JSON
    archived_by = db.Column(db.String(120), nullable=False)
    archived_at = db.Column(db.DateTime, default=datetime.utcnow)
    retention_until = db.Column(db.DateTime, nullable=False)
    file_paths_json = db.Column(db.Text, nullable=True)  # Paths to archived files
    
    def __repr__(self):
        return f'<ReportArchive {self.original_report_id} - {self.document_title}>'



class ScheduledReport(db.Model):
    """Scheduled report generation tasks"""
    __tablename__ = 'scheduled_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('report_templates.id'), nullable=False)
    schedule_type = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly
    schedule_config = db.Column(db.Text, nullable=False)  # JSON cron-like config
    user_email = db.Column(db.String(120), nullable=False)
    recipient_emails = db.Column(db.Text, nullable=False)  # JSON array of emails
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime, nullable=True)
    next_run = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ScheduledReport {self.name} - {self.schedule_type}>'

def init_db(app):
    """Initialize database with proper error handling - optimized"""
    try:
        # Ensure instance directory exists
        instance_dir = os.path.join(app.config.get('BASE_DIR', os.getcwd()), 'instance')
        os.makedirs(instance_dir, exist_ok=True)

        # Check if we should fall back to SQLite
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
        disable_fallback = os.environ.get('DISABLE_SQLITE_FALLBACK') == '1'
        
        # If PostgreSQL connection fails, fall back to SQLite
        if 'postgresql' in db_uri:
            try:
                # Test PostgreSQL connection first
                from sqlalchemy import create_engine
                test_engine = create_engine(db_uri)
                from sqlalchemy import text
                with test_engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
                app.logger.info("PostgreSQL connection successful")
            except Exception as pg_error:
                app.logger.warning(f"PostgreSQL connection failed: {pg_error}")
                if disable_fallback:
                    raise
                app.logger.info("Falling back to SQLite database...")
                
                # Fall back to SQLite
                sqlite_path = os.path.join(instance_dir, 'sat_reports.db')
                app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{sqlite_path}'
                app.logger.info(f"Using SQLite database: {sqlite_path}")

        db.init_app(app)

        with app.app_context():
            # Test database connection
            try:
                from sqlalchemy import text
                with db.engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
                app.logger.info(f"Database connection successful: {app.config['SQLALCHEMY_DATABASE_URI']}")
            except Exception as conn_error:
                app.logger.error(f"Database connection failed: {conn_error}")
                # Try to create the database file and directories
                try:
                    db.create_all()
                    app.logger.info("Database file created successfully")
                    return True  # Return early if we created database
                except Exception as create_error:
                    app.logger.error(f"Could not create database: {create_error}")
                    return False

            # Only create tables if they don't exist - check first!
            try:
                inspector = db.inspect(db.engine)
                existing_tables = inspector.get_table_names()
                
                if not existing_tables or len(existing_tables) == 0:
                    db.create_all()
                    app.logger.info("Database tables created successfully")
                else:
                    app.logger.debug(f"Database tables already exist: {len(existing_tables)} tables found")
                    required_tables = { 'storage_configs': StorageConfig.__table__, 'storage_settings_audit': StorageSettingsAudit.__table__ }
                    missing = [name for name in required_tables if name not in existing_tables]
                    if missing:
                        for table_name in missing:
                            try:
                                required_tables[table_name].create(db.engine, checkfirst=True)
                                app.logger.info(f"Created missing table: {table_name}")
                            except Exception as table_create_error:
                                app.logger.error(f"Failed to create table {table_name}: {table_create_error}", exc_info=True)
                                raise
            except Exception as table_error:
                app.logger.error(f"Error checking/creating tables: {table_error}")
                return False
            
            # Skip migration check on every startup - only run when needed
            # This migration is now handled via CLI commands
            # Comment out for performance - migration should be run manually
            # try:
            #     from database.fix_missing_columns import ensure_database_ready
            #     migration_success = ensure_database_ready(app, db)
            # except Exception:
            #     pass

            # Create default admin user if it doesn't exist
            try:
                admin_user = User.query.filter_by(email='admin@cullyautomation.com').first()
                if not admin_user:
                    admin_user = User(
                        email='admin@cullyautomation.com',
                        full_name='System Administrator',
                        role='Admin',
                        status='Active'
                    )
                    admin_user.set_password('admin123')  # Change this in production
                    db.session.add(admin_user)
                    db.session.commit()
                    app.logger.info("Default admin user created")
            except Exception as user_error:
                app.logger.warning(f"Could not create admin user: {user_error}")
                try:
                    db.session.rollback()
                except:
                    pass

            # Initialize system settings
            try:
                default_settings = [
                    ('company_name', 'Cully Automation'),
                    ('company_logo', 'static/img/cully.png'),
                    ('default_storage_location', 'static/uploads')
                ]

                for key, value in default_settings:
                    existing = SystemSettings.query.filter_by(key=key).first()
                    if not existing:
                        setting = SystemSettings(key=key, value=value)
                        db.session.add(setting)

                db.session.commit()
                app.logger.info("Default system settings initialized")
            except Exception as settings_error:
                app.logger.warning(f"Could not create system settings: {settings_error}")
                try:
                    db.session.rollback()
                except:
                    pass

        app.logger.info("Database initialized successfully")
        return True

    except Exception as e:
        app.logger.error(f"Database initialization failed: {e}")
        return False


def import_json_to_db():
    """One-time import of existing JSON submissions to database"""
    import json
    import uuid

    submissions_file = 'data/submissions.json'
    archived_file = 'data/submissions.archived.json'

    # Check if JSON file exists and hasn't been archived yet
    if not os.path.exists(submissions_file) or os.path.exists(archived_file):
        return

    try:
        with open(submissions_file, 'r') as f:
            submissions = json.load(f)

        print(f"📂 Importing {len(submissions)} submissions from JSON to database...")

        for submission_id, data in submissions.items():
            # Skip if already exists in database
            if Report.query.get(submission_id):
                continue

            context = data.get('context', {})


            # Create parent report record
            report = Report(
                id=submission_id,
                type='SAT',
                status='APPROVED' if data.get('locked', False) else 'DRAFT',
                document_title=context.get('DOCUMENT_TITLE', ''),
                document_reference=context.get('DOCUMENT_REFERENCE', ''),
                project_reference=context.get('PROJECT_REFERENCE', ''),
                client_name=context.get('CLIENT_NAME', ''),
                revision=context.get('REVISION', ''),
                prepared_by=context.get('PREPARED_BY', ''),
                user_email=data.get('user_email', ''),
                created_at=datetime.fromisoformat(data.get('created_at', datetime.utcnow().isoformat())),
                updated_at=datetime.fromisoformat(data.get('updated_at', datetime.utcnow().isoformat())),
                locked=data.get('locked', False),
                approvals_json=json.dumps(data.get('approvals', [])),
                approval_notification_sent=data.get('approval_notification_sent', False)
            )

            # Create SAT-specific record
            sat_report = SATReport(
                report_id=submission_id,
                data_json=json.dumps(data),  # Store entire submission as JSON
                date=context.get('DATE', ''),
                purpose=context.get('PURPOSE', ''),
                scope=context.get('SCOPE', ''),
                scada_image_urls=json.dumps(data.get('scada_image_urls', [])),
                trends_image_urls=json.dumps(data.get('trends_image_urls', [])),
                alarm_image_urls=json.dumps(data.get('alarm_image_urls', []))
            )

            db.session.add(report)
            db.session.add(sat_report)

        db.session.commit()

        # Archive the JSON file
        os.rename(submissions_file, archived_file)
        print(f"✅ Successfully imported {len(submissions)} submissions and archived JSON file")

    except Exception as e:
        print(f"❌ Error importing JSON submissions: {e}")
        db.session.rollback()

def test_db_connection():
    """Test database connectivity"""
    try:
        # Try a simple query
        User.query.limit(1).all()
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False

def create_admin_user(email='admin@cullyautomation.com', password='admin123', full_name='System Administrator'):
    """Create admin user manually - useful for new database setup"""
    try:
        # Check if admin already exists
        existing_admin = User.query.filter_by(email=email).first()
        if existing_admin:
            print(f"Admin user {email} already exists")
            return existing_admin
        
        # Create new admin user
        admin_user = User(
            email=email,
            full_name=full_name,
            role='Admin',
            status='Active'
        )
        admin_user.set_password(password)
        db.session.add(admin_user)
        db.session.commit()
        
        print(f"✅ Admin user created successfully: {email}")
        print(f"   Password: {password}")
        print("   ⚠️  Please change the password after first login!")
        return admin_user
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        db.session.rollback()
        return None

class ModuleSpec(db.Model):
    __tablename__ = 'module_specs'

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(100), nullable=False)  # ABB, Siemens, etc.
    model = db.Column(db.String(100), nullable=False)    # DI810, SM1231, etc.
    description = db.Column(db.String(500), nullable=True)
    digital_inputs = db.Column(db.Integer, default=0)
    digital_outputs = db.Column(db.Integer, default=0)
    analog_inputs = db.Column(db.Integer, default=0)
    analog_outputs = db.Column(db.Integer, default=0)
    voltage_range = db.Column(db.String(100), nullable=True)  # "24 VDC", "0-10V", etc.
    current_range = db.Column(db.String(100), nullable=True)  # "4-20mA", etc.
    resolution = db.Column(db.String(50), nullable=True)      # "12-bit", "16-bit", etc.
    signal_type = db.Column(db.String(50), nullable=True)     # "Digital", "Analog", "Mixed"
    rack_slot_convention = db.Column(db.String(100), nullable=True)  # Vendor-specific naming
    datasheet_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified = db.Column(db.Boolean, default=False)  # Whether spec has been verified

    # Unique constraint on company + model
    __table_args__ = (db.UniqueConstraint('company', 'model', name='unique_company_model'),)

    @classmethod
    def find_or_create(cls, company, model):
        """Find existing module spec or create placeholder for web lookup"""
        spec = cls.query.filter_by(company=company.upper(), model=model.upper()).first()
        if not spec:
            spec = cls(
                company=company.upper(),
                model=model.upper(),
                verified=False
            )
            db.session.add(spec)
            db.session.commit()
        return spec

    def get_total_channels(self):
        """Get total number of I/O channels"""
        return (self.digital_inputs or 0) + (self.digital_outputs or 0) + \
               (self.analog_inputs or 0) + (self.analog_outputs or 0)

    def to_dict(self):
        return {
            'company': self.company,
            'model': self.model,
            'description': self.description,
            'digital_inputs': self.digital_inputs,
            'digital_outputs': self.digital_outputs,
            'analog_inputs': self.analog_inputs,
            'analog_outputs': self.analog_outputs,
            'voltage_range': self.voltage_range,
            'current_range': self.current_range,
            'resolution': self.resolution,
            'signal_type': self.signal_type,
            'total_channels': self.get_total_channels(),
            'verified': self.verified
        }

class ReportEdit(db.Model):
    """Audit trail for report edits"""
    __tablename__ = 'report_edits'
    
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(36), db.ForeignKey('reports.id'), nullable=False)
    editor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    editor_email = db.Column(db.String(120), nullable=False)  # Store email for reference
    before_json = db.Column(db.Text, nullable=True)  # Previous data state
    after_json = db.Column(db.Text, nullable=False)  # New data state
    changes_summary = db.Column(db.Text, nullable=True)  # Human-readable summary of changes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    version_before = db.Column(db.String(10), nullable=True)  # e.g., R0
    version_after = db.Column(db.String(10), nullable=True)  # e.g., R1
    
    # Relationships
    report = db.relationship('Report', backref='edit_history')
    editor = db.relationship('User', backref='report_edits')
    
    def __repr__(self):
        return f'<ReportEdit {self.report_id} by {self.editor_email} at {self.created_at}>'

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)  # Recipient
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # 'approval_request', 'status_update', 'completion', etc.
    related_submission_id = db.Column(db.String(36), nullable=True)  # Link to report
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    action_url = db.Column(db.String(500), nullable=True)  # Optional action link

    # Changed 'type' to 'notification_type' and 'related_submission_id' to 'submission_id' in to_dict for clarity
    def to_dict(self):
        """Convert notification to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.type,
            'read': self.read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'action_url': self.action_url,
            'submission_id': self.related_submission_id
        }

    @staticmethod
    def create_notification(user_email, title, message, notification_type, submission_id=None, action_url=None):
        """Create a new notification for a user"""
        notification = Notification(
            user_email=user_email,
            title=title,
            message=message,
            type=notification_type,
            related_submission_id=submission_id,
            action_url=action_url
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    @staticmethod
    def get_recent_notifications(user_email, limit=10):
        """Get recent notifications for a user"""
        return Notification.query.filter_by(user_email=user_email)\
                                .order_by(Notification.created_at.desc())\
                                .limit(limit).all()

    @staticmethod
    def get_unread_count(user_email):
        """Get count of unread notifications for a user"""
        return Notification.query.filter_by(user_email=user_email, read=False).count()

    def __repr__(self):
        return f'<Notification {self.id}: {self.title}>'
