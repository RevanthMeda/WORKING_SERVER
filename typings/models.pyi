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