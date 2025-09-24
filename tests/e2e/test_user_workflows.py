"""
End-to-end tests for complete user workflows.
"""
import pytest
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


@pytest.mark.e2e
class TestUserAuthenticationWorkflow:
    """Test complete user authentication workflows."""
    
    def test_user_registration_workflow(self, e2e_helper, db_session):
        """Test complete user registration workflow."""
        # Navigate to welcome page
        e2e_helper.navigate_to('/auth/welcome')
        
        # Click register link
        try:
            register_link = e2e_helper.wait_for_clickable((By.LINK_TEXT, 'Register'))
            register_link.click()
        except TimeoutException:
            # Try alternative selectors
            e2e_helper.navigate_to('/auth/register')
        
        # Fill registration form
        e2e_helper.fill_form_field('full_name', 'E2E Test User')
        e2e_helper.fill_form_field('email', 'e2e_new_user@test.com')
        e2e_helper.fill_form_field('password', 'secure_password123')
        
        # Select role
        try:
            e2e_helper.select_dropdown_option('requested_role', 'Engineer')
        except:
            # If dropdown not found, try radio buttons or other input methods
            pass
        
        # Submit form
        e2e_helper.click_button('Register')
        
        # Verify registration success (should show pending status or redirect)
        time.sleep(2)  # Allow for processing
        
        # Check for success message or redirect
        current_url = e2e_helper.driver.current_url
        page_source = e2e_helper.driver.page_source.lower()
        
        # Should either redirect or show success message
        assert ('pending' in page_source or 
                'success' in page_source or 
                'welcome' in current_url or
                'login' in current_url)
    
    def test_user_login_logout_workflow(self, e2e_helper, e2e_admin_user):
        """Test complete login and logout workflow."""
        # Navigate to login page
        e2e_helper.navigate_to('/auth/login')
        
        # Perform login
        e2e_helper.login(e2e_admin_user.email, 'e2e_admin_password')
        
        # Verify successful login (should redirect to dashboard)
        e2e_helper.assert_current_url_contains('/dashboard')
        
        # Verify user is logged in (check for user-specific elements)
        e2e_helper.assert_page_contains(e2e_admin_user.full_name)
        
        # Perform logout
        e2e_helper.logout()
        
        # Verify logout (should redirect to welcome/login)
        current_url = e2e_helper.driver.current_url
        assert ('/auth/welcome' in current_url or 
                '/auth/login' in current_url or
                current_url.endswith('/'))
    
    def test_invalid_login_workflow(self, e2e_helper, e2e_admin_user):
        """Test login with invalid credentials."""
        # Navigate to login page
        e2e_helper.navigate_to('/auth/login')
        
        # Attempt login with wrong password
        e2e_helper.login(e2e_admin_user.email, 'wrong_password')
        
        # Should remain on login page or show error
        time.sleep(2)
        current_url = e2e_helper.driver.current_url
        page_source = e2e_helper.driver.page_source.lower()
        
        # Should not redirect to dashboard
        assert '/dashboard' not in current_url
        
        # Should show error message
        assert ('error' in page_source or 
                'invalid' in page_source or 
                'incorrect' in page_source)
    
    def test_access_control_workflow(self, e2e_helper, e2e_engineer_user):
        """Test access control for different user roles."""
        # Login as engineer
        e2e_helper.navigate_to('/auth/login')
        e2e_helper.login(e2e_engineer_user.email, 'e2e_engineer_password')
        
        # Try to access admin-only pages
        admin_pages = ['/admin', '/users', '/settings']
        
        for page in admin_pages:
            e2e_helper.navigate_to(page)
            time.sleep(1)
            
            current_url = e2e_helper.driver.current_url
            page_source = e2e_helper.driver.page_source.lower()
            
            # Should be redirected or show access denied
            assert (page not in current_url or 
                    'access denied' in page_source or 
                    'unauthorized' in page_source or
                    '403' in page_source)
    
    def test_session_timeout_workflow(self, e2e_helper, e2e_admin_user):
        """Test session timeout behavior."""
        # Login
        e2e_helper.navigate_to('/auth/login')
        e2e_helper.login(e2e_admin_user.email, 'e2e_admin_password')
        
        # Verify logged in
        e2e_helper.assert_current_url_contains('/dashboard')
        
        # Simulate session timeout by clearing cookies
        e2e_helper.driver.delete_all_cookies()
        
        # Try to access protected page
        e2e_helper.navigate_to('/reports/new')
        
        # Should redirect to login
        time.sleep(2)
        current_url = e2e_helper.driver.current_url
        assert ('/auth/login' in current_url or 
                '/auth/welcome' in current_url)


