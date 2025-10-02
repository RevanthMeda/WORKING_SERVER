
"""Centralised storage settings and management services."""
import json
import os
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, cast

from flask import current_app, Flask
from sqlalchemy.exc import SQLAlchemyError

from models import db, StorageConfig, StorageSettingsAudit


class StorageSettingsError(Exception):
    """Base class for storage settings errors."""




def _resolve_app(app: Optional[Flask] = None) -> Flask:
    if app is not None:
        return app

    proxy = current_app
    getter = getattr(proxy, '_get_current_object', None)
    if callable(getter):
        return cast(Flask, getter())
    return cast(Flask, proxy)


class StorageSettingsValidationError(StorageSettingsError):
    """Raised when storage settings payload fails validation."""


class StorageSettingsConcurrencyError(StorageSettingsError):
    """Raised when storage settings update conflicts with concurrent changes."""


@dataclass(frozen=True)
class StorageSettings:
    """Serializable representation of storage settings."""

    org_id: str
    environment: str
    upload_root: str
    image_storage_limit_gb: float
    active_quality: int
    approved_quality: int
    archive_quality: int
    preferred_formats: List[str]
    version: int

    @property
    def compression_profiles(self) -> Dict[str, int]:
        return {
            'active_quality': self.active_quality,
            'approved_quality': self.approved_quality,
            'archive_quality': self.archive_quality,
        }


    def to_dict(self) -> Dict[str, object]:
        return {
            'org_id': self.org_id,
            'environment': self.environment,
            'upload_root': self.upload_root,
            'image_storage_limit_gb': self.image_storage_limit_gb,
            'active_quality': self.active_quality,
            'approved_quality': self.approved_quality,
            'archive_quality': self.archive_quality,
            'preferred_formats': list(self.preferred_formats),
            'version': self.version,
        }


