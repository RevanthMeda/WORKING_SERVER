#!/usr/bin/env python3
"""Test script to verify edit functionality is working"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from app import app
import json

def test_routes():
    """Test that all edit routes are available"""
    print("Testing Edit Routes...")
    
    with app.test_client() as client:
        # Test if edit route exists in edit blueprint
        print("\n1. Checking if edit.edit_report route exists...")
        try:
            with app.test_request_context():
                from flask import url_for
                # This will raise BuildError if route doesn't exist
                url = url_for('edit.edit_report', report_id='test-id')
                print(f"   ✓ edit.edit_report route exists: {url}")
        except Exception as e:
            print(f"   ✗ edit.edit_report route error: {e}")
        
        # Test if sat_wizard route exists
        print("\n2. Checking if reports.sat_wizard route exists...")
        try:
            with app.test_request_context():
                from flask import url_for
                url = url_for('reports.sat_wizard', submission_id='test-id', edit_mode='true')
                print(f"   ✓ reports.sat_wizard route exists: {url}")
        except Exception as e:
            print(f"   ✗ reports.sat_wizard route error: {e}")
        
        # Test if save_edit route exists
        print("\n3. Checking if edit.save_edit route exists...")
        try:
            with app.test_request_context():
                from flask import url_for
                url = url_for('edit.save_edit', report_id='test-id')
                print(f"   ✓ edit.save_edit route exists: {url}")
        except Exception as e:
            print(f"   ✗ edit.save_edit route error: {e}")
        
        # Test permission checks
        print("\n4. Testing permission checks in can_edit_report...")
        try:
            from routes.edit import can_edit_report
            from models import Report, User
            
            # Create mock objects for testing
            class MockUser:
                def __init__(self, role, email):
                    self.role = role
                    self.email = email
            
            class MockReport:
                def __init__(self, user_email, status, locked=False):
                    self.user_email = user_email
                    self.status = status
                    self.locked = locked
                    self.approvals_json = '[]'
            
            # Test Admin can edit any report
            admin_user = MockUser('Admin', 'admin@test.com')
            report = MockReport('engineer@test.com', 'DRAFT')
            assert can_edit_report(report, admin_user) == True
            print("   ✓ Admin can edit any report")
            
            # Test Engineer can edit own DRAFT report
            engineer_user = MockUser('Engineer', 'engineer@test.com')
            own_report = MockReport('engineer@test.com', 'DRAFT')
            assert can_edit_report(own_report, engineer_user) == True
            print("   ✓ Engineer can edit own DRAFT report")
            
            # Test Engineer can edit own PENDING report
            pending_report = MockReport('engineer@test.com', 'PENDING')
            assert can_edit_report(pending_report, engineer_user) == True
            print("   ✓ Engineer can edit own PENDING report")
            
            # Test Engineer cannot edit locked report
            locked_report = MockReport('engineer@test.com', 'DRAFT', locked=True)
            assert can_edit_report(locked_report, engineer_user) == False
            print("   ✓ Engineer cannot edit locked report")
            
            # Test Engineer cannot edit others' reports
            others_report = MockReport('other@test.com', 'DRAFT')
            assert can_edit_report(others_report, engineer_user) == False
            print("   ✓ Engineer cannot edit others' reports")
            
            # Test Engineer cannot edit APPROVED report
            approved_report = MockReport('engineer@test.com', 'APPROVED')
            assert can_edit_report(approved_report, engineer_user) == False
            print("   ✓ Engineer cannot edit APPROVED report")
            
        except Exception as e:
            print(f"   ✗ Permission check error: {e}")
        
        print("\n✅ Edit functionality tests completed!")
        print("\nNext steps to verify in browser:")
        print("1. Login as an Engineer user")
        print("2. Create a new SAT report (it will be in DRAFT status)")
        print("3. Go to 'My Reports' page")
        print("4. Verify that the Edit button appears for DRAFT reports")
        print("5. Click Edit and verify the form loads with existing data")
        print("6. Make changes and save")
        print("7. Verify changes are saved successfully")

if __name__ == "__main__":
    test_routes()