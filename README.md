# SAT Report Generator - Complete End-to-End Documentation

## Overview

The **SAT Report Generator** is a comprehensive Flask-based web application designed specifically for **Cully Automation** to automate the creation, approval, and management of System Acceptance Testing (SAT) reports. This application transforms a manual, time-consuming process into a streamlined digital workflow with role-based access control, automated document generation, and seamless approval workflows.

## 🎯 What This Application Does

### Core Purpose
The application automates the complete lifecycle of SAT (System Acceptance Testing) reports from creation to final client delivery:

1. **Digital Form Interface** - Replace manual Word document editing with a guided web form
2. **Automated Document Generation** - Generate professional Word documents using company templates
3. **Role-Based Approval Workflow** - Route reports through Technical Manager and Project Manager approvals
4. **User Management System** - Complete authentication, authorization, and user lifecycle management
5. **Secure Document Storage** - Organize and store all reports with proper access controls
6. **Email Notifications** - Automated notifications for approvals, rejections, and status changes

### Key Business Problems Solved
- **Manual Document Creation** → Automated template-based generation
- **Email-Based Approvals** → Integrated workflow management  
- **Document Version Control** → Centralized storage and tracking
- **Access Control Issues** → Role-based security system
- **Report Status Confusion** → Real-time status tracking
- **Client Delivery Delays** → Streamlined final document preparation

### FDS Generation from SAT Reports
The application now supports the automatic generation of a Functional Design Specification (FDS) from an existing System Acceptance Test (SAT) report. This feature further streamlines the documentation workflow by leveraging the data already captured in the SAT to create a baseline FDS.

- **One-Click Generation**: Engineers can generate an FDS with a single click from the "My Reports" page.
- **Data Mapping**: The system automatically maps relevant fields from the SAT report to the corresponding sections in the FDS, including:
    - Document Header Information
    - System Overview
    - Equipment and Hardware Lists
    - I/O Signal Mappings
    - Communication and Modbus Registers
- **Extensible**: The generation logic is designed to be extensible, with AI-powered enhancements planned for future releases.
- **AI-Powered Datasheet Fetching**: The system uses an AI service to automatically find and link to manufacturer datasheets for equipment listed in the SAT report, enriching the generated FDS with valuable technical documentation.

## 🏗 Complete Application Architecture

### User Roles & Responsibilities

#### **Admin**
- **User Management**: Approve new registrations, assign roles, enable/disable accounts
- **System Configuration**: Manage company logo, storage settings, system parameters
- **Database Monitoring**: Monitor system health and connectivity
- **Full Access**: Can view, edit, and manage all reports and users

#### **Engineer**
- **Report Creation**: Fill out SAT forms with technical details, test results, and supporting documentation
- **Document Upload**: Add supporting files, images, and technical drawings
- **Initial Submission**: Submit reports for Technical Manager review
- **Edit Until Approved**: Can modify reports until Technical Manager approval

#### **Technical Manager (Automation Manager)**
- **Technical Review**: Review engineering submissions for technical accuracy
- **Approve/Reject Reports**: First-stage approval with detailed feedback
- **Technical Oversight**: Ensure compliance with technical standards
- **Progress Tracking**: Monitor team's report submissions

#### **Project Manager**
- **Final Review**: Second-stage approval for client-ready documents
- **Business Validation**: Ensure reports meet project requirements
- **Client Communication**: Prepare final documents for client delivery
- **Project Oversight**: Track all project-related SAT reports

### Technical Architecture

#### **Frontend Layer**
- **Responsive Web Interface**: Mobile-friendly design using custom CSS
- **Interactive Forms**: Dynamic form fields with client-side validation
- **File Upload Handling**: Drag-and-drop file uploads with progress indicators
- **Digital Signatures**: Canvas-based signature capture for approvals
- **Real-time Updates**: AJAX-based status updates and notifications

#### **Backend Layer**
- **Flask Web Framework**: Python-based web application with modular blueprint structure
- **SQLAlchemy ORM**: Database abstraction with PostgreSQL/SQLite support
- **Authentication System**: Flask-Login with secure password hashing
- **Authorization Layer**: Role-based access control decorators
- **Email Integration**: SMTP integration for automated notifications
- **Caching System**: Redis-based caching for improved performance
- **Background Tasks**: Celery for asynchronous processing

#### **Document Processing Engine**
- **Template Processing**: Uses company-specific Word templates (SAT_Template.docx)
- **Field Replacement**: Advanced template tag replacement system
- **Format Preservation**: Maintains company branding, colors, fonts, and styling
- **PDF Conversion**: Windows COM integration for automatic PDF generation
- **File Management**: Organized storage with proper naming conventions

#### **Database Schema**
- **Users Table**: User accounts with roles, status, and authentication data
- **Reports Table**: Base report data with relationships to specific report types
- **SAT Reports Table**: Specialized SAT report structure with detailed form data
- **FDS Reports Table**: Stores generated Functional Design Specification (FDS) reports, linked to their parent SAT report.
- **FDS/HDS/Site Survey Reports**: Additional report types with specialized fields
- **System Settings**: Configurable application parameters
- **Approval Tracking**: Complete audit trail of all approval actions
- **Notifications**: User notification system for workflow events

## 🔄 Complete User Journey

### 1. New User Onboarding
```
Visit Application → Registration Form → Admin Notification → 
Admin Approval → Role Assignment → User Activated → Dashboard Access
```

**Details:**
- Users register with full name, email, and requested role
- Registration creates "Pending" status account
- Admin receives notification and reviews request
- Admin approves and assigns appropriate role (Engineer/TM/PM)
- User receives activation notification and can log in
- User is directed to role-specific dashboard

