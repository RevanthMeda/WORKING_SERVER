# Type stubs for models
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db: SQLAlchemy


class _BaseQuery:
    def filter(self, *args: object, **kwargs: object) -> "_BaseQuery": ...
    def filter_by(self, **kwargs: object) -> "_BaseQuery": ...
    def order_by(self, *args: object, **kwargs: object) -> "_BaseQuery": ...
    def limit(self, n: int) -> "_BaseQuery": ...
    def offset(self, n: int) -> "_BaseQuery": ...
    def all(self) -> List[Any]: ...
    def first(self) -> Any: ...
    def first_or_404(self) -> Any: ...
    def count(self) -> int: ...
    def scalar(self) -> Any: ...
    def one_or_none(self) -> Any: ...
    def options(self, *args: object, **kwargs: object) -> "_BaseQuery": ...
    def get(self, ident: Any) -> Any: ...
    def get_or_404(self, ident: Any) -> Any: ...
    def delete(self, synchronize_session: Any = ...) -> int: ...


class User:
    id: Any
    email: Any
    full_name: Any
    role: Any
    status: Any
    created_date: Any
    requested_role: Any
    is_authenticated: bool
    query: _BaseQuery
    def __init__(self, **kwargs: Any) -> None: ...


class SystemSettings:
    id: int
    key: str
    value: Optional[str]
    updated_at: Any
    query: _BaseQuery

    @staticmethod
    def get_setting(key: str, default: Optional[str] = ...) -> Optional[str]: ...

    @staticmethod
    def set_setting(key: str, value: str) -> "SystemSettings": ...


class StorageConfig:
    id: Any
    org_id: Any
    environment: Any
    upload_root: Any
    image_storage_limit_gb: Any
    active_quality: Any
    approved_quality: Any
    archive_quality: Any
    preferred_formats: Any
    created_at: Any
    updated_at: Any
    updated_by: Any
    version: Any
    query: _BaseQuery

    @classmethod
    def get_or_create(cls, org_id: str = ..., environment: str = ...) -> "StorageConfig": ...

    def apply_updates(self, data: Dict[str, object]) -> None: ...

    def to_dict(self) -> Dict[str, object]: ...


class StorageSettingsAudit:
    id: Any
    storage_config_id: Any
    actor_email: Any
    actor_id: Any
    action: Any
    changes_json: Any
    ip_address: Any
    created_at: Any
    query: _BaseQuery

    def __init__(self, **kwargs: object) -> None: ...

    def to_dict(self) -> Dict[str, object]: ...


class Report:
    id: Any
    type: Any
    status: Any
    document_title: Any
    document_reference: Any
    project_reference: Any
    client_name: Any
    revision: Any
    prepared_by: Any
    user_email: Any
    version: Any
    locked: Any
    created_at: Any
    updated_at: Any
    approvals_json: Any
    approval_notification_sent: Any
    submitted_at: Any
    approved_at: Any
    approved_by: Any
    edit_count: Any
    sat_report: Any
    fds_report: Any
    hds_report: Any
    site_survey_report: Any
    sds_report: Any
    fat_report: Any
    query: _BaseQuery
    def __init__(self, **kwargs: Any) -> None: ...


class SATReport:
    id: Any
    report_id: Any
    data_json: Any
    scada_image_urls: Any
    trends_image_urls: Any
    alarm_image_urls: Any
    date: Any
    purpose: Any
    scope: Any
    query: _BaseQuery
    def __init__(self, **kwargs: Any) -> None: ...


class FDSReport:
    id: Any
    report_id: Any
    data_json: Any
    system_architecture_json: Any
    functional_requirements: Any
    process_description: Any
    control_philosophy: Any
    query: _BaseQuery
    def get_system_architecture(self) -> Any: ...
    def set_system_architecture(self, payload: Any) -> None: ...
    def record_architecture_version(
        self,
        payload: Any,
        *,
        created_by: Optional[str] = ...,
        note: Optional[str] = ...,
        version_label: Optional[str] = ...,
    ) -> Optional["SystemArchitectureVersion"]: ...


class SystemArchitectureTemplate:
    id: int
    name: str
    slug: str
    description: Optional[str]
    category: Optional[str]
    thumbnail_path: Optional[str]
    layout_json: str
    is_shared: bool
    created_by: Optional[str]
    updated_by: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    query: _BaseQuery
    @staticmethod
    def slugify(name: str) -> str: ...
    def to_dict(self, include_layout: bool = ...) -> Dict[str, Any]: ...


class SystemArchitectureVersion:
    id: int
    report_id: str
    version_label: Optional[str]
    note: Optional[str]
    checksum: Optional[str]
    layout_json: str
    created_by: Optional[str]
    created_at: Optional[datetime]
    query: _BaseQuery
    def to_dict(self, include_layout: bool = ...) -> Dict[str, Any]: ...


class HDSReport:
    id: Any
    report_id: Any
    data_json: Any
    query: _BaseQuery


class SDSReport:
    id: Any
    report_id: Any
    data_json: Any
    query: _BaseQuery


class FATReport:
    id: Any
    report_id: Any
    data_json: Any
    query: _BaseQuery


class SiteSurveyReport:
    id: Any
    report_id: Any
    data_json: Any
    query: _BaseQuery


class Notification:
    id: Any
    user_email: Any
    title: Any
    message: Any
    type: Any
    related_submission_id: Any
    read: Any
    created_at: Any
    action_url: Any
    query: _BaseQuery
    def __init__(self, **kwargs: Any) -> None: ...

    @staticmethod
    def create_notification(
        user_email: str,
        title: str,
        message: str,
        notification_type: str,
        submission_id: Optional[str] = ...,
        action_url: Optional[str] = ...,
    ) -> "Notification": ...

    @staticmethod
    def get_recent_notifications(user_email: str, limit: int = ...) -> List["Notification"]: ...

    @staticmethod
    def get_unread_count(user_email: str) -> int: ...


class CullyStatistics:
    id: Any
    instruments_count: Any
    engineers_count: Any
    experience_years: Any
    water_plants: Any
    last_updated: Any
    fetch_successful: Any
    error_message: Any
    query: _BaseQuery

    def to_dict(self) -> Dict[str, Optional[str]]: ...

    @staticmethod
    def get_current_statistics() -> Dict[str, Optional[str]]: ...

    @staticmethod
    def fetch_and_update_from_cully() -> bool: ...


class ReportTemplate:
    id: int
    name: str
    template_type: str


def test_db_connection() -> bool: ...


def init_db(app: Flask) -> bool: ...
