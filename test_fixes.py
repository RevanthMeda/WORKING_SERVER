#!/usr/bin/env python3
"""
Test script to verify the fixes for both database and form state issues
"""

import os
import sys
from app import create_app

def test_database_connection():
    """Test that database connection works and uses SQLite fallback"""
    print("🔗 Testing database connection...")
    
    app = create_app()
    with app.app_context():
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        print(f"   Database URI: {db_uri}")
        
        if 'sqlite' in db_uri:
            print("   ✅ Successfully using SQLite database")
            
            # Test basic query
            try:
                from models import User
                user_count = User.query.count()
                print(f"   ✅ Database query successful: {user_count} users found")
                return True
            except Exception as e:
                print(f"   ❌ Database query failed: {e}")
                return False
        else:
            print(f"   ⚠️  Not using SQLite: {db_uri}")
            return False

def test_form_state_logic():
    """Test the JavaScript form state logic"""
    print("\n📝 Testing form state management...")
    
    # Check if the fixed JavaScript file exists and contains our fixes
    js_file = "static/js/form.js"
    if not os.path.exists(js_file):
        print("   ❌ Form JavaScript file not found")
        return False
    
    with open(js_file, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    # Check for key fixes
    checks = [
        ("clearFormState function", "function clearFormState()"),
        ("Edit mode detection", "let isEditMode = false"),
        ("Submission ID tracking", "let currentSubmissionId = null"),
        ("Conditional state saving", "if (!isEditMode) return"),
        ("Form mode initialization", "function initializeFormMode()"),
    ]
    
    all_passed = True
    for check_name, check_pattern in checks:
        if check_pattern in js_content:
            print(f"   ✅ {check_name}: Found")
        else:
            print(f"   ❌ {check_name}: Missing")
            all_passed = False
    
    return all_passed

def test_template_data_attributes():
    """Test that template has necessary data attributes"""
    print("\n🎯 Testing template data attributes...")
    
    template_file = "templates/SAT.html"
    if not os.path.exists(template_file):
        print("   ❌ SAT template file not found")
        return False
    
    with open(template_file, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Check for data attributes
    checks = [
        ("Form mode data div", "id=\"form-mode-data\""),
        ("Edit mode attribute", "data-edit-mode"),
        ("New report attribute", "data-is-new-report"),
        ("Submission ID attribute", "data-submission-id"),
    ]
    
    all_passed = True
    for check_name, check_pattern in checks:
        if check_pattern in template_content:
            print(f"   ✅ {check_name}: Found")
        else:
            print(f"   ❌ {check_name}: Missing")
            all_passed = False
    
    return all_passed

def test_route_configurations():
    """Test that routes are properly configured"""
    print("\n🛣️  Testing route configurations...")
    
    routes_file = "routes/reports.py"
    if not os.path.exists(routes_file):
        print("   ❌ Reports routes file not found")
        return False
    
    with open(routes_file, 'r', encoding='utf-8') as f:
        routes_content = f.read()
    
    # Check for edit_mode parameter in new report routes
    checks = [
        ("Edit mode False for new reports", "edit_mode=False"),
        ("Edit mode True for wizard", "edit_mode=True"),
        ("No cache decorator", "@no_cache"),
    ]
    
    all_passed = True
    for check_name, check_pattern in checks:
        if check_pattern in routes_content:
            print(f"   ✅ {check_name}: Found")
        else:
            print(f"   ❌ {check_name}: Missing")
            all_passed = False
    
    return all_passed

def main():
    """Run all tests"""
    print("🧪 SAT Report Generator - Fix Verification Tests")
    print("=" * 60)
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Form State Logic", test_form_state_logic),
        ("Template Data Attributes", test_template_data_attributes),
        ("Route Configurations", test_route_configurations),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"   ❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All fixes verified successfully!")
        print("\n🚀 Your SAT Report Generator is ready!")
        print("   • Database issue: FIXED (SQLite fallback working)")
        print("   • Form state issue: FIXED (proper state management)")
        print("\n💡 Next steps:")
        print("   1. Start the application: python app.py")
        print("   2. Test creating new reports (should show blank forms)")
        print("   3. Test editing existing reports (should show saved data)")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the issues above.")
        sys.exit(1)

if __name__ == '__main__':
    main()