class StorageSettingsService:
    """Service responsible for loading and updating storage settings."""

    _lock = threading.Lock()
    _allowed_formats = {
        'jpeg', 'jpg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'avif'
    }

    @classmethod
    def load_settings(cls, org_id: str = 'default', environment: Optional[str] = None) -> StorageSettings:
        env = environment or cls._resolve_environment()
        config = StorageConfig.get_or_create(org_id=org_id, environment=env)
        return cls._to_settings(config)

    @classmethod
    def update_settings(
        cls,
        payload: Dict,
        actor_email: str,
        actor_id: Optional[int] = None,
        expected_version: Optional[int] = None,
        org_id: str = 'default',
        environment: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> StorageSettings:
        env = environment or cls._resolve_environment()
        with cls._lock:
            config = StorageConfig.get_or_create(org_id=org_id, environment=env)
            if expected_version is not None and config.version != expected_version:
                raise StorageSettingsConcurrencyError(
                    f"Version mismatch: expected {expected_version}, found {config.version}"
                )

            validated_payload = cls._validate_payload(payload, config)
            diff = cls._build_diff(config, validated_payload)
            if not diff:
                return cls._to_settings(config)

            config.apply_updates(validated_payload)
            config.updated_by = actor_email

            try:
                audit_entry = StorageSettingsAudit(
                    storage_config_id=config.id,
                    actor_email=actor_email,
                    actor_id=actor_id,
                    action='update',
                    changes_json=json.dumps(diff),
                    ip_address=ip_address,
                )
                db.session.add(audit_entry)
                db.session.commit()
                db.session.refresh(config)
            except SQLAlchemyError as exc:
                db.session.rollback()
                raise StorageSettingsError(str(exc)) from exc

            settings = cls.sync_app_config()
            return settings

    @classmethod
    def sync_app_config(cls, app=None) -> StorageSettings:
        target_app = _resolve_app(app)
        with target_app.app_context():
            settings = cls.load_settings()
            raw_root = settings.upload_root
            abs_root = cls._resolve_upload_root(raw_root, target_app)
            target_app.config['UPLOAD_ROOT'] = abs_root
            target_app.config['UPLOAD_FOLDER'] = abs_root
            target_app.config['UPLOAD_ROOT_RAW'] = raw_root
            target_app.config['IMAGE_STORAGE_LIMIT_GB'] = settings.image_storage_limit_gb
            target_app.config['IMAGE_COMPRESSION_PROFILES'] = settings.compression_profiles
            target_app.config['IMAGE_PREFERRED_FORMATS'] = settings.preferred_formats
            os.makedirs(abs_root, exist_ok=True)
            return settings

    @classmethod
    def _validate_payload(cls, payload: Dict, current: StorageConfig) -> Dict:
        validated: Dict[str, object] = {}
        if 'upload_root' in payload:
            validated['upload_root'] = cls._validate_upload_root(payload['upload_root'])
        else:
            validated['upload_root'] = current.upload_root

        if 'image_storage_limit_gb' in payload:
            validated['image_storage_limit_gb'] = cls._validate_limit(payload['image_storage_limit_gb'])
        else:
            validated['image_storage_limit_gb'] = current.image_storage_limit_gb

        for quality_key in ('active_quality', 'approved_quality', 'archive_quality'):
            if quality_key in payload:
                validated[quality_key] = cls._validate_quality(payload[quality_key], quality_key)
            else:
                validated[quality_key] = getattr(current, quality_key)

        if 'preferred_formats' in payload:
            validated['preferred_formats'] = cls._validate_formats(payload['preferred_formats'])
        else:
            try:
                validated['preferred_formats'] = json.loads(current.preferred_formats) if current.preferred_formats else []
            except Exception:
                validated['preferred_formats'] = []

        return validated

    @classmethod
    def _validate_upload_root(cls, value: str) -> str:
        if not value or not isinstance(value, str):
            raise StorageSettingsValidationError('Upload root path is required.')
        trimmed = value.strip()
        if not trimmed:
            raise StorageSettingsValidationError('Upload root path cannot be empty.')
        normalized = os.path.normpath(trimmed)
        parts = [part for part in normalized.replace('\\', '/').split('/') if part not in ('', '.')]
        if any(part == '..' for part in parts):
            raise StorageSettingsValidationError('Upload root cannot contain parent directory references.')
        return normalized.replace('\\', '/')

    @classmethod
    def _validate_limit(cls, value) -> float:
        try:
            limit = float(value)
        except (TypeError, ValueError):
            raise StorageSettingsValidationError('Storage limit must be a number.')
        if limit <= 0:
            raise StorageSettingsValidationError('Storage limit must be greater than zero.')
        if limit > 10240:
            raise StorageSettingsValidationError('Storage limit exceeds maximum allowed (10 TB).')
        return round(limit, 2)

    @classmethod
    def _validate_quality(cls, value, label: str) -> int:
        try:
            quality = int(value)
        except (TypeError, ValueError):
            raise StorageSettingsValidationError(f'{label} must be an integer percentage.')
        if quality < 1 or quality > 100:
            raise StorageSettingsValidationError(f'{label} must be between 1 and 100.')
        return quality

    @classmethod
    def _validate_formats(cls, formats) -> List[str]:
        if formats is None:
            return []
        if isinstance(formats, str):
            candidates = [f.strip().lower() for f in formats.split(',')]
        elif isinstance(formats, (list, tuple, set)):
            candidates = [str(f).strip().lower() for f in formats]
        else:
            raise StorageSettingsValidationError('Preferred formats must be a list or comma-separated string.')

        cleaned: List[str] = []
        for fmt in candidates:
            if not fmt:
                continue
            canonical = 'jpeg' if fmt == 'jpg' else fmt
            if canonical not in cls._allowed_formats:
                raise StorageSettingsValidationError(f'Unsupported image format: {fmt}')
            if canonical not in cleaned:
                cleaned.append(canonical)
        return cleaned

    @classmethod
    def _resolve_environment(cls) -> str:
        app = _resolve_app()
        return app.config.get('ENV', 'production')

    @classmethod
    def _resolve_upload_root(cls, raw_root: str, app) -> str:
        if os.path.isabs(raw_root):
            return os.path.normpath(raw_root)
        base_dir = app.config.get('BASE_DIR') or app.root_path
        abs_path = os.path.normpath(os.path.join(base_dir, raw_root))
        return abs_path

    @classmethod
    def _build_diff(cls, config: StorageConfig, new_values: Dict) -> Dict:
        old = config.to_dict()
        diff: Dict[str, Dict[str, object]] = {}
        for key, new_value in new_values.items():
            if key == 'preferred_formats':
                previous = old.get(key) or []
            else:
                previous = old.get(key)
            if previous != new_value:
                diff[key] = {'before': previous, 'after': new_value}
        return diff

    @classmethod
    def _to_settings(cls, config: StorageConfig) -> StorageSettings:
        preferred: List[str] = []
        try:
            preferred = json.loads(config.preferred_formats) if config.preferred_formats else []
        except Exception:
            preferred = []
        return StorageSettings(
            org_id=config.org_id,
            environment=config.environment,
            upload_root=config.upload_root,
            image_storage_limit_gb=config.image_storage_limit_gb,
            active_quality=config.active_quality,
            approved_quality=config.approved_quality,
            archive_quality=config.archive_quality,
            preferred_formats=preferred,
            version=config.version,
        )


class ImageStorageService:
    """Placeholder for future image lifecycle operations."""

    def __init__(self, settings: Optional[StorageSettings] = None):
        self._settings = settings or StorageSettingsService.load_settings()

    @property
    def settings(self) -> StorageSettings:
        return self._settings

    # Methods for saving, updating, and deleting images will be implemented in later phases.
