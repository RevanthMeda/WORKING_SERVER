#!/usr/bin/env python3
"""
Test script to verify logout session invalidation security fix
Tests that sessions are properly revoked after logout
"""

import requests
import json
import time
import sys

# Base URL for the application
BASE_URL = "http://localhost:5000"

def print_result(test_name, passed):
    """Print test result with color"""
    if passed:
        print(f"✅ {test_name}: PASSED")
    else:
        print(f"❌ {test_name}: FAILED")
    return passed

def test_logout_security():
    """Test complete logout security flow"""
    print("=" * 60)
    print("TESTING LOGOUT SESSION INVALIDATION SECURITY FIX")
    print("=" * 60)
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    # Test 1: Check initial unauthenticated state
    print("\n1. Testing initial unauthenticated state...")
    resp = session.get(f"{BASE_URL}/api/check-auth")
    test1 = print_result("Initial state is unauthenticated", resp.status_code == 401)
    
    # Test 2: Login as admin
    print("\n2. Testing login...")
    login_data = {
        "email": "admin@cullyautomation.com",
        "password": "admin123"
    }
    
    # Get CSRF token first
    resp = session.get(f"{BASE_URL}/auth/login")
    
    # Login
    resp = session.post(f"{BASE_URL}/auth/login", data=login_data, allow_redirects=False)
    test2 = print_result("Login successful", resp.status_code in [302, 303])
    
    if not test2:
        print(f"Login response: {resp.status_code}, {resp.text[:200]}")
        
    # Test 3: Check authenticated state after login
    print("\n3. Testing authenticated state after login...")
    resp = session.get(f"{BASE_URL}/api/check-auth")
    test3 = print_result("Authenticated after login", resp.status_code == 200)
    if test3:
        auth_data = resp.json()
        print(f"   Auth data: {auth_data}")
    else:
        print(f"   Response status: {resp.status_code}")
        print(f"   Response body: {resp.text[:200] if resp.text else 'No body'}")
    
    # Save session cookies before logout
    cookies_before_logout = session.cookies.copy()
    print(f"\n   Cookies before logout: {list(cookies_before_logout.keys())}")
    
    # Test 4: Access a protected page (should work)
    print("\n4. Testing access to protected page before logout...")
    resp = session.get(f"{BASE_URL}/dashboard/admin", allow_redirects=False)
    test4 = print_result("Can access protected page before logout", resp.status_code == 200)
    
    # Test 5: Logout
    print("\n5. Testing logout...")
    resp = session.get(f"{BASE_URL}/auth/logout", allow_redirects=False)
    test5 = print_result("Logout successful", resp.status_code in [302, 303])
    
    # Test 6: Check unauthenticated state after logout
    print("\n6. Testing authentication state after logout...")
    resp = session.get(f"{BASE_URL}/api/check-auth")
    test6 = print_result("Unauthenticated after logout", resp.status_code == 401)
    if resp.status_code == 200:
        print(f"   ERROR: Still authenticated! Response: {resp.json()}")
    else:
        print(f"   Good: Authentication properly denied")
        print(f"   Response: {resp.json() if resp.text else 'No response body'}")
    
    # Test 7: Try to access protected page after logout (should fail)
    print("\n7. Testing access to protected page after logout...")
    resp = session.get(f"{BASE_URL}/dashboard/admin", allow_redirects=False)
    test7 = print_result("Cannot access protected page after logout", resp.status_code in [302, 303, 401])
    if resp.status_code == 200:
        print(f"   ERROR: Still able to access protected page!")
    
    # Test 8: Try using old cookies directly
    print("\n8. Testing with old session cookies...")
    new_session = requests.Session()
    new_session.cookies.update(cookies_before_logout)
    resp = new_session.get(f"{BASE_URL}/api/check-auth")
    test8 = print_result("Old cookies are invalid", resp.status_code == 401)
    if resp.status_code == 200:
        print(f"   ERROR: Old cookies still valid! Response: {resp.json()}")
    
    # Test 9: Try accessing protected page with old cookies
    print("\n9. Testing protected page access with old cookies...")
    resp = new_session.get(f"{BASE_URL}/dashboard/admin", allow_redirects=False)
    test9 = print_result("Old cookies cannot access protected pages", resp.status_code in [302, 303, 401])
    if resp.status_code == 200:
        print(f"   ERROR: Old cookies can still access protected pages!")
    
    # Test 10: Verify session is truly revoked (wait and retry)
    print("\n10. Testing session revocation persistence...")
    time.sleep(2)
    resp = new_session.get(f"{BASE_URL}/api/check-auth")
    test10 = print_result("Session remains revoked after time", resp.status_code == 401)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_tests = [test1, test2, test3, test4, test5, test6, test7, test8, test9, test10]
    passed = sum(all_tests)
    total = len(all_tests)
    
    print(f"\nPassed: {passed}/{total} tests")
    
    if passed == total:
        print("\n🎉 SUCCESS: All security tests passed!")
        print("✅ Logout properly invalidates sessions")
        print("✅ Old cookies are rejected")
        print("✅ Protected pages are inaccessible after logout")
        return True
    else:
        print("\n⚠️  WARNING: Some security tests failed!")
        print("❌ Session invalidation may not be working correctly")
        return False

if __name__ == "__main__":
    try:
        success = test_logout_security()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)