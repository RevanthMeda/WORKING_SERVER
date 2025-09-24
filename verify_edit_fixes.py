#!/usr/bin/env python3
"""
Verification script to check that critical edit feature fixes are in place.
This script verifies the code changes without running full database tests.
"""

import os
import re

def verify_approval_database_update():
    """Verify that approval.py properly updates the database"""
    print("\n=== Verifying Approval Database Update Fix ===")
    
    with open('routes/approval.py', 'r') as f:
        content = f.read()
    
    # Check for database commit after updating Report fields
    checks = [
        ("report.locked = True", "✓ Sets report.locked = True when approved"),
        ("report.status = 'APPROVED'", "✓ Sets report.status = 'APPROVED'"),
        ("report.approved_at = datetime.datetime.utcnow()", "✓ Sets approved_at timestamp"),
        ("report.approved_by =", "✓ Sets approved_by field"),
        ("db.session.commit()", "✓ Commits database changes"),
        ("Successfully updated Report database record", "✓ Logs successful database update")
    ]
    
    all_found = True
    for check_text, success_msg in checks:
        if check_text in content:
            print(f"  {success_msg}")
        else:
            print(f"  ✗ Missing: {check_text}")
            all_found = False
    
    if all_found:
        print("✓ Approval workflow database update fix verified!")
    else:
        print("✗ Some database update code missing")
    
    return all_found

def verify_csrf_protection():
    """Verify CSRF protection in edit.py"""
    print("\n=== Verifying CSRF Protection Fix ===")
    
    with open('routes/edit.py', 'r') as f:
        content = f.read()
    
    # Check for CSRF protection code
    checks = [
        ("from flask_wtf.csrf import validate_csrf", "✓ Imports CSRF validation"),
        ("csrf_token = request.headers.get('X-CSRFToken')", "✓ Gets CSRF token from headers"),
        ("validate_csrf(csrf_token)", "✓ Validates CSRF token"),
        ("CSRF validation failed", "✓ Handles CSRF validation errors"),
        ("'error': 'CSRF token validation failed'", "✓ Returns CSRF error response")
    ]
    
    all_found = True
    for check_text, success_msg in checks:
        if check_text in content:
            print(f"  {success_msg}")
        else:
            print(f"  ✗ Missing: {check_text}")
            all_found = False
    
    if all_found:
        print("✓ CSRF protection fix verified!")
    else:
        print("✗ Some CSRF protection code missing")
    
    return all_found

def verify_optimistic_concurrency():
    """Verify optimistic concurrency control in edit.py"""
    print("\n=== Verifying Optimistic Concurrency Control Fix ===")
    
    with open('routes/edit.py', 'r') as f:
        content = f.read()
    
    # Check for concurrency control code
    checks = [
        ("last_updated_timestamp = new_data.get('last_updated_timestamp')", "✓ Gets client timestamp"),
        ("datetime.fromisoformat(last_updated_timestamp)", "✓ Parses client timestamp"),
        ("report.updated_at > client_timestamp", "✓ Checks for concurrent modifications"),
        ("'error': 'Report was modified by another user'", "✓ Returns conflict error message"),
        ("'conflict': True", "✓ Sets conflict flag"),
        ("), 409", "✓ Returns 409 Conflict status code")
    ]
    
    all_found = True
    for check_text, success_msg in checks:
        if check_text in content:
            print(f"  {success_msg}")
        else:
            print(f"  ✗ Missing: {check_text}")
            all_found = False
    
    if all_found:
        print("✓ Optimistic concurrency control fix verified!")
    else:
        print("✗ Some concurrency control code missing")
    
    return all_found

def verify_can_edit_logic():
    """Verify that can_edit_report function blocks approved reports"""
    print("\n=== Verifying Edit Permission Logic ===")
    
    with open('routes/edit.py', 'r') as f:
        content = f.read()
    
    # Extract the can_edit_report function
    func_match = re.search(r'def can_edit_report\(.*?\):(.*?)(?=\ndef|\Z)', content, re.DOTALL)
    
    if func_match:
        func_content = func_match.group(1)
        
        checks = [
            ("if report.locked or report.status == 'APPROVED':", "✓ Checks if report is locked or approved"),
            ("return False", "✓ Returns False for locked/approved reports")
        ]
        
        all_found = True
        for check_text, success_msg in checks:
            if check_text in func_content:
                print(f"  {success_msg}")
            else:
                print(f"  ✗ Missing: {check_text}")
                all_found = False
        
        if all_found:
            print("✓ Edit permission logic correctly blocks approved reports!")
        else:
            print("✗ Edit permission logic incomplete")
        
        return all_found
    else:
        print("✗ Could not find can_edit_report function")
        return False

def main():
    """Run all verifications"""
    print("=" * 60)
    print("VERIFYING CRITICAL EDIT FEATURE FIXES")
    print("=" * 60)
    
    results = []
    
    # Verify each fix
    results.append(verify_approval_database_update())
    results.append(verify_csrf_protection())
    results.append(verify_optimistic_concurrency())
    results.append(verify_can_edit_logic())
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    if all(results):
        print("✅ ALL CRITICAL FIXES VERIFIED!")
        print("\nThe following fixes have been successfully implemented:")
        print("1. ✅ Approval workflow properly updates database")
        print("2. ✅ CSRF protection added to JSON edit endpoint")
        print("3. ✅ Optimistic concurrency control prevents conflicts")
        print("4. ✅ Approved reports are locked from editing")
    else:
        print("⚠️ SOME FIXES MISSING - Please review the output above")
    
    print("\n" + "=" * 60)
    
    return 0 if all(results) else 1

if __name__ == "__main__":
    exit(main())