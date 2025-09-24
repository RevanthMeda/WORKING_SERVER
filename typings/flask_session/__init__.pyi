# Type stubs for flask_session
from typing import Any, Optional
from flask import Flask

class Session:
    def __init__(self, app: Optional[Flask] = None) -> None: ...
    def init_app(self, app: Flask) -> None: ...