### 2. SAT Report Creation Workflow

#### **Engineer Phase**
```
Create New Report → Fill SAT Form → Upload Files → Add Signatures → 
Submit for Review → Technical Manager Notification
```

**SAT Form Sections:**
- **Project Information**: Project reference, document title, client details, revision info
- **Personnel**: Prepared by, reviewed by (Technical Manager), approved by (Project Manager)
- **Test Results**: Detailed test data, pass/fail status, technical specifications
- **Supporting Documents**: File uploads, technical drawings, test certificates
- **Comments & Notes**: Additional technical information, special requirements
- **Digital Signatures**: Engineer signature with timestamp

#### **Technical Manager Review**
```
Receive Notification → Review Technical Content → Check Test Data → 
Add Comments → Approve/Reject → Engineer Notification
```

**Review Process:**
- Access assigned reports from TM dashboard
- Review all technical content and test results
- Verify supporting documentation completeness
- Add technical comments and feedback
- Digital signature approval for technical accuracy
- Automatic notification to Engineer (if rejected) or Project Manager (if approved)

#### **Project Manager Final Approval**
```
Receive Notification → Business Review → Client Requirements Check → 
Final Comments → Approve for Client → Document Generation
```

**Final Review Process:**
- Verify project requirements compliance
- Review client deliverable requirements
- Check document completeness and professional presentation
- Add final project comments
- Digital signature for client delivery approval
- Trigger final document generation

### 3. Document Generation Process
```
PM Approval → Template Processing → Field Replacement → 
Format Verification → PDF Generation → Storage → Download Ready
```

**Technical Process:**
- Load company SAT_Template.docx template
- Replace all template tags with actual form data:
  - `{{ PROJECT_REFERENCE }}` → Actual project number
  - `{{ DOCUMENT_TITLE }}` → Report title
  - `{{ DATE }}` → Report date
  - `{{ CLIENT_NAME }}` → Client company name
  - `{{ REVISION }}` → Document revision number
  - Plus all other form fields
- Preserve all company branding, colors, fonts, logos
- Generate both .docx and .pdf versions
- Store with standardized naming: `SAT_[PROJECT_NUMBER].docx`

### 4. Status Tracking & Notifications

#### **Report Status States**
- **DRAFT** - Being created by Engineer
- **SUBMITTED** - Awaiting Technical Manager review
- **TM_APPROVED** - Technical Manager approved, awaiting PM review
- **PM_APPROVED** - Project Manager approved, ready for client
- **REJECTED** - Rejected at any stage with feedback
- **DELIVERED** - Final document delivered to client

#### **Automated Notifications**
- **Submission Notifications** - TM notified when Engineer submits
- **Approval Notifications** - PM notified when TM approves
- **Rejection Notifications** - Engineer notified with detailed feedback
- **Final Approval** - All stakeholders notified when ready for client
- **System Alerts** - Database issues, login attempts, system status

## 🛠 Installation & Configuration

### Prerequisites
- **Python 3.7+** with pip package manager
- **PostgreSQL Database** (production) or SQLite (development)
- **Windows Server** (required for Word to PDF conversion)
- **SMTP Email Account** (Gmail recommended) for notifications
- **Redis Server** (optional, for caching and session management)

### Environment Configuration (.env)
```env
# Flask Application Configuration
SECRET_KEY=your-super-secret-key-here
CSRF_SECRET_KEY=your-csrf-protection-key
FLASK_DEBUG=False  # Set to True for development only

# Database Configuration
DATABASE_URL=postgresql://username:password@host:5432/database
# Development alternative: DATABASE_URL=sqlite:///sat_reports.db

# Email Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# File Storage Configuration
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=16777216  # 16MB max upload size
ALLOWED_EXTENSIONS=pdf,png,jpg,jpeg,docx,xlsx,csv

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379/0
```

### Installation Steps

1. **Clone Repository**
   ```bash
   git clone https://github.com/your-org/sat-report-generator.git
   cd sat-report-generator
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Database**
   ```bash
   flask db init
   flask db migrate -m "Initial migration"
   flask db upgrade
   ```

5. **Create Required Directories**
   ```bash
   python deploy.py
   ```

6. **Start Development Server**
   ```bash
   flask run
   ```

## 📊 System Monitoring & Maintenance

### Database Maintenance
- **Backup Schedule**: Daily automated backups
- **Cleanup Tasks**: Temporary file cleanup every 24 hours
- **Performance Monitoring**: Query optimization and index management

### Security Measures
- **CSRF Protection**: All forms protected against cross-site request forgery
- **Password Security**: Bcrypt hashing with appropriate work factor
- **Session Management**: Secure, time-limited sessions with proper invalidation
- **Input Validation**: Client and server-side validation of all inputs
- **Access Controls**: Strict role-based access control on all routes

### Troubleshooting Common Issues
- **Database Connection Errors**: Check PostgreSQL service status and credentials
- **Email Sending Failures**: Verify SMTP settings and server connectivity
- **PDF Generation Issues**: Ensure Word is properly installed on the server
- **File Upload Problems**: Check directory permissions and file size limits

## 📚 Additional Resources

For more detailed technical information, please refer to the [TECHNICAL_DOCUMENTATION.md](TECHNICAL_DOCUMENTATION.md) file, which contains:

- Detailed system architecture diagrams
- Complete API documentation
- Component interface specifications
- Call hierarchy and dependencies
- List of potentially redundant files

## 🔄 Version Control

This documentation has been updated as part of a systematic code analysis. No functional code has been modified during this documentation update process.

---

*Last Updated: August 2023*