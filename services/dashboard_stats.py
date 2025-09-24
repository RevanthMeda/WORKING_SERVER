import json
import threading
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional

from flask import current_app, has_app_context
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError

from models import db, Report, User, SystemSettings

ROLE_AUTOMATION_MANAGER = 'Automation Manager'
ROLE_PM = 'PM'

_DEFAULT_STATS_PAYLOAD: Dict[str, int] = {
    'draft': 0,
    'pending': 0,
    'rejected': 0,
    'approved': 0,
    'requests_received': 0,
    'requests_approved': 0,
    'total_reports': 0,
}

_CACHE_KEY_TEMPLATE = 'dashboard_stats:{role}:{email}'
_REFRESH_THREAD: Optional[threading.Thread] = None
_REFRESH_LOCK = threading.Lock()


def _log_debug(message: str) -> None:
    if has_app_context():
        current_app.logger.debug(message)
    else:
        print(message)


def _log_error(message: str, exc: Optional[Exception] = None) -> None:
    if has_app_context():
        current_app.logger.error(message, exc_info=exc)
    else:
        print(f"ERROR: {message} {exc if exc else ''}")


def _normalise_role(role: str) -> str:
    return role.strip().lower().replace(' ', '_')


def _make_cache_key(role: str, email: str) -> str:
    role_segment = _normalise_role(role)[:12]
    email_segment = email.lower()
    raw_key = _CACHE_KEY_TEMPLATE.format(role=role_segment, email=email_segment)
    if len(raw_key) <= 50:
        return raw_key
    digest = hashlib.sha1(raw_key.encode('utf-8')).hexdigest()[:8]
    return f"ds:{role_segment}:{digest}"


def _store_dashboard_stats(role: str, email: str, stats: Dict[str, int]) -> None:
    payload = {
        'computed_at': datetime.utcnow().isoformat(),
        'data': stats,
    }
    key = _make_cache_key(role, email)
    try:
        SystemSettings.set_setting(key, json.dumps(payload))
    except SQLAlchemyError:
        db.session.rollback()
        raise


def get_cached_dashboard_stats(role: str, email: str, max_age_seconds: Optional[int] = None) -> Optional[Dict[str, int]]:
    """Return cached stats for the user if they are fresh enough."""
    key = _make_cache_key(role, email)
    record = SystemSettings.query.filter_by(key=key).first()
    if not record or not record.value:
        return None

    try:
        payload = json.loads(record.value)
        computed_at_raw = payload.get('computed_at')
        if not computed_at_raw:
            return None

        computed_at = datetime.fromisoformat(computed_at_raw)
        max_age = max_age_seconds
        if max_age is None:
            max_age = _get_config_value('DASHBOARD_STATS_MAX_AGE_SECONDS', 600)
        if datetime.utcnow() - computed_at > timedelta(seconds=max_age):
            return None
        data = payload.get('data') or {}
        return {**_DEFAULT_STATS_PAYLOAD, **data}
    except Exception as exc:  # noqa: broad-except - defensive against bad JSON
        _log_debug(f"Failed to read cached dashboard stats for {email}: {exc}")
        return None


def compute_and_cache_dashboard_stats(role: str, email: str) -> Dict[str, int]:
    """Compute stats for the provided user and store them in the cache."""
    stats = _compute_dashboard_stats(role, email)
    _store_dashboard_stats(role, email, stats)
    return stats


def _compute_dashboard_stats(role: str, email: str) -> Dict[str, int]:
    normalised = _normalise_role(role)
    if normalised in ('automation_manager', 'automation manager'):
        return _compute_user_stats(email, stage=1)
    if normalised == 'pm':
        return _compute_user_stats(email, stage=2)
    raise ValueError(f"Unsupported dashboard role: {role}")


def _compute_user_stats(email: str, stage: int) -> Dict[str, int]:
    approver_match = f'"approver_email": "{email}"'
    candidate_reports = Report.query.filter(
        or_(
            Report.user_email == email,
            and_(
                Report.approvals_json.isnot(None),
                Report.approvals_json.contains(approver_match)
            )
        )
    ).all()

    status_counts = {
        'DRAFT': 0,
        'PENDING': 0,
        'REJECTED': 0,
        'APPROVED': 0,
    }
    requests_received = 0
    requests_approved = 0
    total_relevant_reports = 0

    for report in candidate_reports:
        owns_report = report.user_email == email
        assigned_to_user = False
        approvals = []

        if report.approvals_json:
            try:
                approvals = json.loads(report.approvals_json)
            except json.JSONDecodeError:
                approvals = []

        for approval in approvals:
            if approval.get('approver_email') == email and approval.get('stage') == stage:
                assigned_to_user = True
                requests_received += 1
                if approval.get('status') == 'approved':
                    requests_approved += 1
                break

        if not owns_report and not assigned_to_user:
            continue

        total_relevant_reports += 1
        status_key = (report.status or 'DRAFT').upper()
        if status_key in status_counts:
            status_counts[status_key] += 1

    result = {
        'draft': status_counts['DRAFT'],
        'pending': status_counts['PENDING'],
        'rejected': status_counts['REJECTED'],
        'approved': status_counts['APPROVED'],
        'requests_received': requests_received,
        'requests_approved': requests_approved,
        'total_reports': total_relevant_reports,
    }
    return result


def refresh_all_dashboard_stats() -> None:
    """Recompute cached stats for all Automation Managers and PMs."""
    roles = (ROLE_AUTOMATION_MANAGER, ROLE_PM)
    for role in roles:
        users = User.query.filter(User.role == role).all()
        for user in users:
            try:
                stats = _compute_dashboard_stats(role, user.email)
                _store_dashboard_stats(role, user.email, stats)
            except Exception as exc:  # noqa: broad-except - safeguard per user
                _log_error(f"Failed to refresh dashboard stats for {user.email}", exc)
                db.session.rollback()
        db.session.remove()


def start_dashboard_stats_refresher(app) -> Optional[threading.Thread]:
    """Start the background thread responsible for refreshing dashboard stats."""
    global _REFRESH_THREAD
    with _REFRESH_LOCK:
        if _REFRESH_THREAD and _REFRESH_THREAD.is_alive():
            return _REFRESH_THREAD

        if not getattr(app, 'logger', None):
            return None

        interval = app.config.get('DASHBOARD_STATS_REFRESH_SECONDS', 300)

        def _refresh_loop():
            with app.app_context():
                _log_debug("Dashboard stats refresher thread started")
                while True:
                    try:
                        refresh_all_dashboard_stats()
                    except Exception as exc:  # noqa: broad-except
                        _log_error("Dashboard stats refresh cycle failed", exc)
                        db.session.rollback()
                    finally:
                        db.session.remove()
                    time.sleep(interval)

        _REFRESH_THREAD = threading.Thread(
            target=_refresh_loop,
            name='DashboardStatsRefresher',
            daemon=True,
        )
        _REFRESH_THREAD.start()
        return _REFRESH_THREAD


def _get_config_value(key: str, default_value: int) -> int:
    if has_app_context():
        return current_app.config.get(key, default_value)
    return default_value
