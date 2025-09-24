#!/usr/bin/env python3
"""
Focused test to verify the core logout security fix
Tests that sessions are properly revoked after logout and old cookies cannot be reused
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:5000"

def test_core_logout_security():
    """Test the core security requirement: sessions are invalidated after logout"""
    print("=" * 60)
    print("TESTING CORE LOGOUT SECURITY FIX")
    print("=" * 60)
    
    # Create a session to maintain cookies
    session = requests.Session()
    
    print("\n1. Initial state - should be unauthenticated")
    resp = session.get(f"{BASE_URL}/api/check-auth")
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json() if resp.text else 'No response'}")
    assert resp.status_code == 401, "Should be unauthenticated initially"
    
    print("\n2. Login as admin")
    # Get login page for CSRF
    session.get(f"{BASE_URL}/auth/login")
    
    # Login
    login_data = {
        "email": "admin@cullyautomation.com",
        "password": "admin123"
    }
    resp = session.post(f"{BASE_URL}/auth/login", data=login_data, allow_redirects=False)
    print(f"   Login status: {resp.status_code}")
    assert resp.status_code in [302, 303], "Login should redirect"
    
    # Save cookies immediately after login
    cookies_after_login = dict(session.cookies)
    print(f"   Cookies after login: {list(cookies_after_login.keys())}")
    
    print("\n3. Logout")
    resp = session.get(f"{BASE_URL}/auth/logout", allow_redirects=False)
    print(f"   Logout status: {resp.status_code}")
    assert resp.status_code in [302, 303], "Logout should redirect"
    
    print("\n4. Check authentication after logout (same session)")
    resp = session.get(f"{BASE_URL}/api/check-auth")
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json() if resp.text else 'No response'}")
    assert resp.status_code == 401, "Should be unauthenticated after logout"
    
    print("\n5. Try to use old cookies in a new session")
    new_session = requests.Session()
    new_session.cookies.update(cookies_after_login)
    print(f"   Using old cookies: {list(cookies_after_login.keys())}")
    
    resp = new_session.get(f"{BASE_URL}/api/check-auth")
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.json() if resp.text else 'No response'}")
    assert resp.status_code == 401, "Old cookies should be rejected"
    
    print("\n6. Wait and retry with old cookies (test persistence)")
    time.sleep(3)
    resp = new_session.get(f"{BASE_URL}/api/check-auth")
    print(f"   Status after wait: {resp.status_code}")
    print(f"   Response: {resp.json() if resp.text else 'No response'}")
    assert resp.status_code == 401, "Old cookies should remain invalid"
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS: CORE SECURITY FIX IS WORKING!")
    print("=" * 60)
    print("\nVerified:")
    print("✅ Sessions are invalidated after logout")
    print("✅ Old cookies cannot be reused after logout")
    print("✅ Session revocation is persistent")
    print("\nThe logout session persistence vulnerability is FIXED!")
    
    return True

if __name__ == "__main__":
    try:
        success = test_core_logout_security()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)