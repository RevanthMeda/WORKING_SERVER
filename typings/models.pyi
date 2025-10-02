# Type stubs for models
from typing import Any, Optional, List, Dict
from flask_sqlalchemy import SQLAlchemy
from flask import Flask

db: SQLAlchemy

class User:
    id: int
    email: str
    full_name: str
    role: str
    status: str
    is_authenticated: bool
    
    @staticmethod
    def query() -> Any: ...

class Report:
    id: int
    title: str
    status: str
    
    @staticmethod
    def query() -> Any: ...

class SATReport(Report):
    client_name: str
    project_reference: str
    
class StorageConfig:
    org_id: str
    environment: str
    upload_root: str
    image_storage_limit_gb: float
    active_quality: int
    approved_quality: int
    archive_quality: int
    preferred_formats: str
    version: int

    @classmethod
    def get_or_create(cls, org_id: str = ..., environment: str = ...) -> "StorageConfig": ...

    def apply_updates(self, data: Dict[str, object]) -> None: ...

    def to_dict(self) -> Dict[str, object]: ...


class StorageSettingsAudit:
    storage_config_id: int
    actor_email: str
    actor_id: int | None
    action: str
    changes_json: str
    ip_address: str | None

    def __init__(self, **kwargs: object) -> None: ...

    def to_dict(self) -> Dict[str, object]: ...


class FDSReport(Report):
    pass

class HDSReport(Report):
    pass

class SDSReport(Report):
    pass

class FATReport(Report):
    pass

class SiteSurveyReport(Report):
    pass

class ReportTemplate:
    id: int
    name: str
    template_type: str

def init_db(app: Flask) -> bool: ...