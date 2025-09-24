# Contributing to SAT Report Generator

## Welcome Contributors!

Thank you for your interest in contributing to the SAT Report Generator project. This document provides guidelines and best practices for contributing to ensure a smooth collaboration process and maintain code quality.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Process](#development-process)
4. [Coding Standards](#coding-standards)
5. [Testing Requirements](#testing-requirements)
6. [Documentation Guidelines](#documentation-guidelines)
7. [Pull Request Process](#pull-request-process)
8. [Issue Reporting](#issue-reporting)
9. [Security Considerations](#security-considerations)
10. [Release Process](#release-process)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of background, experience level, gender identity, sexual orientation, disability, personal appearance, body size, race, ethnicity, age, religion, or nationality.

### Expected Behavior

- **Be respectful**: Treat all community members with respect and kindness
- **Be collaborative**: Work together constructively and help others learn
- **Be inclusive**: Welcome newcomers and help them get started
- **Be professional**: Maintain professional communication in all interactions
- **Be constructive**: Provide helpful feedback and suggestions

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Publishing private information without consent
- Spam or irrelevant promotional content
- Any behavior that would be inappropriate in a professional setting

### Enforcement

Violations of the code of conduct should be reported to the project maintainers. All reports will be reviewed and investigated promptly and fairly.

## Getting Started

### Prerequisites

Before contributing, ensure you have:

1. **Read the documentation**: Familiarize yourself with the project structure and goals
2. **Set up development environment**: Follow the [Developer Onboarding Guide](onboarding.md)
3. **Understand the codebase**: Review existing code and architecture
4. **Join communication channels**: Connect with the development team

### Types of Contributions

We welcome various types of contributions:

**Code Contributions:**
- Bug fixes
- New features
- Performance improvements
- Code refactoring
- Security enhancements

**Documentation:**
- API documentation improvements
- User guide updates
- Code comments and docstrings
- Tutorial creation
- Translation

**Testing:**
- Unit test additions
- Integration test improvements
- End-to-end test scenarios
- Performance test cases
- Security test cases

**Design and UX:**
- User interface improvements
- User experience enhancements
- Accessibility improvements
- Mobile responsiveness

## Development Process

### Workflow Overview

We use **Git Flow** with the following process:

1. **Fork the repository** (external contributors)
2. **Create a feature branch** from `develop`
3. **Implement your changes** following coding standards
4. **Write/update tests** for your changes
5. **Update documentation** as needed
6. **Submit a pull request** for review
7. **Address review feedback** if any
8. **Merge after approval** by maintainers

### Branch Naming Convention

Use descriptive branch names with prefixes:

```bash
# Feature branches
feature/add-report-templates
feature/improve-authentication
feature/api-rate-limiting

# Bug fix branches
bugfix/fix-login-redirect
bugfix/resolve-file-upload-error
bugfix/correct-date-validation

# Hotfix branches (for critical production issues)
hotfix/security-patch-auth
hotfix/fix-data-corruption

# Documentation branches
docs/update-api-documentation
docs/add-deployment-guide
```

### Commit Message Guidelines

Follow **Conventional Commits** specification:

**Format:**
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only changes
- `style`: Changes that don't affect code meaning (formatting, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to build process or auxiliary tools

**Examples:**
```bash
feat(api): add report template endpoints

Add CRUD operations for report templates including:
- Create template from existing report
- List user templates
- Apply template to new report
- Delete template

Closes #123

fix(auth): resolve JWT token expiration handling

- Fix token refresh mechanism
- Add proper error handling for expired tokens
- Update client-side token management

Breaking change: Token refresh endpoint now requires
different request format

docs(readme): update installation instructions

- Add Docker setup instructions
- Update Python version requirements
- Fix broken links to documentation

test(reports): add integration tests for approval workflow

- Test complete approval process
- Add edge cases for rejection scenarios
- Mock email notifications
```

## Coding Standards

### Python Style Guide

We follow **PEP 8** with these specific guidelines:

**Code Formatting:**
- Use **Black** for automatic code formatting
- Maximum line length: **88 characters**
- Use **4 spaces** for indentation (no tabs)
- Use **double quotes** for strings (Black default)

**Naming Conventions:**
```python
# Variables and functions: snake_case
user_name = "john_doe"
def calculate_total_amount():
    pass

# Constants: UPPER_SNAKE_CASE
MAX_FILE_SIZE = 16777216
DEFAULT_TIMEOUT = 30

# Classes: PascalCase
class ReportService:
    pass

# Private methods: leading underscore
def _internal_helper_method():
    pass

# Protected methods: single leading underscore
def _protected_method(self):
    pass
```

**Import Organization:**
```python
# Standard library imports
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Third-party imports
import requests
from flask import Flask, request, jsonify
from sqlalchemy import Column, String, DateTime

# Local application imports
from models import User, Report
from services.report_service import ReportService
from utils.validation import validate_email
```

**Function Documentation:**
```python
def create_report(
    title: str, 
    client_name: str, 
    user_id: str,
    template_id: Optional[str] = None
) -> Report:
    """Create a new SAT report.
    
    Creates a new report with the specified parameters. If a template_id
    is provided, the report will be initialized with template data.
    
    Args:
        title: The report title
        client_name: Name of the client organization
        user_id: ID of the user creating the report
        template_id: Optional template to use for initialization
        
    Returns:
        The created Report instance
        
    Raises:
        ValidationError: If input parameters are invalid
        TemplateNotFoundError: If template_id doesn't exist
        PermissionError: If user lacks creation permissions
        
    Example:
        >>> report = create_report(
        ...     title="SAT Report for Project Alpha",
        ...     client_name="Acme Corp",
        ...     user_id="user_123"
        ... )
        >>> print(report.id)
        'report_456'
    """
    # Implementation here
    pass
```

### Code Quality Requirements

**Automated Checks:**
All code must pass these automated checks:

```bash
# Code formatting
black --check .

# Import sorting
isort --check-only .

# Linting
flake8 .

# Type checking
mypy .

# Security scanning
bandit -r .

# Dependency scanning
safety check
```

**Code Complexity:**
- **Cyclomatic complexity**: Maximum 10 per function
- **Function length**: Maximum 50 lines
- **Class length**: Maximum 500 lines
- **File length**: Maximum 1000 lines

**Error Handling:**
```python
# Use specific exception types
class ReportValidationError(ValueError):
    """Raised when report data validation fails."""
    pass

class ReportNotFoundError(Exception):
    """Raised when a report cannot be found."""
    pass

# Proper exception handling
try:
    report = Report.query.get(report_id)
    if not report:
        raise ReportNotFoundError(f"Report {report_id} not found")
    
    # Process report
    result = process_report(report)
    
except ReportValidationError as e:
    logger.warning(f"Validation error for report {report_id}: {e}")
    return {"error": "Invalid report data", "details": str(e)}, 400
    
except ReportNotFoundError as e:
    logger.info(f"Report not found: {e}")
    return {"error": "Report not found"}, 404
    
except Exception as e:
    logger.error(f"Unexpected error processing report {report_id}: {e}")
    return {"error": "Internal server error"}, 500
```

### Database Guidelines

**Model Definitions:**
```python
class Report(db.Model):
    """SAT Report model."""
    
    __tablename__ = 'reports'
    
    # Primary key
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Required fields
    document_title = db.Column(db.String(200), nullable=False)
    document_reference = db.Column(db.String(100), nullable=False, unique=True)
    
    # Optional fields with defaults
    status = db.Column(db.String(50), default='Draft', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign keys
    created_by = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    creator = db.relationship('User', backref='reports')
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_reports_status', 'status'),
        db.Index('idx_reports_created_by', 'created_by'),
        db.Index('idx_reports_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f'<Report {self.document_reference}>'
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'document_title': self.document_title,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
```

**Query Guidelines:**
```python
# Use explicit queries instead of lazy loading
reports = db.session.query(Report)\
    .options(joinedload(Report.creator))\
    .filter(Report.status == 'Approved')\
    .order_by(Report.created_at.desc())\
    .limit(50)\
    .all()

# Use pagination for large datasets
def get_reports_paginated(page=1, per_page=20):
    return Report.query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

# Use database-level filtering
active_reports = Report.query.filter(
    Report.status.in_(['Draft', 'Pending Approval', 'Approved'])
).all()
```

### API Guidelines

**Endpoint Structure:**
```python
from flask_restx import Namespace, Resource, fields
from marshmallow import Schema, fields as ma_fields

# Create namespace with documentation
reports_ns = Namespace(
    'reports', 
    description='Report management operations',
    path='/reports'
)

# Define request/response models
report_model = reports_ns.model('Report', {
    'id': fields.String(description='Unique report identifier'),
    'document_title': fields.String(required=True, description='Report title'),
    'status': fields.String(description='Current report status'),
    'created_at': fields.DateTime(description='Creation timestamp')
})

# Validation schema
class ReportCreateSchema(Schema):
    document_title = ma_fields.Str(required=True, validate=Length(min=1, max=200))
    client_name = ma_fields.Str(required=True, validate=Length(min=1, max=100))
    purpose = ma_fields.Str(validate=Length(max=1000))

@reports_ns.route('')
class ReportsResource(Resource):
    """Reports collection endpoint."""
    
    @reports_ns.marshal_list_with(report_model)
    @reports_ns.doc('list_reports')
    @reports_ns.param('page', 'Page number', type=int, default=1)
    @reports_ns.param('per_page', 'Items per page', type=int, default=20)
    def get(self):
        """Retrieve list of reports with pagination."""
        # Implementation here
        pass
    
    @reports_ns.expect(report_model)
    @reports_ns.marshal_with(report_model, code=201)
    @reports_ns.doc('create_report')
    def post(self):
        """Create a new report."""
        # Implementation here
        pass
```

**Response Format:**
```python
# Success response
{
    "data": {
        "id": "report_123",
        "document_title": "SAT Report for Project Alpha",
        "status": "Draft"
    },
    "message": "Report created successfully"
}

# Error response
{
    "error": {
        "message": "Validation failed",
        "code": "VALIDATION_ERROR",
        "details": {
            "document_title": ["This field is required"],
            "client_name": ["Must be between 1 and 100 characters"]
        },
        "timestamp": "2023-01-01T12:00:00Z"
    }
}

# Paginated response
{
    "data": [...],
    "pagination": {
        "page": 1,
        "per_page": 20,
        "total": 100,
        "pages": 5
    }
}
```

## Testing Requirements

### Test Coverage Requirements

- **Minimum coverage**: 80% overall
- **Critical paths**: 95% coverage required
- **New code**: 90% coverage required
- **API endpoints**: 100% coverage required

### Test Categories

**Unit Tests:**
```python
# Test individual functions and methods
class TestReportService:
    def test_create_report_success(self):
        # Test successful report creation
        pass
    
    def test_create_report_validation_error(self):
        # Test validation error handling
        pass
    
    def test_create_report_duplicate_reference(self):
        # Test duplicate reference handling
        pass
```

**Integration Tests:**
```python
# Test API endpoints and database interactions
class TestReportAPI:
    def test_create_report_endpoint(self, client, auth_headers):
        # Test complete API workflow
        pass
    
    def test_get_reports_with_pagination(self, client, auth_headers):
        # Test pagination functionality
        pass
```

**End-to-End Tests:**
```python
# Test complete user workflows
class TestReportWorkflow:
    def test_complete_report_approval_workflow(self, browser):
        # Test from creation to approval
        pass
```

### Test Data Management

**Use Factories for Test Data:**
```python
import factory
from models import User, Report

class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = 'commit'
    
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    full_name = factory.Faker('name')
    role = 'Engineer'
    is_active = True
    is_approved = True

class ReportFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Report
        sqlalchemy_session_persistence = 'commit'
    
    document_title = factory.Faker('sentence', nb_words=4)
    document_reference = factory.Sequence(lambda n: f'DOC-{n:04d}')
    client_name = factory.Faker('company')
    created_by = factory.SubFactory(UserFactory)
```

### Performance Testing

**Load Testing Requirements:**
- API endpoints must handle 100 concurrent users
- Response time < 500ms for 95% of requests
- Database queries optimized for expected load

```python
# Example load test with locust
from locust import HttpUser, task, between

class ReportUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # Login and get token
        response = self.client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def list_reports(self):
        self.client.get("/api/v1/reports", headers=self.headers)
    
    @task(1)
    def create_report(self):
        self.client.post("/api/v1/reports", json={
            "document_title": "Load Test Report",
            "client_name": "Test Client"
        }, headers=self.headers)
```

## Documentation Guidelines

### Code Documentation

**Docstring Requirements:**
- All public functions and classes must have docstrings
- Use Google-style docstrings
- Include examples for complex functions
- Document all parameters and return values
- List possible exceptions

**API Documentation:**
- All endpoints must be documented with Flask-RESTX
- Include request/response examples
- Document all parameters and headers
- Specify error responses

### User Documentation

**When to Update Documentation:**
- New features added
- API changes made
- Configuration changes
- Deployment process changes
- Troubleshooting information added

**Documentation Standards:**
- Use clear, concise language
- Include code examples
- Add screenshots for UI changes
- Keep examples up to date
- Test all instructions

## Pull Request Process

### Before Submitting

**Pre-submission Checklist:**
- [ ] Code follows style guidelines
- [ ] All tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] No merge conflicts with target branch
- [ ] Commit messages follow convention
- [ ] Security considerations addressed

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed
- [ ] Performance impact assessed

## Screenshots (if applicable)
Add screenshots to help explain your changes.

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes

## Related Issues
Closes #(issue number)
```

### Review Process

**Review Criteria:**
1. **Functionality**: Does the code work as intended?
2. **Code Quality**: Is the code clean, readable, and maintainable?
3. **Testing**: Are there adequate tests for the changes?
4. **Documentation**: Is documentation updated appropriately?
5. **Security**: Are there any security implications?
6. **Performance**: Does the change impact performance?

**Review Timeline:**
- **Small changes**: 1-2 business days
- **Medium changes**: 2-3 business days
- **Large changes**: 3-5 business days
- **Critical fixes**: Same day

### Merge Requirements

**Automated Checks:**
- [ ] All CI/CD pipeline checks pass
- [ ] Code coverage meets requirements
- [ ] Security scans pass
- [ ] Performance benchmarks met

**Manual Review:**
- [ ] At least one approved review from maintainer
- [ ] All review comments addressed
- [ ] No unresolved conversations

## Issue Reporting

### Bug Reports

**Bug Report Template:**
```markdown
## Bug Description
A clear and concise description of what the bug is.

## Steps to Reproduce
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## Expected Behavior
A clear description of what you expected to happen.

## Actual Behavior
A clear description of what actually happened.

## Screenshots
If applicable, add screenshots to help explain your problem.

## Environment
- OS: [e.g. Windows 10, macOS 11.0, Ubuntu 20.04]
- Browser: [e.g. Chrome 95, Firefox 94, Safari 15]
- Version: [e.g. 1.2.3]

## Additional Context
Add any other context about the problem here.
```

### Feature Requests

**Feature Request Template:**
```markdown
## Feature Description
A clear and concise description of what you want to happen.

## Problem Statement
Describe the problem this feature would solve.

## Proposed Solution
Describe the solution you'd like to see implemented.

## Alternatives Considered
Describe any alternative solutions or features you've considered.

## Additional Context
Add any other context, mockups, or examples about the feature request here.

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
```

### Issue Labels

**Priority Labels:**
- `priority/critical`: Critical issues requiring immediate attention
- `priority/high`: High priority issues
- `priority/medium`: Medium priority issues
- `priority/low`: Low priority issues

**Type Labels:**
- `type/bug`: Bug reports
- `type/feature`: Feature requests
- `type/enhancement`: Improvements to existing features
- `type/documentation`: Documentation updates
- `type/question`: Questions about the project

**Status Labels:**
- `status/triage`: Needs initial review
- `status/in-progress`: Currently being worked on
- `status/blocked`: Blocked by external dependencies
- `status/needs-info`: Requires additional information

## Security Considerations

### Security Review Process

**Security Checklist:**
- [ ] Input validation implemented
- [ ] Authentication/authorization checked
- [ ] SQL injection prevention verified
- [ ] XSS protection implemented
- [ ] CSRF protection enabled
- [ ] Sensitive data handling reviewed
- [ ] Error messages don't leak information
- [ ] Logging doesn't expose sensitive data

### Vulnerability Reporting

**Security Issues:**
- **DO NOT** create public GitHub issues for security vulnerabilities
- Email security issues to: security@yourdomain.com
- Include detailed description and reproduction steps
- Allow reasonable time for fix before public disclosure

### Security Best Practices

**Code Security:**
```python
# Input validation
from marshmallow import Schema, fields, validate

class ReportSchema(Schema):
    document_title = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=200),
            validate.Regexp(r'^[a-zA-Z0-9\s\-_\.]+$')  # Whitelist characters
        ]
    )

# SQL injection prevention
# Use parameterized queries
reports = db.session.query(Report).filter(
    Report.client_name == client_name  # SQLAlchemy handles parameterization
).all()

# XSS prevention
from markupsafe import escape
safe_title = escape(user_input)

# Authentication
from functools import wraps
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return {'error': 'Authentication required'}, 401
        return f(*args, **kwargs)
    return decorated_function
```

## Release Process

### Version Numbering

We use **Semantic Versioning** (SemVer):
- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

**Examples:**
- `1.0.0`: Initial release
- `1.1.0`: New features added
- `1.1.1`: Bug fixes
- `2.0.0`: Breaking changes

### Release Checklist

**Pre-release:**
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Version number bumped
- [ ] Security scan completed
- [ ] Performance benchmarks met

**Release:**
- [ ] Create release branch
- [ ] Final testing in staging
- [ ] Create GitHub release
- [ ] Deploy to production
- [ ] Monitor for issues

**Post-release:**
- [ ] Verify deployment
- [ ] Update documentation
- [ ] Communicate changes to users
- [ ] Monitor error rates

### Changelog Format

```markdown
# Changelog

## [1.2.0] - 2023-01-15

### Added
- Report template functionality
- Bulk report operations
- Advanced search filters

### Changed
- Improved API response times
- Updated user interface design
- Enhanced error messages

### Fixed
- Fixed file upload issue with large files
- Resolved authentication token refresh bug
- Corrected date validation in reports

### Security
- Updated dependencies with security patches
- Enhanced input validation
- Improved session management

## [1.1.0] - 2022-12-01
...
```

Thank you for contributing to the SAT Report Generator! Your contributions help make this project better for everyone.