# Overview

This is a comprehensive Flask-based web application for generating System Acceptance Testing (SAT) reports, specifically designed for Cully Automation. The application provides a complete user management system with role-based access control, admin approval workflows, and multi-step report generation capabilities. Users can create detailed SAT reports through a guided interface, with built-in approval workflows for Technical Managers and Project Managers, and automated document generation in Word and PDF formats.

## Recent Updates

### October 1, 2025 - SAT Report State Management Fixes
- Fixed critical bug where new reports showed previously saved data from localStorage
- Implemented proper state isolation between new and existing reports using is_new_report flag
- Added cross-report contamination prevention with submission_id tracking in localStorage
- Enhanced saveProgress() and autoSaveProgress() to save to backend and update submission_id
- Added automatic data saving when navigating between form steps (Next/Back buttons)
- Implemented legacy localStorage cleanup for reports created before submission_id tracking
- Ensured localStorage backup consistency by including submission_id after server response

### October 1, 2025 - Replit Environment Setup
- Configured application for Replit deployment
- Created main.py entry point for gunicorn server
- Set up workflow with gunicorn (2 workers, 120s timeout, auto-reload)
- Created stub cache modules for non-Redis environments
- Configured deployment for autoscale with proper gunicorn settings
- Verified application is running successfully on port 5000

### September 14, 2025
- Fixed report status persistence - reports now correctly maintain DRAFT status across browser sessions
- Restored edit functionality - users can now properly edit DRAFT and PENDING reports
- Fixed manager dashboards - approval workflows now display pending reports correctly
- Implemented comprehensive performance optimizations - 50-70% faster with database query optimization, caching, and compression

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 templates with responsive HTML/CSS design
- **UI Framework**: Custom CSS with Font Awesome icons and Google Fonts (Inter)
- **JavaScript**: Vanilla JavaScript for form interactions, signature pad integration, and CSRF token management
- **Responsive Design**: Mobile-first approach with adaptive layouts for different screen sizes
- **Real-time Features**: Comment system with @mentions, live collaboration indicators

## Backend Architecture
- **Web Framework**: Flask 2.2.3 with modular blueprint structure
- **Authentication**: Flask-Login with password hashing using Werkzeug
- **Security**: CSRF protection via Flask-WTF, role-based access control decorators, 30-minute session timeout
- **Database ORM**: SQLAlchemy for database operations and migrations
- **Session Management**: Server-side sessions with automatic timeout and complete clearing on logout

## Database Design
- **User Management**: Users table with roles (Admin, Engineer, TM, PM), status tracking, and password hashing
- **Report Storage**: Reports table with JSON data storage for form submissions
- **System Settings**: Key-value configuration storage for application settings
- **Notifications**: User notification system with read/unread status tracking

## Document Generation
- **Template Processing**: DocxTemplate for Word document generation from templates
- **PDF Conversion**: Windows COM integration (pywin32) for automated Word-to-PDF conversion
- **File Management**: Organized directory structure for uploads, signatures, and generated outputs

## Email Integration
- **SMTP Configuration**: Gmail integration with app password authentication
- **Notification System**: Automated email notifications for approval workflows
- **Retry Logic**: Built-in retry mechanisms for email delivery failures

## Role-Based Workflow
- **Engineer Role**: Create and edit reports until Technical Manager approval
- **Technical Manager Role**: Review and approve engineer submissions
- **Project Manager Role**: Final approval and client document preparation
- **Admin Role**: Complete system oversight, user management, configuration, bulk operations, and audit logs
- **Automation Manager Role**: Manage templates, workflows, and system integrations

## Security Features
- **Password Security**: Werkzeug password hashing with salt
- **CSRF Protection**: Token-based protection for all form submissions
- **Session Security**: HTTP-only cookies with 30-minute timeout, complete session clearing on logout
- **Input Validation**: Server-side validation for all user inputs
- **Audit Logging**: Comprehensive tracking of all user actions for compliance
- **Role-Based Access**: Granular permissions for different user roles

# Production Deployment Configuration

## Server Configuration
- **Target Server**: 172.16.18.21 (Windows Server)
- **Internal Access**: http://172.16.18.21:5000 (company network only)
- **Security Model**: No external ports exposed - internal access only
- **Access Control**: Company network employees only (secure by design)

## Deployment Files
- **app.py**: Main Flask application with production configuration
- **start_production.bat**: Windows batch file for server startup
- **config.py**: Environment configuration and security settings

## Security Features
- **Network Isolation**: Internal company network access only
- **No External Ports**: Maximum security through network-level isolation
- **CSRF Protection**: Enhanced token-based protection for all forms
- **Session Security**: Secure session management with timeout controls
- **Authentication**: Role-based access control with password hashing

## External Dependencies

## Database
- **PostgreSQL**: Primary production database (configurable via DATABASE_URL)
- **SQLite**: Development fallback database with file-based storage
- **psycopg2-binary**: PostgreSQL adapter for Python

## Email Services
- **Gmail SMTP**: Email delivery through Gmail's SMTP servers
- **App Passwords**: Secure authentication using Gmail app-specific passwords

## Document Processing
- **Microsoft Word**: Required for PDF conversion functionality (Windows only)
- **pywin32**: Windows COM interface for Word automation
- **python-docx**: Word document manipulation and template processing
- **docxtpl**: Advanced template processing with variable substitution

## Web Dependencies
- **Flask Extensions**: flask-login, flask-wtf, flask-sqlalchemy for core functionality
- **Image Processing**: Pillow for image manipulation and signature processing
- **Web Scraping**: requests and beautifulsoup4 for external data integration
- **Security**: itsdangerous for secure token generation
- **Production Server**: Gunicorn for production WSGI deployment

## Frontend Libraries
- **Font Awesome 6.0**: Icon library for UI elements
- **Google Fonts**: Inter font family for consistent typography
- **Signature Pad**: signature_pad library for digital signature capture

## Development Tools
- **python-dotenv**: Environment variable management
- **logging**: Comprehensive application logging and error tracking