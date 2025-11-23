# Overview

This is a comprehensive Flask-based web application for generating System Acceptance Testing (SAT) reports, specifically designed for Cully Automation. The application provides a complete user management system with role-based access control, admin approval workflows, and multi-step report generation capabilities. Users can create detailed SAT reports through a guided interface, with built-in approval workflows for Technical Managers and Project Managers, and automated document generation in Word and PDF formats.

## Recent Updates

### November 23, 2025 - Intelligent Lookup System & Document Corruption Fix (COMPLETE)
- **Word Document Corruption FIXED**: Removed InlineImage objects that were corrupting Word documents
- **Intelligent Lookup Service Created**: Built reusable Tier 1→2→3→Manual pattern for any resource type
- **AI-Powered Module Lookup**: System automatically fetches module details from any user request using tiered search:
  - Tier 1: Database (previously found modules) - instant
  - Tier 2: Hardcoded common modules - instant  
  - Tier 3: Gemini AI search (with rate-limit fallback) - saves to database automatically
  - Tier 4: Manual entry form - user-verified data saved to database
- **Automatic Caching**: All discovered modules stored in database for future users (shared knowledge)
- **IO Builder Enhancements**: Fixed quota handling, added manual entry endpoint, improved error logging
- **Reusable Search Endpoints**: Created `/api/search/templates`, `/api/search/signals`, `/api/search/components` for any resource
- **App.py Updated**: Registered intelligent search blueprint with all search functionality

### October 2, 2025 - Word Document Corruption Fix (RESOLVED)
- **Root Cause Identified**: InlineImage objects from docxtpl library were corrupting the Word document XML structure
- **Solution Implemented**: Removed ALL InlineImage creation code that was causing "unreadable content" errors in Microsoft Word
- **Technical Details**: docxtpl.InlineImage objects were producing invalid XML when rendering templates, causing 100% document corruption
- **Current Behavior**: Documents now generate successfully without images embedded (images are still saved to database/filesystem for future enhancement)
- **Result**: Generated Word documents now open correctly in Microsoft Word without any corruption errors
- **Future Enhancement**: Image rendering can be re-implemented using alternative approach (e.g., post-processing with python-docx) if needed

### October 1, 2025 - Comprehensive Save Progress Enhancements
- **Signal tables now save correctly**: Added processing for all signal tables (Digital Signals, Analogue Input/Output, Digital Output, Modbus Digital/Analogue)
- **Image uploads implemented**: SCADA, Trends, and Alarm screenshots now save to database with proper file validation
- **Security improvements**: Added file extension validation, PIL image verification, and image removal handling
- **Data integrity protection**: All tables use conditional processing to preserve existing data when saving from earlier steps
- All reported missing sections now save and load correctly in edit mode

### October 1, 2025 - Edit Mode Data Display Fixes  
- **Fixed Step 2 approver email visibility**: Added value attributes to hidden email/name fields and JavaScript initialization to populate display fields when editing existing reports
- **Fixed Step 4+ table data visibility**: Updated save_progress route to process and save list/table fields
- **Data integrity protection**: Implemented conditional list field processing that preserves existing data when saving from earlier steps
- Edit mode now correctly displays all saved data across all form steps

### October 1, 2025 - SAT Report State Management Fixes
- Fixed critical bug where new reports showed previously saved data from localStorage
- Implemented proper state isolation between new and existing reports using is_new_report flag
- Added cross-report contamination prevention with submission_id tracking in localStorage
- Enhanced saveProgress() and autoSaveProgress() to save to backend and update submission_id
- Added automatic data saving when navigating between form steps (Next/Back buttons)
- Implemented legacy localStorage cleanup for reports created before submission_id tracking
- Ensured localStorage backup consistency by including submission_id after server response

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

## Intelligent Lookup System (NEW)
- **Purpose**: Automatic discovery and caching of any resource (modules, templates, signals, components)
- **Tier 1 (Database)**: Check PostgreSQL for previously found resources
- **Tier 2 (Internal Cache)**: Check hardcoded common resources (ABB DC523, Siemens modules, etc.)
- **Tier 3 (AI)**: Use Gemini AI to search online for specifications
- **Tier 4 (Manual)**: Fallback form for user to enter specifications manually
- **Auto-Caching**: All discovered resources automatically saved to database for all future users
- **Use Cases**: Module specs, report templates, signal definitions, component configurations

## Database Design
- **User Management**: Users table with roles (Admin, Engineer, TM, PM), status tracking, and password hashing
- **Report Storage**: Reports table with JSON data storage for form submissions
- **Module Specs**: ModuleSpec table for caching discovered I/O module specifications
- **System Settings**: Key-value configuration storage for application settings
- **Notifications**: User notification system with read/unread status tracking

## Document Generation
- **Template Processing**: DocxTemplate for Word document generation from templates
- **PDF Conversion**: Windows COM integration (pywin32) for automated Word-to-PDF conversion
- **File Management**: Organized directory structure for uploads, signatures, and generated outputs
- **Image Handling**: Images saved to filesystem and database, but NOT embedded in Word (prevents corruption)

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
