"""
Configuration and fixtures for end-to-end tests.
"""
import pytest
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from models import db, User
from tests.factories import UserFactory, AdminUserFactory


@pytest.fixture(scope='session')
def selenium_driver():
    """Create Selenium WebDriver for E2E tests."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Try to create Chrome driver
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception:
        # Fallback to Firefox if Chrome not available
        try:
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            firefox_options = FirefoxOptions()
            firefox_options.add_argument('--headless')
            driver = webdriver.Firefox(options=firefox_options)
        except Exception:
            pytest.skip("No suitable WebDriver found (Chrome or Firefox)")
    
    driver.implicitly_wait(10)
    yield driver
    driver.quit()


@pytest.fixture(scope='function')
def live_server(app):
    """Start live server for E2E tests."""
    import threading
    import socket
    from werkzeug.serving import make_server
    
    # Find available port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    
    # Create server
    server = make_server('localhost', port, app, threaded=True)
    
    # Start server in thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    # Wait for server to start
    time.sleep(1)
    
    base_url = f'http://localhost:{port}'
    
    yield base_url
    
    # Shutdown server
    server.shutdown()


@pytest.fixture
def e2e_admin_user(db_session):
    """Create admin user for E2E tests."""
    user = AdminUserFactory(
        email='e2e_admin@test.com',
        full_name='E2E Admin User'
    )
    user.set_password('e2e_admin_password')
    db_session.commit()
    return user


@pytest.fixture
def e2e_engineer_user(db_session):
    """Create engineer user for E2E tests."""
    user = UserFactory(
        email='e2e_engineer@test.com',
        full_name='E2E Engineer User',
        role='Engineer',
        status='Active'
    )
    user.set_password('e2e_engineer_password')
    db_session.commit()
    return user


@pytest.fixture
def e2e_pm_user(db_session):
    """Create PM user for E2E tests."""
    user = UserFactory(
        email='e2e_pm@test.com',
        full_name='E2E PM User',
        role='PM',
        status='Active'
    )
    user.set_password('e2e_pm_password')
    db_session.commit()
    return user


class E2ETestHelper:
    """Helper class for E2E test operations."""
    
    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url
        self.wait = WebDriverWait(driver, 10)
    
    def navigate_to(self, path=''):
        """Navigate to a specific path."""
        url = f"{self.base_url}{path}"
        self.driver.get(url)
        return self
    
    def login(self, email, password):
        """Perform login operation."""
        # Navigate to login page
        self.navigate_to('/auth/login')
        
        # Wait for login form
        email_field = self.wait.until(
            EC.presence_of_element_located((By.NAME, 'email'))
        )
        password_field = self.driver.find_element(By.NAME, 'password')
        submit_button = self.driver.find_element(By.CSS_SELECTOR, 'input[type="submit"], button[type="submit"]')
        
        # Fill and submit form
        email_field.clear()
        email_field.send_keys(email)
        password_field.clear()
        password_field.send_keys(password)
        submit_button.click()
        
        # Wait for redirect (login success) or error message
        try:
            self.wait.until(
                EC.any_of(
                    EC.url_contains('/dashboard'),
                    EC.presence_of_element_located((By.CLASS_NAME, 'error')),
                    EC.presence_of_element_located((By.CLASS_NAME, 'alert-danger'))
                )
            )
        except TimeoutException:
            pass
        
        return self
    
    def logout(self):
        """Perform logout operation."""
        try:
            logout_link = self.wait.until(
                EC.element_to_be_clickable((By.LINK_TEXT, 'Logout'))
            )
            logout_link.click()
            
            # Wait for redirect to welcome/login page
            self.wait.until(
                EC.any_of(
                    EC.url_contains('/auth/welcome'),
                    EC.url_contains('/auth/login')
                )
            )
        except TimeoutException:
            # Try alternative logout methods
            try:
                self.navigate_to('/auth/logout')
            except:
                pass
        
        return self
    
    def wait_for_element(self, locator, timeout=10):
        """Wait for element to be present."""
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.presence_of_element_located(locator))
    
    def wait_for_clickable(self, locator, timeout=10):
        """Wait for element to be clickable."""
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(EC.element_to_be_clickable(locator))
    
    def fill_form_field(self, name, value):
        """Fill a form field by name."""
        field = self.driver.find_element(By.NAME, name)
        field.clear()
        field.send_keys(value)
        return self
    
    def select_dropdown_option(self, select_name, option_text):
        """Select option from dropdown."""
        from selenium.webdriver.support.ui import Select
        select_element = self.driver.find_element(By.NAME, select_name)
        select = Select(select_element)
        select.select_by_visible_text(option_text)
        return self
    
    def click_button(self, text=None, css_selector=None):
        """Click button by text or CSS selector."""
        if text:
            button = self.wait_for_clickable((By.XPATH, f"//button[contains(text(), '{text}')]"))
        elif css_selector:
            button = self.wait_for_clickable((By.CSS_SELECTOR, css_selector))
        else:
            raise ValueError("Must provide either text or css_selector")
        
        button.click()
        return self
    
    def assert_page_contains(self, text):
        """Assert that page contains specific text."""
        assert text in self.driver.page_source
        return self
    
    def assert_current_url_contains(self, path):
        """Assert that current URL contains specific path."""
        assert path in self.driver.current_url
        return self
    
    def assert_element_present(self, locator):
        """Assert that element is present on page."""
        element = self.wait_for_element(locator)
        assert element is not None
        return self
    
    def assert_element_not_present(self, locator, timeout=5):
        """Assert that element is not present on page."""
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.presence_of_element_located(locator))
            assert False, f"Element {locator} should not be present"
        except TimeoutException:
            # Element not found, which is what we want
            pass
        return self
    
    def take_screenshot(self, filename):
        """Take screenshot for debugging."""
        screenshot_dir = 'test_screenshots'
        os.makedirs(screenshot_dir, exist_ok=True)
        filepath = os.path.join(screenshot_dir, filename)
        self.driver.save_screenshot(filepath)
        return self


@pytest.fixture
def e2e_helper(selenium_driver, live_server):
    """Create E2E test helper."""
    return E2ETestHelper(selenium_driver, live_server)