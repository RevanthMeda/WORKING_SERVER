
import json
import os

import pytest

from models import db, StorageConfig, StorageSettingsAudit
from services.storage_manager import (
    StorageSettingsService,
    StorageSettingsValidationError,
    StorageSettingsConcurrencyError,
)


@pytest.fixture
def storage_db(app):
    """Provide a database session with storage tables only."""
    with app.app_context():
        StorageConfig.__table__.create(db.engine, checkfirst=True)
        StorageSettingsAudit.__table__.create(db.engine, checkfirst=True)
        try:
            yield db.session
        finally:
            db.session.rollback()
            StorageSettingsAudit.__table__.drop(db.engine, checkfirst=True)
            StorageConfig.__table__.drop(db.engine, checkfirst=True)
            db.session.remove()


@pytest.fixture
def storage_context(app, storage_db):
    """Ensure storage settings exist for tests."""
    with app.app_context():
        return StorageSettingsService.load_settings()


def test_sync_app_config_applies_database_settings(app, storage_db, tmp_path, storage_context):
    with app.app_context():
        config = StorageConfig.query.filter_by(org_id=storage_context.org_id, environment=storage_context.environment).first()
        assert config is not None
        upload_root = tmp_path / 'custom_uploads'
        config.upload_root = str(upload_root)
        config.image_storage_limit_gb = 72.5
        config.active_quality = 88
        config.approved_quality = 77
        config.archive_quality = 55
        config.preferred_formats = json.dumps(['jpeg', 'webp'])
        storage_db.commit()

        settings = StorageSettingsService.sync_app_config(app)

        assert settings.upload_root == str(upload_root)
        assert app.config['UPLOAD_ROOT'] == os.path.normpath(str(upload_root))
        assert app.config['UPLOAD_FOLDER'] == os.path.normpath(str(upload_root))
        assert app.config['IMAGE_STORAGE_LIMIT_GB'] == pytest.approx(72.5)
        profiles = app.config['IMAGE_COMPRESSION_PROFILES']
        assert profiles['active_quality'] == 88
        assert profiles['approved_quality'] == 77
        assert profiles['archive_quality'] == 55
        assert app.config['IMAGE_PREFERRED_FORMATS'] == ['jpeg', 'webp']


def test_update_settings_rejects_invalid_values(app, storage_db, storage_context):
    with app.app_context():
        with pytest.raises(StorageSettingsValidationError):
            StorageSettingsService.update_settings(
                {'upload_root': '../etc/passwd'},
                actor_email='admin@test.com',
                actor_id=None,
                expected_version=storage_context.version,
            )

        with pytest.raises(StorageSettingsValidationError):
            StorageSettingsService.update_settings(
                {'image_storage_limit_gb': 0},
                actor_email='admin@test.com',
                actor_id=None,
                expected_version=StorageConfig.get_or_create().version,
            )

        with pytest.raises(StorageSettingsValidationError):
            StorageSettingsService.update_settings(
                {'active_quality': 150},
                actor_email='admin@test.com',
                actor_id=None,
                expected_version=StorageConfig.get_or_create().version,
            )


def test_update_settings_produces_audit_and_detects_conflict(app, storage_db, storage_context):
    with app.app_context():
        payload = {
            'upload_root': storage_context.upload_root + '_next',
            'image_storage_limit_gb': storage_context.image_storage_limit_gb + 5,
            'active_quality': storage_context.active_quality - 5,
            'approved_quality': storage_context.approved_quality - 5,
            'archive_quality': storage_context.archive_quality - 5,
            'preferred_formats': ['jpeg', 'png'],
        }

        updated = StorageSettingsService.update_settings(
            payload,
            actor_email='admin@test.com',
            actor_id=None,
            expected_version=storage_context.version,
        )

        audit_entries = StorageSettingsAudit.query.order_by(StorageSettingsAudit.created_at.desc()).all()
        assert audit_entries, 'Audit entry should be recorded'
        latest = audit_entries[0]
        assert latest.actor_email == 'admin@test.com'
        assert 'upload_root' in latest.to_dict()['changes']

        with pytest.raises(StorageSettingsConcurrencyError):
            StorageSettingsService.update_settings(
                {'image_storage_limit_gb': 10},
                actor_email='admin@test.com',
                actor_id=None,
                expected_version=storage_context.version,
            )

        assert updated.version > storage_context.version
