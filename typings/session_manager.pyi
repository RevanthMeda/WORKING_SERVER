# Type stubs for session_manager
from typing import Any, Optional

class SessionManager:
    def is_session_valid(self, session_id: Optional[str] = None) -> bool: ...
    def revoke_session(self, session_id: Optional[str] = None) -> None: ...

session_manager: SessionManager