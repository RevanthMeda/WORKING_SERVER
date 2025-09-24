#!/usr/bin/env python
"""
Verify that PENDING reports are correctly unlocked and editable
"""

import os
import sys
import json
from datetime import datetime

# Add the current directory to the path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the necessary modules
from app import create_app
from models import db, Report, User

# Create the Flask app
app = create_app('default')

def verify_reports():
    """Verify the locked status of all reports"""
    
    with app.app_context():
        print("Verifying report lock status...")
        print("=" * 60)
        
        # Get all reports
        all_reports = Report.query.all()
        print(f"Total reports in database: {len(all_reports)}")
        print()
        
        # Group reports by status
        reports_by_status = {}
        for report in all_reports:
            status = report.status or 'DRAFT'
            if status not in reports_by_status:
                reports_by_status[status] = []
            reports_by_status[status].append(report)
        
        # Check each status group
        issues_found = []
        
        for status, reports in reports_by_status.items():
            print(f"\n{status} Reports ({len(reports)} total):")
            print("-" * 40)
            
            for report in reports:
                # Determine what locked should be
                expected_locked = False
                
                if status == 'APPROVED':
                    expected_locked = True
                elif report.approvals_json:
                    try:
                        approvals = json.loads(report.approvals_json)
                        # Check if Automation Manager (stage 1) approved
                        for approval in approvals:
                            if approval.get('stage') == 1 and approval.get('status') == 'approved':
                                expected_locked = True
                                break
                    except:
                        pass
                
                # Check if there's an issue
                if report.locked != expected_locked:
                    issues_found.append({
                        'id': report.id,
                        'status': status,
                        'locked': report.locked,
                        'expected': expected_locked,
                        'title': report.document_title or 'Untitled'
                    })
                    status_icon = "❌ ISSUE"
                else:
                    status_icon = "✓"
                
                print(f"  {status_icon} Report {report.id[:8]}...")
                print(f"      Title: {report.document_title or 'Untitled'}")
                print(f"      Locked: {report.locked} (Expected: {expected_locked})")
                print(f"      User: {report.user_email}")
                
                # Show approval status if present
                if report.approvals_json:
                    try:
                        approvals = json.loads(report.approvals_json)
                        if approvals:
                            print(f"      Approvals:")
                            for approval in approvals:
                                stage = approval.get('stage', '?')
                                status = approval.get('status', 'unknown')
                                approver = approval.get('approver_email', 'N/A')
                                print(f"        - Stage {stage}: {status} ({approver})")
                    except:
                        pass
        
        # Summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        
        if issues_found:
            print(f"\n⚠️  Found {len(issues_found)} reports with incorrect lock status:")
            for issue in issues_found:
                print(f"  - Report {issue['id']}: status={issue['status']}, "
                      f"locked={issue['locked']} (should be {issue['expected']})")
            print("\n❌ VERIFICATION FAILED - Issues found!")
            return False
        else:
            print("\n✅ ALL REPORTS HAVE CORRECT LOCK STATUS!")
            print("\nReport Status Summary:")
            for status, reports in reports_by_status.items():
                locked_count = sum(1 for r in reports if r.locked)
                unlocked_count = len(reports) - locked_count
                print(f"  {status}: {len(reports)} reports "
                      f"({locked_count} locked, {unlocked_count} unlocked)")
            
            # Show specific info for PENDING reports
            if 'PENDING' in reports_by_status:
                pending_reports = reports_by_status['PENDING']
                print(f"\n✅ All {len(pending_reports)} PENDING reports are correctly UNLOCKED")
                print("   Engineers can edit their pending reports until approved!")
            
            return True

if __name__ == '__main__':
    success = verify_reports()
    sys.exit(0 if success else 1)