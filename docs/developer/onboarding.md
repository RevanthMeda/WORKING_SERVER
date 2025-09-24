# Developer Onboarding Guide

## Welcome to the SAT Report Generator Development Team

This guide will help you get up and running as a developer on the SAT Report Generator project. By the end of this guide, you'll have a complete development environment set up and understand our development processes.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Environment Setup](#development-environment-setup)
3. [Project Structure](#project-structure)
4. [Development Workflow](#development-workflow)
5. [Coding Standards](#coding-standards)
6. [Testing Guidelines](#testing-guidelines)
7. [Database Management](#database-management)
8. [API Development](#api-development)
9. [Frontend Development](#frontend-development)
10. [Deployment Process](#deployment-process)
11. [Troubleshooting](#troubleshooting)
12. [Resources and Documentation](#resources-and-documentation)

## Prerequisites

### Required Software

**Essential Tools:**
- **Git**: Version control system
- **Python 3.11+**: Programming language runtime
- **Node.js 16+**: JavaScript runtime for frontend tools
- **Docker**: Containerization platform
- **Docker Compose**: Multi-container orchestration
- **PostgreSQL**: Database system (or Docker alternative)
- **Redis**: Caching system (or Docker alternative)

**Recommended Tools:**
- **VS Code**: Code editor with Python extensions
- **PyCharm**: Python IDE (Professional edition recommended)
- **Postman**: API testing tool
- **pgAdmin**: PostgreSQL administration tool
- **Redis Desktop Manager**: Redis GUI client

### Development Accounts

**Required Accounts:**
- **GitHub**: Access to the repository
- **Docker Hub**: Container registry access
- **Slack**: Team communication (if applicable)
- **Jira/Linear**: Issue tracking (if applicable)

**Optional Accounts:**
- **AWS**: Cloud services (for production deployment)
- **Sentry**: Error monitoring
- **DataDog**: Application monitoring

### System Requirements

**Minimum Specifications:**
- **OS**: Windows 10, macOS 10.15, or Linux (Ubuntu 20.04+)
- **RAM**: 8GB (16GB recommended)
- **Storage**: 20GB free space
- **CPU**: 4 cores recommended

## Development Environment Setup

### Step 1: Clone the Repository

```bash
# Clone the main repository
git clone https://github.com/your-org/sat-report-generator.git
cd sat-report-generator

# Set up your Git configuration
git config user.name "Your Name"
git config user.email "your.email@company.com"
```

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
cd SERVER
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 3: Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your local settings
# Use your preferred text editor
code .env  # VS Code
nano .env  # Terminal editor
```

**Sample .env configuration:**
```bash
# Application
SECRET_KEY=your-local-secret-key-here
FLASK_ENV=development
DEBUG=true

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/satreports_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Email (for development)
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=false
MAIL_USERNAME=
MAIL_PASSWORD=

# File Storage
UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=16777216

# Development settings
TESTING=false
WTF_CSRF_ENABLED=false
```

### Step 4: Database Setup

**Option A: Using Docker (Recommended)**
```bash
# Start PostgreSQL and Redis with Docker Compose
docker-compose -f docker-compose.dev.yml up -d db redis

# Wait for services to start
sleep 10

# Initialize database
python manage_db.py init
python manage_db.py migrate
python manage_db.py seed  # Optional: add sample data
```

**Option B: Local Installation**
```bash
# Install PostgreSQL locally
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# macOS with Homebrew:
brew install postgresql

# Start PostgreSQL service
sudo systemctl start postgresql  # Linux
brew services start postgresql   # macOS

# Create database and user
sudo -u postgres psql
CREATE DATABASE satreports_dev;
CREATE USER satreports WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE satreports_dev TO satreports;
\q

# Initialize database
python manage_db.py init
python manage_db.py migrate
```

### Step 5: Start Development Server

```bash
# Start the Flask development server
python app.py

# Or use the development script
./debug_start.bat  # Windows
./debug_start.sh   # macOS/Linux

# The application will be available at:
# http://localhost:5000
```

### Step 6: Verify Installation

```bash
# Run health check
curl http://localhost:5000/health

# Expected response:
# {"status": "healthy", "timestamp": "...", "version": "1.0.0"}

# Run tests to ensure everything works
pytest tests/ -v

# Check code quality
flake8 .
black --check .
```

## Project Structure

### Directory Layout

```
sat-report-generator/
├── SERVER/                     # Main application directory
│   ├── api/                   # REST API endpoints
│   │   ├── __init__.py       # API initialization
│   │   ├── auth.py           # Authentication endpoints
│   │   ├── reports.py        # Report management endpoints
│   │   ├── users.py          # User management endpoints
│   │   └── ...
│   ├── cache/                # Caching utilities
│   ├── config/               # Configuration files
│   ├── database/             # Database utilities
│   ├── docs/                 # Documentation
│   ├── monitoring/           # Monitoring and metrics
│   ├── security/             # Security utilities
│   ├── static/               # Static assets
│   ├── templates/            # Jinja2 templates
│   ├── tests/                # Test suite
│   │   ├── unit/            # Unit tests
│   │   ├── integration/     # Integration tests
│   │   ├── e2e/             # End-to-end tests
│   │   └── conftest.py      # Test configuration
│   ├── app.py               # Application factory
│   ├── models.py            # Database models
│   ├── requirements.txt     # Python dependencies
│   └── ...
├── docker/                   # Docker configuration
├── k8s/                     # Kubernetes manifests
├── helm/                    # Helm charts
├── .github/                 # GitHub Actions workflows
├── docker-compose.yml       # Docker Compose configuration
└── README.md               # Project documentation
```

### Key Files and Their Purpose

**Application Core:**
- `app.py`: Flask application factory and configuration
- `models.py`: SQLAlchemy database models
- `config.py`: Application configuration management
- `manage_db.py`: Database management CLI

**API Layer:**
- `api/__init__.py`: API initialization and documentation
- `api/auth.py`: Authentication and authorization endpoints
- `api/reports.py`: Report management endpoints
- `api/schemas.py`: Request/response serialization schemas

**Security:**
- `security/authentication.py`: Authentication utilities
- `security/validation.py`: Input validation
- `security/audit.py`: Audit logging

**Testing:**
- `tests/conftest.py`: Test configuration and fixtures
- `tests/unit/`: Unit tests for individual components
- `tests/integration/`: Integration tests for API endpoints
- `tests/e2e/`: End-to-end tests for user workflows

## Development Workflow

### Git Workflow

We use **Git Flow** with the following branch structure:

**Main Branches:**
- `main`: Production-ready code
- `develop`: Integration branch for features

**Supporting Branches:**
- `feature/*`: New features
- `bugfix/*`: Bug fixes
- `hotfix/*`: Critical production fixes
- `release/*`: Release preparation

### Feature Development Process

**1. Create Feature Branch:**
```bash
# Start from develop branch
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/your-feature-name

# Example:
git checkout -b feature/add-report-templates
```

**2. Development Cycle:**
```bash
# Make your changes
# Edit files, add features, write tests

# Run tests frequently
pytest tests/unit/test_your_feature.py -v

# Check code quality
flake8 your_files.py
black your_files.py

# Commit changes with descriptive messages
git add .
git commit -m "feat: add report template functionality

- Add template model and API endpoints
- Implement template creation and usage
- Add unit tests for template operations
- Update API documentation"
```

**3. Code Review Process:**
```bash
# Push feature branch
git push origin feature/your-feature-name

# Create Pull Request on GitHub
# - Fill out PR template
# - Add reviewers
# - Link related issues
# - Ensure CI passes
```

**4. Merge and Cleanup:**
```bash
# After approval, merge via GitHub
# Delete feature branch
git checkout develop
git pull origin develop
git branch -d feature/your-feature-name
```

### Commit Message Convention

We follow **Conventional Commits** specification:

**Format:**
```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(api): add report template endpoints

fix(auth): resolve JWT token expiration issue

docs(readme): update installation instructions

test(reports): add integration tests for approval workflow
```

## Coding Standards

### Python Code Style

We follow **PEP 8** with some modifications:

**Line Length:**
- Maximum 88 characters (Black formatter default)
- Use parentheses for line continuation

**Imports:**
```python
# Standard library imports
import os
import sys
from datetime import datetime

# Third-party imports
from flask import Flask, request, jsonify
from sqlalchemy import Column, String, DateTime

# Local imports
from models import User, Report
from security.authentication import require_auth
```

**Function and Class Definitions:**
```python
class ReportService:
    """Service class for report operations."""
    
    def __init__(self, db_session):
        """Initialize service with database session."""
        self.db = db_session
    
    def create_report(self, data: dict) -> Report:
        """Create a new report.
        
        Args:
            data: Report data dictionary
            
        Returns:
            Created report instance
            
        Raises:
            ValidationError: If data is invalid
        """
        # Implementation here
        pass
```

**Error Handling:**
```python
# Use specific exception types
try:
    report = Report.query.get(report_id)
    if not report:
        raise NotFoundError(f"Report {report_id} not found")
except DatabaseError as e:
    logger.error(f"Database error: {e}")
    raise ServiceError("Failed to retrieve report")
```

### Code Quality Tools

**Automated Formatting:**
```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Check with flake8
flake8 .

# Type checking with mypy
mypy .
```

**Pre-commit Hooks:**
```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

### Documentation Standards

**Docstring Format (Google Style):**
```python
def process_report(report_id: str, action: str) -> dict:
    """Process a report with the specified action.
    
    This function handles various report processing actions including
    approval, rejection, and document generation.
    
    Args:
        report_id: Unique identifier for the report
        action: Action to perform ('approve', 'reject', 'generate')
        
    Returns:
        Dictionary containing processing results with keys:
        - success: Boolean indicating success
        - message: Status message
        - data: Additional result data
        
    Raises:
        ValueError: If action is not supported
        NotFoundError: If report doesn't exist
        PermissionError: If user lacks required permissions
        
    Example:
        >>> result = process_report('123', 'approve')
        >>> print(result['success'])
        True
    """
    # Implementation here
    pass
```

## Testing Guidelines

### Test Structure

**Test Organization:**
```
tests/
├── unit/                    # Unit tests
│   ├── test_models.py      # Model tests
│   ├── test_auth.py        # Authentication tests
│   └── test_services.py    # Service layer tests
├── integration/            # Integration tests
│   ├── test_api_endpoints.py
│   └── test_database_operations.py
├── e2e/                   # End-to-end tests
│   ├── test_user_workflows.py
│   └── test_report_workflows.py
├── fixtures/              # Test data
└── conftest.py           # Test configuration
```

### Writing Tests

**Unit Test Example:**
```python
import pytest
from unittest.mock import Mock, patch
from models import Report, User
from services.report_service import ReportService

class TestReportService:
    """Test cases for ReportService."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return Mock()
    
    @pytest.fixture
    def report_service(self, mock_db_session):
        """ReportService instance with mocked dependencies."""
        return ReportService(mock_db_session)
    
    def test_create_report_success(self, report_service, mock_db_session):
        """Test successful report creation."""
        # Arrange
        report_data = {
            'document_title': 'Test Report',
            'client_name': 'Test Client'
        }
        
        # Act
        result = report_service.create_report(report_data)
        
        # Assert
        assert result is not None
        assert result.document_title == 'Test Report'
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    def test_create_report_validation_error(self, report_service):
        """Test report creation with invalid data."""
        # Arrange
        invalid_data = {}
        
        # Act & Assert
        with pytest.raises(ValidationError):
            report_service.create_report(invalid_data)
```

**Integration Test Example:**
```python
import pytest
from flask import url_for
from models import User, Report

class TestReportAPI:
    """Integration tests for Report API endpoints."""
    
    def test_create_report_authenticated(self, client, auth_headers):
        """Test report creation with valid authentication."""
        # Arrange
        report_data = {
            'document_title': 'Integration Test Report',
            'document_reference': 'INT-001',
            'client_name': 'Test Client'
        }
        
        # Act
        response = client.post(
            url_for('api.reports_reports_list_resource'),
            json=report_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 201
        data = response.get_json()
        assert data['document_title'] == report_data['document_title']
    
    def test_create_report_unauthenticated(self, client):
        """Test report creation without authentication."""
        # Arrange
        report_data = {'document_title': 'Test Report'}
        
        # Act
        response = client.post(
            url_for('api.reports_reports_list_resource'),
            json=report_data
        )
        
        # Assert
        assert response.status_code == 401
```

### Running Tests

**Basic Test Execution:**
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_models.py

# Run tests with coverage
pytest --cov=. --cov-report=html

# Run tests in parallel
pytest -n auto

# Run only failed tests
pytest --lf
```

**Test Configuration:**
```bash
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --disable-warnings
    --cov=.
    --cov-report=term-missing
    --cov-report=html:htmlcov
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow running tests
```

## Database Management

### Database Migrations

**Creating Migrations:**
```bash
# Create a new migration
python manage_db.py create_migration "Add report templates table"

# This creates a new migration file in database/migrations/
```

**Migration File Structure:**
```python
"""Add report templates table

Revision ID: 001_add_templates
Revises: 000_initial
Create Date: 2023-01-01 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001_add_templates'
down_revision = '000_initial'
branch_labels = None
depends_on = None

def upgrade():
    """Apply migration."""
    op.create_table(
        'report_templates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('template_data', sa.JSON),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('created_by', sa.String(36), nullable=False)
    )

def downgrade():
    """Rollback migration."""
    op.drop_table('report_templates')
```

**Running Migrations:**
```bash
# Apply all pending migrations
python manage_db.py migrate

# Rollback to specific revision
python manage_db.py downgrade 000_initial

# Show migration history
python manage_db.py history

# Show current revision
python manage_db.py current
```

### Database Seeding

**Seed Data for Development:**
```python
# database/seeds.py
from models import User, Report, db
from werkzeug.security import generate_password_hash

def seed_users():
    """Create sample users for development."""
    users = [
        {
            'email': 'admin@example.com',
            'full_name': 'System Administrator',
            'role': 'Admin',
            'password': 'admin123',
            'is_active': True,
            'is_approved': True
        },
        {
            'email': 'engineer@example.com',
            'full_name': 'Test Engineer',
            'role': 'Engineer',
            'password': 'engineer123',
            'is_active': True,
            'is_approved': True
        }
    ]
    
    for user_data in users:
        existing_user = User.query.filter_by(email=user_data['email']).first()
        if not existing_user:
            user = User(
                email=user_data['email'],
                full_name=user_data['full_name'],
                role=user_data['role'],
                is_active=user_data['is_active'],
                is_approved=user_data['is_approved']
            )
            user.set_password(user_data['password'])
            db.session.add(user)
    
    db.session.commit()

def seed_reports():
    """Create sample reports for development."""
    # Implementation here
    pass
```

## API Development

### API Design Principles

**RESTful Design:**
- Use HTTP methods appropriately (GET, POST, PUT, DELETE)
- Use resource-based URLs
- Return appropriate HTTP status codes
- Use consistent response formats

**URL Structure:**
```
GET    /api/v1/reports           # List reports
POST   /api/v1/reports           # Create report
GET    /api/v1/reports/{id}      # Get specific report
PUT    /api/v1/reports/{id}      # Update report
DELETE /api/v1/reports/{id}      # Delete report

# Sub-resources
GET    /api/v1/reports/{id}/files     # List report files
POST   /api/v1/reports/{id}/approve   # Approve report
```

### Creating API Endpoints

**Endpoint Implementation:**
```python
from flask_restx import Namespace, Resource, fields
from flask import request
from models import Report, db
from security.authentication import require_auth
from api.schemas import report_schema, reports_schema

# Create namespace
reports_ns = Namespace('reports', description='Report operations')

# Define models for documentation
report_model = reports_ns.model('Report', {
    'id': fields.String(description='Report ID'),
    'document_title': fields.String(required=True, description='Document title'),
    'status': fields.String(description='Report status'),
    'created_at': fields.DateTime(description='Creation timestamp')
})

@reports_ns.route('')
class ReportsListResource(Resource):
    """Reports collection endpoint."""
    
    @reports_ns.marshal_list_with(report_model)
    @require_auth
    def get(self):
        """Get list of reports."""
        reports = Report.query.filter_by(created_by=current_user.id).all()
        return reports_schema.dump(reports)
    
    @reports_ns.expect(report_model)
    @reports_ns.marshal_with(report_model, code=201)
    @require_auth
    def post(self):
        """Create new report."""
        data = request.get_json()
        
        # Validate data
        errors = report_schema.validate(data)
        if errors:
            return {'errors': errors}, 400
        
        # Create report
        report = Report(**data)
        report.created_by = current_user.id
        
        db.session.add(report)
        db.session.commit()
        
        return report_schema.dump(report), 201
```

### API Documentation

**OpenAPI/Swagger Documentation:**
```python
# api/__init__.py
from flask_restx import Api

api = Api(
    title='SAT Report Generator API',
    version='1.0.0',
    description='Enterprise API for SAT report management',
    doc='/docs/',
    authorizations={
        'Bearer': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization'
        }
    }
)
```

**Testing API Endpoints:**
```bash
# Using curl
curl -X GET "http://localhost:5000/api/v1/reports" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Using httpie
http GET localhost:5000/api/v1/reports \
     Authorization:"Bearer YOUR_JWT_TOKEN"
```

## Frontend Development

### Template Structure

**Jinja2 Templates:**
```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}SAT Report Generator{% endblock %}</title>
    <link href="{{ url_for('static', filename='css/main.css') }}" rel="stylesheet">
</head>
<body>
    <nav class="navbar">
        <!-- Navigation content -->
    </nav>
    
    <main class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </main>
    
    <script src="{{ url_for('static', filename='js/main.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

### Static Assets

**CSS Organization:**
```
static/
├── css/
│   ├── main.css          # Main stylesheet
│   ├── components.css    # Component styles
│   └── utilities.css     # Utility classes
├── js/
│   ├── main.js          # Main JavaScript
│   ├── api.js           # API utilities
│   └── components/      # Component scripts
└── images/
    └── logos/
```

**JavaScript Utilities:**
```javascript
// static/js/api.js
class APIClient {
    constructor(baseURL = '/api/v1') {
        this.baseURL = baseURL;
        this.token = localStorage.getItem('jwt_token');
    }
    
    async request(method, endpoint, data = null) {
        const config = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`
            }
        };
        
        if (data) {
            config.body = JSON.stringify(data);
        }
        
        const response = await fetch(`${this.baseURL}${endpoint}`, config);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return response.json();
    }
    
    async getReports() {
        return this.request('GET', '/reports');
    }
    
    async createReport(reportData) {
        return this.request('POST', '/reports', reportData);
    }
}
```

## Deployment Process

### Local Development Deployment

**Using Docker Compose:**
```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

### Staging Deployment

**Build and Deploy:**
```bash
# Build application image
docker build -t sat-report-generator:staging .

# Tag for registry
docker tag sat-report-generator:staging your-registry/sat-report-generator:staging

# Push to registry
docker push your-registry/sat-report-generator:staging

# Deploy to staging
kubectl apply -f k8s/staging/
```

### Production Deployment

**CI/CD Pipeline:**
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build and push Docker image
        run: |
          docker build -t sat-report-generator:${{ github.sha }} .
          docker push your-registry/sat-report-generator:${{ github.sha }}
      
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/sat-report-generator \
            app=your-registry/sat-report-generator:${{ github.sha }}
```

## Troubleshooting

### Common Development Issues

**Database Connection Issues:**
```bash
# Check database status
docker-compose ps db

# View database logs
docker-compose logs db

# Connect to database directly
docker-compose exec db psql -U postgres -d satreports_dev
```

**Import Errors:**
```bash
# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Verify virtual environment
which python
pip list

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Port Conflicts:**
```bash
# Check what's using port 5000
lsof -i :5000  # macOS/Linux
netstat -ano | findstr :5000  # Windows

# Kill process using port
kill -9 <PID>  # macOS/Linux
taskkill /PID <PID> /F  # Windows
```

### Performance Issues

**Slow Database Queries:**
```sql
-- Enable query logging
ALTER SYSTEM SET log_statement = 'all';
ALTER SYSTEM SET log_min_duration_statement = 100;

-- Check slow queries
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
```

**Memory Issues:**
```bash
# Monitor memory usage
docker stats

# Check Python memory usage
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB')
"
```

## Resources and Documentation

### Internal Documentation

- **API Documentation**: http://localhost:5000/api/v1/docs/
- **Architecture Guide**: `/docs/architecture/README.md`
- **Deployment Guide**: `/docs/deployment/README.md`
- **User Guide**: `/docs/user-guide/README.md`

### External Resources

**Flask Ecosystem:**
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Flask-RESTX](https://flask-restx.readthedocs.io/)
- [SQLAlchemy](https://docs.sqlalchemy.org/)
- [Marshmallow](https://marshmallow.readthedocs.io/)

**Testing:**
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-flask](https://pytest-flask.readthedocs.io/)
- [Factory Boy](https://factoryboy.readthedocs.io/)

**Development Tools:**
- [Black Code Formatter](https://black.readthedocs.io/)
- [Flake8 Linter](https://flake8.pycqa.org/)
- [pre-commit Hooks](https://pre-commit.com/)

### Team Communication

**Slack Channels:**
- `#sat-report-dev`: General development discussion
- `#sat-report-alerts`: Automated alerts and notifications
- `#sat-report-releases`: Release announcements

**Meeting Schedule:**
- **Daily Standup**: 9:00 AM (15 minutes)
- **Sprint Planning**: Every 2 weeks (2 hours)
- **Code Review**: As needed
- **Architecture Review**: Monthly (1 hour)

### Getting Help

**Internal Support:**
- **Tech Lead**: @tech-lead-name
- **DevOps**: @devops-team
- **Product Owner**: @product-owner

**External Support:**
- **Stack Overflow**: Tag questions with `sat-report-generator`
- **GitHub Issues**: For bug reports and feature requests
- **Documentation**: Keep this guide updated with new learnings

Welcome to the team! Don't hesitate to ask questions and contribute to improving this onboarding guide based on your experience.