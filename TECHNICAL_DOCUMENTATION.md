# SAT Report Generator - Technical Documentation

## System Architecture

The SAT Report Generator is a Flask-based web application designed to streamline the creation, management, and approval of various technical reports, with a primary focus on Site Acceptance Testing (SAT) reports.

### Core Components

1. **Web Application (Flask)**
   - Handles HTTP requests, routing, and view rendering
   - Manages user sessions and authentication
   - Coordinates between different system components

2. **Database Layer (SQLAlchemy)**
   - Stores user data, report content, and system settings
   - Manages relationships between different data entities
   - Provides query capabilities for report filtering and search

3. **Document Processing Engine**
   - Generates formatted reports in various formats (DOCX, PDF)
   - Processes templates with user-provided data
   - Handles image and attachment inclusion

4. **Authentication System**
   - Manages user registration, login, and session tracking
   - Implements role-based access control
   - Secures API endpoints and sensitive operations

5. **Caching System**
   - Improves performance for frequently accessed data
   - Reduces database load for common queries
   - Configurable based on environment (development/production)

## Page Linkages and Navigation Flows

### Main Navigation Paths

1. **Authentication Flow**
   - `/auth/welcome` → Welcome page with registration and login options
   - `/auth/register` → User registration form
   - `/auth/login` → User login form
   - `/auth/logout` → User logout (redirects to welcome)

2. **Dashboard Flow (Role-Based)**
   - `/dashboard/` → Role-based redirect to appropriate dashboard
   - `/dashboard/admin` → Administrator dashboard
   - `/dashboard/engineer` → Engineer dashboard
   - `/dashboard/automation_manager` → Automation Manager dashboard
   - `/dashboard/pm` → Project Manager dashboard

3. **Report Creation Flow**
   - `/reports/new` → Select report type
   - `/reports/sat/wizard` → SAT report creation wizard
   - `/reports/sat/preview/<id>` → Preview generated SAT report
   - `/reports/sat/submit/<id>` → Submit report for approval

4. **Report Management Flow**
   - `/reports/my` → List user's reports
   - `/reports/view/<id>` → View specific report
   - `/reports/download/<id>` → Download report as PDF/DOCX
   - `/reports/archive/<id>` → Archive report

5. **Approval Flow**
   - `/approval/pending` → List reports pending approval
   - `/approval/review/<id>` → Review specific report
   - `/approval/approve/<id>` → Approve report
   - `/approval/reject/<id>` → Reject report with comments

6. **Edit Flow**
   - `/edit/report/<id>` → Edit existing report
   - `/edit/save/<id>` → Save edited report

## Component Interfaces

### Database Models and Relationships

1. **User Model**
   - Core user information and authentication data
   - Role-based permissions (Admin, Engineer, Automation Manager, PM)
   - Status tracking (Pending, Active, Disabled)

2. **Report Model**
   - Base report information (common across all report types)
   - One-to-one relationships with specific report types:
     - SATReport
     - FDSReport
     - HDSReport
     - SiteSurveyReport
     - SDSReport
     - FATReport

3. **Notification System**
   - User notifications for report status changes
   - Approval requests and responses
   - System announcements

4. **Template System**
   - Report templates with versioning
   - Field specifications for different report types
   - Reusable components across reports

### API Endpoints

1. **RESTful API (`/api/v1/`)**
   - Report management endpoints
   - User management endpoints
   - File upload/download endpoints
   - Search and filtering endpoints

2. **Legacy API (to be deprecated)**
   - Backward compatibility endpoints
   - Limited functionality compared to RESTful API

## Call Hierarchy and Dependencies

### Application Initialization

1. `create_app()` in app.py
   - Configures application settings
   - Initializes extensions (SQLAlchemy, Login Manager, etc.)
   - Registers blueprints for different routes
   - Sets up error handlers and middleware

2. Database Initialization
   - `init_db()` in models.py
   - Creates database tables if they don't exist
   - Validates schema consistency

3. Blueprint Registration
   - Routes are organized into logical blueprints:
     - auth_bp: Authentication routes
     - dashboard_bp: Dashboard routes
     - reports_bp: Report management routes
     - notifications_bp: Notification routes
     - approval_bp: Approval workflow routes
     - edit_bp: Report editing routes

### Request Processing Flow

1. Request received by Flask application
2. Middleware processing (CSRF protection, session validation)
3. Route handling by appropriate blueprint
4. Database operations via SQLAlchemy models
5. Template rendering or API response generation
6. Response returned to client

## Component Relationships

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Web Interface  │────▶│  Flask Routes   │────▶│  Database Layer │
│  (HTML/CSS/JS)  │     │  (Blueprints)   │     │  (SQLAlchemy)   │
│                 │◀────│                 │◀────│                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │  ▲                     │  ▲
                               │  │                     │  │
                               ▼  │                     ▼  │
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Authentication │◀───▶│  Business Logic │◀───▶│  Document       │
│  System         │     │  (Services)     │     │  Processing     │
│                 │     │                 │     │  Engine         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │  ▲
                               │  │
                               ▼  │
                        ┌─────────────────┐
                        │                 │
                        │  Caching System │
                        │  (Redis)        │
                        │                 │
                        └─────────────────┘
