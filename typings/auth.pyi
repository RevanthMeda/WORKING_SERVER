# Type stubs for auth
from typing import Any, Callable, TypeVar
from flask import Flask

F = TypeVar('F', bound=Callable[..., Any])

def init_auth(app: Flask) -> None: ...
def require_auth(func: F) -> F: ...