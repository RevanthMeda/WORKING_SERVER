# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

The SAT Report Generator is a comprehensive Flask-based web application for Cully Automation that automates the creation, approval, and management of System Acceptance Testing (SAT) reports. The application features role-based workflows, document generation, and automated email notifications.

### Key Business Purpose
- Digitize manual SAT report creation process
- Implement structured approval workflows (Engineer → Technical Manager → Project Manager)
- Generate professional Word/PDF documents from templates
- Manage multi-type reports: SAT, FDS, HDS, Site Survey, SDS, FAT

## Development Commands

### Core Development Tasks
```powershell
# Start development server
make run
# OR
python app.py

# Start with debug mode
make run-debug
# OR 
$env:FLASK_ENV="development"; $env:FLASK_DEBUG="1"; python app.py

# Start production server
make run-production
# OR
python production_start.py
```

### Database Operations
```powershell
# Initialize database
make db-init
flask db init

# Create migration
make migrate MESSAGE="Description of changes"
flask db migrate -m "Description"

# Apply migrations
make db-upgrade
flask db upgrade

# Rollback migration
make db-downgrade
flask db downgrade

# Run database CLI tools
python manage_db.py --help
python init_new_db.py  # Reset database
```

### Testing
```powershell
# Run all tests
make test
python -m pytest tests/ -v

# Run specific test types
make test-unit       # Unit tests only
make test-integration # Integration tests
make test-e2e        # End-to-end tests
make test-performance # Performance tests

# Run with coverage
make test-coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Code Quality
```powershell
# Format code
make format
black . --line-length=127
isort . --profile=black --line-length=127

# Lint code
make lint
flake8 . --max-line-length=127
pylint . --exit-zero

# Type checking
make type-check
mypy . --ignore-missing-imports

# Security checks
make security-check
bandit -r . --exclude="tests,migrations,venv"

# Run all quality checks
make quality-check
```

### Development Environment Setup
```powershell
# Full development setup
make setup-dev

# Manual setup
pip install -r requirements.txt -r requirements-test.txt
make setup-pre-commit
make db-init
make db-upgrade
```

## High-Level Architecture

### Application Structure
- **Flask Application**: Modular blueprint-based architecture with role-based access control
- **Database Layer**: SQLAlchemy ORM with PostgreSQL/SQLite, optimized connection pooling
- **Document Processing**: Word template processing with automated PDF generation (Windows COM)
- **Caching System**: Redis-based caching for performance optimization
- **Authentication**: Flask-Login with secure session management and CSRF protection

### Core Components

#### User Roles & Workflow
1. **Engineer**: Creates reports, submits for approval
2. **Technical Manager (Automation Manager)**: Technical review and first-stage approval
3. **Project Manager**: Business review and final approval
4. **Admin**: Full system access and user management

#### Report Types & Models
- **Base Report Model**: Common fields across all report types
- **SAT Reports**: Site Acceptance Testing with detailed test data
- **FDS Reports**: Functional Design Specification
- **HDS Reports**: Hardware Design Specification  
- **Site Survey Reports**: SCADA migration surveys
- **SDS/FAT Reports**: Additional specialized reports

### Key Directories
```
├── api/             # API endpoints and business logic
├── routes/          # Flask blueprints for web routes
├── models.py        # SQLAlchemy models and database schema
├── config/          # Hierarchical configuration system
├── database/        # Database utilities, migrations, performance
├── cache/           # Redis caching system
├── monitoring/      # Logging, metrics, tracing
├── tests/          # Comprehensive test suite
├── templates/      # Jinja2 templates for web interface
├── static/         # Static assets (CSS, JS, images)
├── docs/           # Architecture and API documentation
└── scripts/        # Development and deployment utilities
```

## Development Guidelines

### Database Development
- **Models**: All models in `models.py` with relationships and constraints
- **Migrations**: Always create migrations for schema changes using Flask-Migrate
- **Performance**: Use query optimization utilities in `database/` directory
- **Testing**: Database tests in `tests/unit/test_models.py` and `tests/integration/`

### API Development
- **RESTful Design**: Follow resource-based URL patterns in `routes/api.py`
- **Authentication**: All API endpoints require authentication via `@login_required`
- **Error Handling**: Use standardized error responses from `api/errors.py`
- **Validation**: Use schemas from `api/schemas.py` for request/response validation

### Frontend Development
- **Templates**: Jinja2 templates with role-based rendering
- **Static Assets**: Organized in `static/` with proper versioning
- **JavaScript**: Minimal vanilla JS, focus on progressive enhancement
- **CSS**: Custom CSS with responsive design principles

### Security Considerations
- **CSRF Protection**: Enabled on all forms via `WTF_CSRF_ENABLED=True`
- **Role-Based Access**: Use `@role_required` decorator from `auth.py`
- **Input Validation**: Server-side validation for all user inputs
- **File Uploads**: Restricted file types in `config.py` `ALLOWED_EXTENSIONS`

### Document Generation
- **Templates**: Word templates in `templates/` directory with placeholder tags
- **Processing**: Use `python-docx` and `docxtpl` libraries in `utils.py`
- **PDF Generation**: Windows COM integration via `win32com.client` (Windows only)
- **File Storage**: Organized in `static/uploads/` and `outputs/` directories

### Caching Strategy
- **Application Cache**: In-memory caching for frequently accessed data
- **Redis Cache**: Distributed caching configured in `config.py`
- **Session Storage**: Redis-based sessions via `cache/session_store.py`
- **Cache Invalidation**: Proper invalidation on data updates

### Testing Strategy
- **Unit Tests**: Individual component testing in `tests/unit/`
- **Integration Tests**: Component interaction testing in `tests/integration/`
- **End-to-End Tests**: Complete workflow testing in `tests/e2e/`
- **Performance Tests**: Load testing configuration in `tests/performance/`

### Configuration Management
- **Environment Variables**: Loaded via `python-dotenv` in `config.py`
- **Hierarchical Config**: Advanced config system in `config/manager.py`
- **Secrets Management**: Secure handling via `config/secrets.py`
- **Environment Specific**: Development, testing, production configs

### Error Handling & Monitoring
- **Logging**: Structured logging via `monitoring/logging_config.py`
- **Metrics**: Application metrics in `monitoring/metrics.py`
- **Tracing**: Distributed tracing setup in `monitoring/tracing.py`
- **Health Checks**: Application health monitoring endpoints

### Windows-Specific Considerations
- **PDF Generation**: Requires Microsoft Word via COM automation
- **File Locking**: Cross-platform file locking in `utils.py`
- **Path Handling**: Windows path compatibility throughout codebase
- **Service Installation**: Production deployment via `deploy.py`

### Performance Optimization
- **Database**: Connection pooling and query optimization
- **Caching**: Multi-layer caching strategy (L1: Memory, L2: Redis)
- **Background Tasks**: Celery integration for async processing
- **Static Assets**: Optimized serving and CDN integration

### AI Integration
- **Gemini API**: AI assistance configured via `GEMINI_API_KEY`
- **Report Enhancement**: AI-powered report suggestions and validation
- **Content Generation**: Automated content assistance features

The application follows enterprise-grade software architecture principles with emphasis on scalability, maintainability, and security. The modular design enables easy feature additions while maintaining code quality and performance standards.