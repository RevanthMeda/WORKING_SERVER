# SAT Report Generator - User Guide

## Welcome to SAT Report Generator

The SAT Report Generator is a comprehensive web application designed to streamline the creation, management, and approval of Site Acceptance Testing (SAT) reports. This user guide will help you navigate the system and make the most of its features.

## Table of Contents

1. [Getting Started](#getting-started)
2. [User Roles and Permissions](#user-roles-and-permissions)
3. [Creating Your First Report](#creating-your-first-report)
4. [Managing Reports](#managing-reports)
5. [Approval Workflow](#approval-workflow)
6. [File Management](#file-management)
7. [User Account Management](#user-account-management)
8. [Advanced Features](#advanced-features)
9. [Troubleshooting](#troubleshooting)
10. [Frequently Asked Questions](#frequently-asked-questions)

## Getting Started

### System Requirements

**Supported Browsers:**
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

**Internet Connection:**
- Stable internet connection required
- Minimum 1 Mbps for basic functionality
- 5+ Mbps recommended for file uploads

### Accessing the System

1. **Open your web browser** and navigate to your organization's SAT Report Generator URL
2. **Login Page**: You'll see the login screen with fields for email and password
3. **First-time users**: Click "Register" to create a new account (requires admin approval)

### Registration Process

**Step 1: Create Account**
1. Click "Register" on the login page
2. Fill in the registration form:
   - **Full Name**: Your complete name as it should appear on reports
   - **Email Address**: Your work email address
   - **Password**: Must be at least 12 characters with mixed case, numbers, and symbols
   - **Requested Role**: Select the role that matches your responsibilities
3. Click "Register"

**Step 2: Account Approval**
- Your account will be pending approval by an administrator
- You'll receive an email notification once approved
- Contact your system administrator if approval takes longer than expected

**Step 3: First Login**
1. Enter your email and password
2. You may be prompted to set up Multi-Factor Authentication (MFA) for enhanced security
3. Complete the MFA setup using an authenticator app like Google Authenticator or Authy

### Dashboard Overview

After logging in, you'll see the main dashboard with:

- **Navigation Menu**: Access to different sections (Reports, Users, Admin)
- **Quick Stats**: Overview of your reports and system activity
- **Recent Activity**: Latest actions and notifications
- **Quick Actions**: Shortcuts to common tasks

## User Roles and Permissions

### Engineer
**Responsibilities:**
- Create and edit SAT reports
- Upload supporting documents and images
- Submit reports for approval
- View own reports and their status

**Permissions:**
- ✅ Create new reports
- ✅ Edit draft reports
- ✅ Upload files to reports
- ✅ Submit reports for approval
- ✅ View own reports
- ❌ Approve reports
- ❌ Access admin functions
- ❌ Manage other users

### Project Manager (PM)
**Responsibilities:**
- Review and approve SAT reports
- Monitor project progress
- Manage approval workflows
- View team reports

**Permissions:**
- ✅ View all reports
- ✅ Approve/reject reports
- ✅ Add approval comments
- ✅ View user activity
- ✅ Generate reports
- ❌ Create reports (unless also Engineer)
- ❌ Access admin functions
- ❌ Manage users

### Automation Manager
**Responsibilities:**
- Oversee automation testing processes
- Create and manage complex reports
- Review technical implementations
- Coordinate with engineering teams

**Permissions:**
- ✅ Create and edit reports
- ✅ Upload files
- ✅ Submit reports for approval
- ✅ View team reports
- ✅ Access advanced features
- ❌ Approve reports (unless also PM)
- ❌ Access admin functions

### Administrator
**Responsibilities:**
- Manage user accounts
- Configure system settings
- Monitor system health
- Manage approval workflows

**Permissions:**
- ✅ All report functions
- ✅ Approve reports
- ✅ Manage users
- ✅ Access admin panel
- ✅ Configure system settings
- ✅ View audit logs
- ✅ Generate system reports

## Creating Your First Report

### Step 1: Start a New Report

1. **Navigate to Reports**: Click "Reports" in the main navigation
2. **Create New Report**: Click the "New Report" button
3. **Choose Report Type**: Select "SAT Report" (default)

### Step 2: Fill in Basic Information

**Document Information:**
- **Document Title**: Descriptive title for your report (e.g., "SAT Report for Conveyor System Alpha")
- **Document Reference**: Unique identifier (e.g., "DOC-2023-001")
- **Project Reference**: Project code or identifier (e.g., "PROJ-ALPHA-2023")
- **Client Name**: Name of the client or organization
- **Revision**: Document revision (start with "R1")

**Report Details:**
- **Prepared By**: Your name (auto-filled)
- **Date**: Report date (defaults to today)
- **Purpose**: Brief description of the testing purpose
- **Scope**: What systems/components are being tested

### Step 3: Add Test Cases

1. **Click "Add Test Case"** to create your first test
2. **Fill in test details**:
   - **Test Description**: What is being tested
   - **Expected Result**: What should happen
   - **Actual Result**: What actually happened
   - **Status**: Pass/Fail/Not Tested
   - **Comments**: Additional notes or observations

3. **Add more test cases** as needed using the "Add Test Case" button

### Step 4: Upload Supporting Files

1. **Click "Upload Files"** in the Files section
2. **Select files** from your computer:
   - Screenshots of test results
   - Configuration files
   - Technical drawings
   - Supporting documentation
3. **Add descriptions** for each file to help reviewers understand their purpose

### Step 5: Save and Review

1. **Save Draft**: Click "Save Draft" to save your progress
2. **Preview**: Use the "Preview" button to see how your report will look
3. **Edit as needed**: Make any necessary changes
4. **Submit for Approval**: When ready, click "Submit for Approval"

## Managing Reports

### Report Dashboard

The Reports dashboard shows all your reports with the following information:
- **Title**: Report name and document reference
- **Status**: Current status (Draft, Pending Approval, Approved, etc.)
- **Created**: When the report was created
- **Last Modified**: Most recent update
- **Actions**: Available actions for each report

### Report Statuses

**Draft**
- Report is being created or edited
- Only visible to the creator
- Can be edited freely
- Not yet submitted for review

**Pending Approval**
- Report has been submitted for review
- Cannot be edited by creator
- Awaiting PM or Admin approval
- Email notifications sent to approvers

**Approved**
- Report has been approved by authorized personnel
- Cannot be edited
- Ready for document generation
- Approval comments visible

**Rejected**
- Report was not approved
- Returned to Draft status
- Rejection comments provided
- Can be edited and resubmitted

**Generated**
- Final document has been created
- PDF available for download
- Report is locked from further changes
- Archive copy maintained

### Searching and Filtering

**Search Reports:**
- Use the search box to find reports by title, reference, or client name
- Search is case-insensitive and matches partial text

**Filter Options:**
- **Status**: Filter by report status
- **Date Range**: Show reports from specific time periods
- **Client**: Filter by client name
- **Created By**: Filter by report creator (Admin only)

**Sorting:**
- Click column headers to sort by that field
- Click again to reverse sort order
- Default sort is by creation date (newest first)

### Bulk Operations

**Select Multiple Reports:**
1. Check the boxes next to reports you want to manage
2. Use the "Actions" dropdown for bulk operations:
   - Export selected reports
   - Change status (Admin only)
   - Delete selected reports (Admin only)

## Approval Workflow

### Submitting for Approval

**Before Submission Checklist:**
- ✅ All required fields completed
- ✅ Test cases added with results
- ✅ Supporting files uploaded
- ✅ Report reviewed for accuracy
- ✅ Spelling and grammar checked

**Submission Process:**
1. **Open your draft report**
2. **Click "Submit for Approval"**
3. **Add submission comments** (optional but recommended)
4. **Confirm submission**
5. **Automatic notifications** sent to approvers

### Approval Process (For PMs and Admins)

**Reviewing Reports:**
1. **Navigate to "Pending Approvals"** in your dashboard
2. **Click on a report** to review it
3. **Review all sections**:
   - Document information
   - Test cases and results
   - Uploaded files
   - Overall completeness

**Making Approval Decisions:**

**To Approve:**
1. Click "Approve Report"
2. Add approval comments (optional)
3. Confirm approval
4. Report moves to "Approved" status

**To Reject:**
1. Click "Reject Report"
2. **Add rejection comments** (required)
3. Explain what needs to be fixed
4. Confirm rejection
5. Report returns to "Draft" status

### Approval Notifications

**Email Notifications:**
- Report submitters receive approval/rejection notifications
- Approvers receive notifications of new submissions
- All parties notified of status changes

**In-App Notifications:**
- Dashboard shows pending approvals count
- Recent activity feed shows approval actions
- Status indicators on report lists

## File Management

### Supported File Types

**Documents:**
- PDF (.pdf)
- Microsoft Word (.doc, .docx)
- Microsoft Excel (.xls, .xlsx)
- Text files (.txt)

**Images:**
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- BMP (.bmp)

**Other:**
- ZIP archives (.zip)
- Configuration files (.cfg, .conf)

### File Upload Process

1. **Click "Upload Files"** in the report editor
2. **Drag and drop files** or click "Choose Files"
3. **Wait for upload** to complete (progress bar shown)
4. **Add file descriptions** to help reviewers
5. **Organize files** by dragging to reorder

### File Management Features

**File Information:**
- Original filename preserved
- File size and type displayed
- Upload date and user tracked
- Download count monitored

**File Actions:**
- **Download**: Get a copy of the file
- **Preview**: View images and PDFs in browser
- **Replace**: Upload a new version
- **Delete**: Remove file from report

**File Security:**
- Virus scanning on upload
- Access control based on report permissions
- Audit trail of file access
- Secure storage with encryption

### File Size Limits

- **Maximum file size**: 16 MB per file
- **Total report size**: 100 MB per report
- **Supported formats**: See list above
- **Virus scanning**: All files scanned automatically

## User Account Management

### Profile Settings

**Accessing Your Profile:**
1. Click your name in the top-right corner
2. Select "Profile Settings"

**Editable Information:**
- **Full Name**: Update your display name
- **Email**: Change your email address (requires verification)
- **Password**: Update your password
- **Notification Preferences**: Choose how you receive notifications

### Security Settings

**Password Requirements:**
- Minimum 12 characters
- Must include uppercase and lowercase letters
- Must include numbers
- Must include special characters
- Cannot reuse last 5 passwords

**Multi-Factor Authentication (MFA):**
1. **Enable MFA**: Go to Security Settings
2. **Scan QR Code**: Use authenticator app
3. **Enter verification code**: Confirm setup
4. **Save backup codes**: Store in secure location

**Session Management:**
- **Active Sessions**: View all logged-in devices
- **Session Timeout**: Automatic logout after inactivity
- **Secure Logout**: Always log out when finished

### Notification Preferences

**Email Notifications:**
- ✅ Report approval/rejection
- ✅ New reports assigned for approval
- ✅ System maintenance notifications
- ❌ Daily activity summaries (optional)

**In-App Notifications:**
- ✅ Real-time status updates
- ✅ New comments on reports
- ✅ System alerts
- ✅ Approval reminders

## Advanced Features

### Report Templates

**Using Templates:**
1. **Create a template** from an existing report
2. **Save as template** with a descriptive name
3. **Use template** when creating new reports
4. **Customize** as needed for specific projects

**Template Management:**
- **Personal templates**: Available only to you
- **Shared templates**: Available to your team
- **Organization templates**: Available to all users

### System Architecture Designer

The FDS workflow now includes an interactive system architecture designer on **Step 6**.

- **Auto-generate**: Use the “Generate from Equipment List” button to pull images for each device and build an initial layout.
- **Drag & drop**: Move equipment nodes to match the project topology; the canvas stores your adjustments automatically when you save the FDS.
- **Swap imagery**: Click the camera icon on a node to paste an alternate image URL if the automatic match needs refinement.
- **Reuse assets**: Once an equipment model has an image, future projects re-use the cached asset, speeding up diagram assembly.

> Tip: Make sure your equipment list in Step 4 is complete before generating the diagram so every device appears in the canvas.

### Bulk Import/Export

**Exporting Reports:**
1. **Select reports** to export
2. **Choose export format**: PDF, Excel, or CSV
3. **Download** the exported file
4. **Use for reporting** or archival purposes

**Importing Test Data:**
1. **Prepare CSV file** with test case data
2. **Use import wizard** in report editor
3. **Map columns** to report fields
4. **Review and confirm** import

### API Access

**For Advanced Users:**
- **API documentation**: Available at `/api/v1/docs/`
- **Authentication**: Use API keys or JWT tokens
- **Rate limits**: 1000 requests per hour
- **Support**: Contact admin for API access

### Integration Features

**Email Integration:**
- **Automatic notifications** for workflow events
- **Custom email templates** for different actions
- **SMTP configuration** by administrators

**File Storage Integration:**
- **Cloud storage** support (S3, Azure, etc.)
- **Automatic backups** of uploaded files
- **CDN delivery** for faster downloads

## Troubleshooting

### Common Issues

**Cannot Log In**
- ✅ Check email and password spelling
- ✅ Ensure Caps Lock is off
- ✅ Try password reset if needed
- ✅ Contact admin if account is locked

**File Upload Fails**
- ✅ Check file size (max 16MB)
- ✅ Verify file type is supported
- ✅ Check internet connection
- ✅ Try a different browser

**Report Won't Save**
- ✅ Check all required fields are filled
- ✅ Ensure you have permission to edit
- ✅ Try refreshing the page
- ✅ Contact support if problem persists

**Slow Performance**
- ✅ Check internet connection speed
- ✅ Close unnecessary browser tabs
- ✅ Clear browser cache and cookies
- ✅ Try a different browser

### Browser Issues

**Clearing Browser Cache:**

**Chrome:**
1. Press Ctrl+Shift+Delete (Cmd+Shift+Delete on Mac)
2. Select "All time" for time range
3. Check "Cached images and files"
4. Click "Clear data"

**Firefox:**
1. Press Ctrl+Shift+Delete (Cmd+Shift+Delete on Mac)
2. Select "Everything" for time range
3. Check "Cache"
4. Click "Clear Now"

**Safari:**
1. Go to Safari > Preferences
2. Click "Privacy" tab
3. Click "Manage Website Data"
4. Click "Remove All"

### Getting Help

**Self-Service Options:**
- **Help Documentation**: Available in the app
- **Video Tutorials**: Linked from help pages
- **FAQ Section**: Common questions answered
- **System Status**: Check for known issues

**Contact Support:**
- **Email**: support@yourdomain.com
- **Phone**: Available during business hours
- **Live Chat**: Available in the application
- **Ticket System**: For complex issues

## Frequently Asked Questions

### General Questions

**Q: How do I reset my password?**
A: Click "Forgot Password" on the login page, enter your email, and follow the instructions in the reset email.

**Q: Can I work on reports offline?**
A: No, the system requires an internet connection. However, you can prepare content offline and copy it into the system when connected.

**Q: How long are reports stored in the system?**
A: Reports are stored indefinitely unless specifically deleted by an administrator. Archived reports remain accessible for audit purposes.

**Q: Can I collaborate with others on a report?**
A: Currently, only one person can edit a report at a time. However, you can add comments and share drafts for review.

### Technical Questions

**Q: What browsers are supported?**
A: Chrome 90+, Firefox 88+, Safari 14+, and Edge 90+. Mobile browsers are supported but desktop is recommended.

**Q: Is my data secure?**
A: Yes, all data is encrypted in transit and at rest. The system follows enterprise security standards and compliance requirements.

**Q: Can I integrate with other systems?**
A: Yes, the system provides REST APIs for integration. Contact your administrator for API access and documentation.

**Q: How do I report a bug or request a feature?**
A: Use the feedback form in the application or contact support with detailed information about the issue or request.

### Workflow Questions

**Q: Who can approve my reports?**
A: Users with PM or Admin roles can approve reports. Your organization may have specific approval workflows configured.

**Q: What happens if my report is rejected?**
A: The report returns to Draft status with comments from the reviewer. You can make changes and resubmit for approval.

**Q: Can I withdraw a report from approval?**
A: No, once submitted, only approvers can change the status. Contact your PM or Admin if you need to make urgent changes.

**Q: How do I know when my report is approved?**
A: You'll receive an email notification and see the status change in your dashboard. In-app notifications are also available.

This user guide provides comprehensive information to help you effectively use the SAT Report Generator. For additional help or specific questions not covered here, please contact your system administrator or support team.