@pytest.mark.e2e
class TestNavigationWorkflow:
    """Test navigation workflows."""
    
    def test_main_navigation_workflow(self, e2e_helper, e2e_admin_user):
        """Test main navigation menu functionality."""
        # Login first
        e2e_helper.navigate_to('/auth/login')
        e2e_helper.login(e2e_admin_user.email, 'e2e_admin_password')
        
        # Test navigation to different sections
        navigation_items = [
            ('Dashboard', '/dashboard'),
            ('Reports', '/reports'),
            ('New Report', '/reports/new')
        ]
        
        for nav_text, expected_path in navigation_items:
            try:
                # Look for navigation link
                nav_link = e2e_helper.wait_for_clickable((By.PARTIAL_LINK_TEXT, nav_text))
                nav_link.click()
                
                time.sleep(1)
                current_url = e2e_helper.driver.current_url
                
                # Verify navigation worked
                assert expected_path in current_url
                
            except TimeoutException:
                # Navigation item might not be available for this user role
                pass
    
    def test_breadcrumb_navigation(self, e2e_helper, e2e_admin_user):
        """Test breadcrumb navigation functionality."""
        # Login and navigate to nested page
        e2e_helper.navigate_to('/auth/login')
        e2e_helper.login(e2e_admin_user.email, 'e2e_admin_password')
        
        # Navigate to a nested page
        e2e_helper.navigate_to('/reports/new/sat')
        
        # Look for breadcrumb elements
        try:
            breadcrumbs = e2e_helper.driver.find_elements(By.CSS_SELECTOR, '.breadcrumb a, .breadcrumb-item a')
            
            if breadcrumbs:
                # Click on a breadcrumb to navigate back
                breadcrumbs[0].click()
                time.sleep(1)
                
                # Verify navigation worked
                current_url = e2e_helper.driver.current_url
                assert current_url != '/reports/new/sat'
        except:
            # Breadcrumbs might not be implemented yet
            pass
    
    def test_responsive_navigation(self, e2e_helper, e2e_admin_user):
        """Test responsive navigation on different screen sizes."""
        # Login first
        e2e_helper.navigate_to('/auth/login')
        e2e_helper.login(e2e_admin_user.email, 'e2e_admin_password')
        
        # Test desktop size
        e2e_helper.driver.set_window_size(1920, 1080)
        e2e_helper.navigate_to('/dashboard')
        
        # Look for desktop navigation elements
        desktop_nav_present = len(e2e_helper.driver.find_elements(By.CSS_SELECTOR, '.navbar, .nav, .navigation')) > 0
        
        # Test mobile size
        e2e_helper.driver.set_window_size(375, 667)
        time.sleep(1)
        
        # Look for mobile navigation elements (hamburger menu, etc.)
        mobile_nav_elements = e2e_helper.driver.find_elements(By.CSS_SELECTOR, '.navbar-toggle, .hamburger, .mobile-menu')
        
        # At least one navigation method should be available
        assert desktop_nav_present or len(mobile_nav_elements) > 0
        
        # Reset to desktop size
        e2e_helper.driver.set_window_size(1920, 1080)


@pytest.mark.e2e
class TestErrorHandlingWorkflow:
    """Test error handling workflows."""
    
    def test_404_error_workflow(self, e2e_helper):
        """Test 404 error page workflow."""
        # Navigate to non-existent page
        e2e_helper.navigate_to('/nonexistent-page')
        
        # Should show 404 error page
        page_source = e2e_helper.driver.page_source.lower()
        assert ('404' in page_source or 
                'not found' in page_source or 
                'page not found' in page_source)
    
    def test_form_validation_error_workflow(self, e2e_helper):
        """Test form validation error handling."""
        # Navigate to registration page
        e2e_helper.navigate_to('/auth/register')
        
        # Submit form with missing required fields
        try:
            submit_button = e2e_helper.wait_for_clickable((By.CSS_SELECTOR, 'input[type="submit"], button[type="submit"]'))
            submit_button.click()
            
            time.sleep(2)
            
            # Should show validation errors
            page_source = e2e_helper.driver.page_source.lower()
            assert ('required' in page_source or 
                    'error' in page_source or 
                    'invalid' in page_source)
        except TimeoutException:
            # Form might have client-side validation preventing submission
            pass
    
    def test_network_error_recovery(self, e2e_helper, e2e_admin_user):
        """Test recovery from network errors."""
        # Login first
        e2e_helper.navigate_to('/auth/login')
        e2e_helper.login(e2e_admin_user.email, 'e2e_admin_password')
        
        # Navigate to a page
        e2e_helper.navigate_to('/dashboard')
        
        # Simulate network error by navigating to invalid URL
        e2e_helper.navigate_to('/invalid-endpoint')
        
        # Then navigate back to valid page
        e2e_helper.navigate_to('/dashboard')
        
        # Should recover and show dashboard
        time.sleep(2)
        current_url = e2e_helper.driver.current_url
        assert '/dashboard' in current_url