```

## Redundant or Obsolete Files

The following files appear to be redundant or obsolete and could potentially be safely removed:

1. `routes/dashboard_optimized.py` - Experimental optimization of dashboard routes that hasn't been integrated
2. `test_edit_functionality.py` - Test script that should be moved to the tests directory
3. `EDIT_FEATURE_FIX_SUMMARY.md` - Documentation of fixes that have already been implemented
4. `scripts/debt_dashboard.py` - Development tool not needed in production
5. `scripts/technical_debt_tracker.py` - Development utility for tracking technical debt
6. `4.0.0` - Temporary pip installation log file
7. `attached_assets/Pasted-E-report-generator-SERVER-python-app-py-Initializing-SAT-Report-Generator-2025-09-13-11-29-1757762970194_1757762970195.txt` - Debug log file that should be moved to logs directory
8. `utils.py` (lines 1247-1255) - Contains redundant duplicate functions that should be refactored

## Version Control Measures

To maintain version integrity during documentation updates:

1. All documentation changes are isolated to README.md and TECHNICAL_DOCUMENTATION.md
2. No functional code has been modified during this documentation process
3. File creation is limited to new documentation files only
4. All changes are tracked in this documentation for audit purposes

---

*This technical documentation was generated based on systematic analysis of the codebase on [Current Date].*
## Conversational Bot Enhancements
- Guided conversation now prompts for required SAT fields sequentially and validates responses before persisting them.
- Excel uploads can be multi-sheet; recognised values are auto-mapped to form fields with inline validation and immediate session updates.
- Bot messages that include a report identifier such as a UUID trigger a read-only document lookup and return a modern download link.

## Modern Document Pipeline
- /status/download-modern/<id> streams a regenerated DOCX built by services/report_renderer.generate_modern_sat_report using the existing SAT template for styling.
- The renderer assembles cover metadata, purpose/scope copy, and structured tables for any populated SAT list sections to maintain parity with legacy reports while modernising the layout.

## Bot Quick Summary Command
- A new natural-language trigger (e.g. "summary", "progress") now returns a structured snapshot of collected SAT fields, pending prompts, and missing required data via the bot conversation API.
- The response includes both machine-readable command metadata and a friendly progress message so UI clients can surface the state instantly.

## Session Performance Improvements
- `session_manager.is_session_valid` now batches filesystem writes by updating the activity timestamp at most once per minute, reducing disk churn under Flask-Session's filesystem backend.
- `app.before_request` caches the session validation result per request and disables `SESSION_REFRESH_EACH_REQUEST`, cutting redundant session store updates that previously caused server lag.
## Cully Copilot Assistant Refresh (2025-09-20)
- Persistent assistant widget is injected from `templates/partials/chatbot_widget.html` and loaded globally via `base.html` and `base_dashboard.html`, bringing a 3D launcher button, responsive chat panel, drag-and-drop upload zone, and quick-intent buttons.
- Styling and interaction logic live in `static/css/chatbot-assistant.css` and `static/js/chatbot-assistant.js`; the script bootstraps on demand, calls `/bot/start`, `/bot/message`, `/bot/reset`, `/bot/upload`, and injects CSRF headers automatically.
- Front-end supports `mode: "research"` when submitting messages, which hits the revised `services.bot_assistant.process_user_message` flow; the backend performs context-aware queries and enriches responses using DuckDuckGo Instant Answer data when `ASSISTANT_ALLOW_EXTERNAL=True` (default) and respects `ASSISTANT_RESEARCH_TIMEOUT` overrides.
- The upload pipeline now routes through `services.bot_assistant.ingest_upload`, allowing `.xlsx/.xls/.xlsm`, `.csv`, and common image formats. Excel/CSV data is normalised into SAT fields, images are hashed to block duplicates, analysed for resolution via Pillow (optional), and staged metadata is exposed in the response payload.
- New state field `BotConversationState.ingested_files` keeps lightweight metadata for uploaded media so later automation steps can map images into evidence sections; duplicate or low-value assets surface warnings immediately in the UI and in API responses.
- To plug in higher-power LLM automation, wire `services.ai_assistant.generate_sat_suggestion` or an external orchestrator inside `process_user_message` (e.g., when `normalized_mode == "default"` and all required fields are present) and reuse the collected context payload for prompts.
- Disable outbound research or run the assistant fully offline by setting `ASSISTANT_ALLOW_EXTERNAL=False`; the UI remains active and continues to automate internal workflows with gathered field data.

## UI Consistency Retrofit Workflow (2025-09-20)
- **Audit Intake:** Use `docs/ui_consistency_audit.md` to log annotated screenshots, severity, and remediation notes for Reports Notifications, I/O Builder, and Settings.
- **Design System Assets:** Reference `static/css/design-system.css` for shared color tokens, typography, spacing, card shells, status chips, and button patterns. Extend this file before adding module-specific overrides.
- **Implementation Loop:**
  1. Import shared stylesheet into module templates (or bundle) and remove redundant inline styles.
  2. Replace bespoke layouts with standard classes (`layout-shell`, `card-surface`, `status-chip`, utility spacing helpers).
  3. Validate on desktop/tablet/mobile; run accessibility spot checks (contrast, focus order, keyboard navigation).
- **Review & Sign-off:** After each module retrofit, capture before/after evidence, update the audit tracker, and schedule a cross-team walkthrough to confirm behavioral parity.
- **Maintenance:** Document any new components or tokens inside `design-system.css` and mirror the guidance here to keep the design system single-sourced.
