"""
Session Management and Revocation System for SAT Report Generator
Handles server-side session invalidation and tracking
"""

import os
import json
import time
import hashlib
from datetime import datetime, timedelta
from flask import session, current_app
from threading import Lock
import secrets

SESSION_TIMEOUT_SECONDS = 1800  # 30 minutes
ACTIVITY_UPDATE_THRESHOLD = 60  # seconds between disk writes


class SessionManager:
    """
    Manages session revocation and validation
    Uses both in-memory and file-based storage for persistence
    """
    
    def __init__(self):
        self.revoked_sessions = set()
        self.session_timestamps = {}
        self.lock = Lock()
        self.revocation_file = 'instance/revoked_sessions.json'
        self.session_timeout = SESSION_TIMEOUT_SECONDS
        self.activity_update_threshold = ACTIVITY_UPDATE_THRESHOLD
        self._load_revoked_sessions()
        
    def _load_revoked_sessions(self):
        """Load revoked sessions from persistent storage"""
        try:
            if os.path.exists(self.revocation_file):
                with open(self.revocation_file, 'r') as f:
                    data = json.load(f)
                    # Only load sessions revoked in last 24 hours
                    cutoff_time = time.time() - 86400  # 24 hours
                    self.revoked_sessions = {
                        sid for sid, timestamp in data.items() 
                        if float(timestamp) > cutoff_time
                    }
        except Exception as e:
            print(f"Error loading revoked sessions: {e}")
            self.revoked_sessions = set()
    
    def _save_revoked_sessions(self):
        """Save revoked sessions to persistent storage"""
        try:
            os.makedirs('instance', exist_ok=True)
            # Save with timestamps for cleanup
            data = {sid: time.time() for sid in self.revoked_sessions}
            with open(self.revocation_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving revoked sessions: {e}")
    
    def generate_session_id(self):
        """Generate a unique session identifier"""
        return secrets.token_hex(32)
    
    def create_session(self, user_id):
        """Create a new session with tracking"""
        session_id = self.generate_session_id()
        
        with self.lock:
            # Store session creation time
            self.session_timestamps[session_id] = time.time()
            
            # Remove from revoked list if it exists (reusing ID)
            self.revoked_sessions.discard(session_id)
        
        # Store in Flask session
        session['session_id'] = session_id
        session['user_id'] = user_id
        session['created_at'] = time.time()
        session['last_activity'] = time.time()
        session.permanent = False  # Never persist session
        
        return session_id
    
    def revoke_session(self, session_id=None):
        """Revoke a session, making it invalid"""
        if not session_id:
            session_id = session.get('session_id')
        
        if session_id:
            with self.lock:
                self.revoked_sessions.add(session_id)
                # Remove from active timestamps
                self.session_timestamps.pop(session_id, None)
                self._save_revoked_sessions()
        
        # Clear Flask session completely
        session.clear()
        session.permanent = False
        
    def is_session_revoked(self, session_id):
        """Check if a specific session ID has been revoked"""
        with self.lock:
            return session_id in self.revoked_sessions
    
    def is_session_valid(self, session_id=None):
        """Return True when the session exists, is active, and not revoked."""
        if not session_id:
            session_id = session.get('session_id')

        if not session_id:
            return False

        now = time.time()

        with self.lock:
            if session_id in self.revoked_sessions:
                return False

            created_at = float(session.get('created_at', 0) or 0)
            if created_at and now - created_at > self.session_timeout:
                self.revoked_sessions.add(session_id)
                self._save_revoked_sessions()
                return False

            last_activity = float(session.get('last_activity', 0) or 0)
            if last_activity and now - last_activity > self.session_timeout:
                self.revoked_sessions.add(session_id)
                self._save_revoked_sessions()
                return False

        last_activity = float(session.get('last_activity', 0) or 0)
        if not last_activity:
            session['last_activity'] = now
            session.modified = True
        elif now - last_activity >= self.activity_update_threshold:
            session['last_activity'] = now
            session.modified = True

        return True

    def cleanup_old_sessions(self):
        """Remove old revoked sessions from tracking (housekeeping)"""
        with self.lock:
            cutoff_time = time.time() - 86400  # 24 hours
            # Since we're using a set, we need to track timestamps separately
            # For simplicity, clear very old sessions periodically
            if len(self.revoked_sessions) > 10000:  # Arbitrary limit
                # Keep only recent revocations
                self._load_revoked_sessions()
    
    def invalidate_all_user_sessions(self, user_id):
        """Invalidate all sessions for a specific user"""
        # In a real implementation, you'd track user_id -> session_id mapping
        # For now, just revoke the current session
        self.revoke_session()
    
    def get_session_info(self):
        """Get current session information for debugging"""
        return {
            'session_id': session.get('session_id'),
            'user_id': session.get('user_id'),
            'created_at': session.get('created_at'),
            'last_activity': session.get('last_activity'),
            'is_valid': self.is_session_valid()
        }

# Global session manager instance
session_manager = SessionManager()