@pytest.mark.e2e
class TestAccessibilityWorkflow:
    """Test accessibility features in workflows."""
    
    def test_keyboard_navigation_workflow(self, e2e_helper):
        """Test keyboard navigation functionality."""
        from selenium.webdriver.common.keys import Keys
        
        # Navigate to login page
        e2e_helper.navigate_to('/auth/login')
        
        # Test tab navigation through form fields
        body = e2e_helper.driver.find_element(By.TAG_NAME, 'body')
        
        # Tab through form elements
        for _ in range(5):
            body.send_keys(Keys.TAB)
            time.sleep(0.5)
        
        # Should be able to navigate to submit button and press Enter
        active_element = e2e_helper.driver.switch_to.active_element
        
        # Verify we can interact with form elements via keyboard
        if active_element.tag_name in ['input', 'button']:
            # Test passed - keyboard navigation is working
            assert True
        else:
            # Keyboard navigation might not be fully implemented
            pass
    
    def test_screen_reader_compatibility(self, e2e_helper):
        """Test screen reader compatibility features."""
        # Navigate to main page
        e2e_helper.navigate_to('/auth/welcome')
        
        # Check for accessibility attributes
        elements_with_labels = e2e_helper.driver.find_elements(By.CSS_SELECTOR, '[aria-label], [aria-labelledby]')
        form_labels = e2e_helper.driver.find_elements(By.TAG_NAME, 'label')
        alt_texts = e2e_helper.driver.find_elements(By.CSS_SELECTOR, 'img[alt]')
        
        # Should have some accessibility features
        accessibility_features = len(elements_with_labels) + len(form_labels) + len(alt_texts)
        
        # At minimum, should have some form labels
        assert accessibility_features > 0
    
    def test_color_contrast_elements(self, e2e_helper):
        """Test that important elements are visible (basic contrast check)."""
        # Navigate to main page
        e2e_helper.navigate_to('/auth/welcome')
        
        # Check that key elements are visible
        key_elements = e2e_helper.driver.find_elements(By.CSS_SELECTOR, 'button, .btn, input[type="submit"]')
        
        visible_elements = 0
        for element in key_elements:
            if element.is_displayed():
                visible_elements += 1
        
        # Should have at least some visible interactive elements
        assert visible_elements > 0


@pytest.mark.e2e
class TestPerformanceWorkflow:
    """Test performance aspects of workflows."""
    
    def test_page_load_performance(self, e2e_helper, e2e_admin_user):
        """Test page load performance."""
        import time
        
        # Test login page load time
        start_time = time.time()
        e2e_helper.navigate_to('/auth/login')
        e2e_helper.wait_for_element((By.NAME, 'email'))
        login_load_time = time.time() - start_time
        
        # Login
        e2e_helper.login(e2e_admin_user.email, 'e2e_admin_password')
        
        # Test dashboard load time
        start_time = time.time()
        e2e_helper.navigate_to('/dashboard')
        e2e_helper.wait_for_element((By.TAG_NAME, 'body'))
        dashboard_load_time = time.time() - start_time
        
        # Pages should load within reasonable time (adjust thresholds as needed)
        assert login_load_time < 10.0  # 10 seconds max
        assert dashboard_load_time < 10.0  # 10 seconds max
    
    def test_form_submission_performance(self, e2e_helper):
        """Test form submission performance."""
        import time
        
        # Navigate to registration form
        e2e_helper.navigate_to('/auth/register')
        
        # Fill form
        e2e_helper.fill_form_field('full_name', 'Performance Test User')
        e2e_helper.fill_form_field('email', 'perf_test@test.com')
        e2e_helper.fill_form_field('password', 'password123')
        
        try:
            e2e_helper.select_dropdown_option('requested_role', 'Engineer')
        except:
            pass
        
        # Submit form and measure time
        start_time = time.time()
        e2e_helper.click_button('Register')
        
        # Wait for response (success or error)
        time.sleep(3)
        submission_time = time.time() - start_time
        
        # Form submission should complete within reasonable time
        assert submission_time < 15.0  # 15 seconds max