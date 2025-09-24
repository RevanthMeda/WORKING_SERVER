"""
Locust performance testing configuration for SAT Report Generator.
"""
import random
import json
from locust import HttpUser, task, between
from locust.exception import StopUser


class SATReportUser(HttpUser):
    """Simulates a user interacting with the SAT Report Generator."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts. Perform login."""
        self.login()
    
    def login(self):
        """Login with test credentials."""
        # Get login page first to get CSRF token
        response = self.client.get("/auth/login")
        
        if response.status_code != 200:
            print(f"Failed to get login page: {response.status_code}")
            raise StopUser()
        
        # Extract CSRF token if present
        csrf_token = None
        if 'csrf_token' in response.text:
            # Simple extraction - in real scenario might need more robust parsing
            import re
            match = re.search(r'name="csrf_token".*?value="([^"]+)"', response.text)
            if match:
                csrf_token = match.group(1)
        
        # Login with test user credentials
        login_data = {
            'email': 'perf_test@example.com',
            'password': 'performance_test_password'
        }
        
        if csrf_token:
            login_data['csrf_token'] = csrf_token
        
        response = self.client.post("/auth/login", data=login_data)
        
        # Check if login was successful
        if response.status_code == 200 and 'dashboard' in response.url:
            self.logged_in = True
        else:
            # Create test user if login failed
            self.create_test_user()
            self.logged_in = False
    
    def create_test_user(self):
        """Create a test user for performance testing."""
        user_data = {
            'full_name': 'Performance Test User',
            'email': 'perf_test@example.com',
            'password': 'performance_test_password',
            'requested_role': 'Engineer'
        }
        
        response = self.client.post("/auth/register", data=user_data)
        # Note: In real scenario, user would need to be activated by admin
    
    @task(3)
    def view_dashboard(self):
        """View the dashboard - most common action."""
        response = self.client.get("/dashboard")
        
        if response.status_code != 200:
            print(f"Dashboard access failed: {response.status_code}")
    
    @task(2)
    def view_reports_list(self):
        """View the reports list."""
        response = self.client.get("/reports")
        
        if response.status_code == 200:
            # Parse response to check for reports
            if 'report' in response.text.lower():
                # Reports are present
                pass
    
    @task(1)
    def create_new_report(self):
        """Create a new SAT report."""
        # Navigate to new report page
        response = self.client.get("/reports/new/sat/full")
        
        if response.status_code != 200:
            return
        
        # Extract CSRF token
        csrf_token = None
        import re
        match = re.search(r'name="csrf_token".*?value="([^"]+)"', response.text)
        if match:
            csrf_token = match.group(1)
        
        # Generate test report data
        report_data = {
            'document_title': f'Performance Test Report {random.randint(1000, 9999)}',
            'project_reference': f'PERF-{random.randint(100, 999)}',
            'document_reference': f'DOC-PERF-{random.randint(100, 999)}',
            'client_name': f'Performance Client {random.randint(1, 10)}',
            'revision': 'R0',
            'prepared_by': 'Performance Test Engineer',
            'date': '2024-01-15',
            'purpose': 'Performance testing of report creation',
            'scope': 'Load testing validation'
        }
        
        if csrf_token:
            report_data['csrf_token'] = csrf_token
        
        # Submit the report
        response = self.client.post("/reports/create", data=report_data)
        
        if response.status_code in [200, 201, 302]:
            # Report creation successful
            pass
        else:
            print(f"Report creation failed: {response.status_code}")
    
    @task(1)
    def search_reports(self):
        """Search for reports."""
        search_terms = ['test', 'SAT', 'performance', 'validation']
        search_term = random.choice(search_terms)
        
        response = self.client.get(f"/search?q={search_term}")
        
        if response.status_code == 200:
            # Search completed
            pass
    
    @task(1)
    def view_report_status(self):
        """View report status page."""
        # Generate random report ID (might not exist, but tests the endpoint)
        report_id = f"report-{random.randint(1, 100)}"
        
        response = self.client.get(f"/status/{report_id}")
        
        # Accept 404 as valid response for non-existent reports
        if response.status_code in [200, 404]:
            pass
    
    @task(1)
    def api_health_check(self):
        """Check API health endpoint."""
        response = self.client.get("/health")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('status') == 'healthy':
                    pass
            except:
                pass
    
    @task(1)
    def check_authentication_status(self):
        """Check authentication status via API."""
        response = self.client.get("/api/check-auth")
        
        if response.status_code in [200, 401]:
            # Both authenticated and unauthenticated are valid responses
            pass


class AdminUser(HttpUser):
    """Simulates an admin user with additional privileges."""
    
    wait_time = between(2, 5)
    weight = 1  # Lower weight - fewer admin users
    
    def on_start(self):
        """Login as admin user."""
        self.login_as_admin()
    
    def login_as_admin(self):
        """Login with admin credentials."""
        response = self.client.get("/auth/login")
        
        if response.status_code != 200:
            raise StopUser()
        
        # Extract CSRF token
        csrf_token = None
        import re
        match = re.search(r'name="csrf_token".*?value="([^"]+)"', response.text)
        if match:
            csrf_token = match.group(1)
        
        login_data = {
            'email': 'admin@cullyautomation.com',  # Default admin
            'password': 'admin123'
        }
        
        if csrf_token:
            login_data['csrf_token'] = csrf_token
        
        response = self.client.post("/auth/login", data=login_data)
        
        if response.status_code == 200:
            self.logged_in = True
        else:
            self.logged_in = False
            raise StopUser()
    
    @task(2)
    def view_admin_dashboard(self):
        """View admin dashboard."""
        response = self.client.get("/admin/dashboard")
        
        if response.status_code in [200, 404]:  # 404 if not implemented
            pass
    
    @task(1)
    def manage_users(self):
        """Access user management."""
        response = self.client.get("/admin/users")
        
        if response.status_code in [200, 404]:
            pass
    
    @task(1)
    def view_system_settings(self):
        """View system settings."""
        response = self.client.get("/admin/settings")
        
        if response.status_code in [200, 404]:
            pass
    
    @task(1)
    def approve_pending_reports(self):
        """Check for and approve pending reports."""
        response = self.client.get("/approve")
        
        if response.status_code == 200:
            # Look for approval opportunities in response
            if 'approve' in response.text.lower():
                # Simulate approval action
                approval_data = {
                    'action': 'approve',
                    'comment': 'Performance test approval'
                }
                
                # This would need actual report ID in real scenario
                self.client.post("/approve/submit", data=approval_data)


class APIUser(HttpUser):
    """Simulates API-only usage."""
    
    wait_time = between(0.5, 2)
    weight = 2  # Moderate weight for API users
    
    def on_start(self):
        """Setup API authentication."""
        self.api_key = "test-api-key-for-performance"
        self.headers = {"X-API-Key": self.api_key}
    
    @task(3)
    def api_get_reports(self):
        """Get reports via API."""
        response = self.client.get("/api/reports", headers=self.headers)
        
        if response.status_code in [200, 401]:  # 401 if API key invalid
            pass
    
    @task(2)
    def api_health_check(self):
        """API health check."""
        response = self.client.get("/api/health", headers=self.headers)
        
        if response.status_code == 200:
            pass
    
    @task(1)
    def api_create_report(self):
        """Create report via API."""
        report_data = {
            "type": "SAT",
            "document_title": f"API Performance Test {random.randint(1000, 9999)}",
            "project_reference": f"API-PERF-{random.randint(100, 999)}"
        }
        
        response = self.client.post("/api/reports", 
                                  json=report_data, 
                                  headers=self.headers)
        
        if response.status_code in [200, 201, 401]:
            pass
    
    @task(1)
    def api_get_users(self):
        """Get users by role via API."""
        response = self.client.get("/api/get-users-by-role", headers=self.headers)
        
        if response.status_code in [200, 401]:
            pass


class MobileUser(HttpUser):
    """Simulates mobile device usage."""
    
    wait_time = between(2, 6)  # Slower interactions on mobile
    weight = 1  # Lower weight - fewer mobile users
    
    def on_start(self):
        """Setup mobile user agent."""
        self.client.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15'
        })
        self.login_mobile()
    
    def login_mobile(self):
        """Login optimized for mobile."""
        response = self.client.get("/auth/login")
        
        if response.status_code != 200:
            raise StopUser()
        
        login_data = {
            'email': 'mobile_test@example.com',
            'password': 'mobile_test_password'
        }
        
        response = self.client.post("/auth/login", data=login_data)
        
        if response.status_code == 200:
            self.logged_in = True
        else:
            self.logged_in = False
    
    @task(3)
    def mobile_dashboard(self):
        """View dashboard on mobile."""
        response = self.client.get("/dashboard")
        
        if response.status_code == 200:
            # Check for mobile-responsive elements
            if 'viewport' in response.text or 'mobile' in response.text:
                pass
    
    @task(2)
    def mobile_view_reports(self):
        """View reports on mobile device."""
        response = self.client.get("/reports")
        
        if response.status_code == 200:
            pass
    
    @task(1)
    def mobile_quick_actions(self):
        """Perform quick actions on mobile."""
        # Simulate touch interactions with shorter wait times
        actions = ["/dashboard", "/reports", "/notifications"]
        action = random.choice(actions)
        
        response = self.client.get(action)
        
        if response.status_code == 200:
            pass


# Performance test scenarios
class StressTestUser(HttpUser):
    """High-intensity user for stress testing."""
    
    wait_time = between(0.1, 0.5)  # Very fast interactions
    weight = 1  # Use sparingly
    
    @task
    def rapid_requests(self):
        """Make rapid requests to test system limits."""
        endpoints = [
            "/health",
            "/api/check-auth", 
            "/dashboard",
            "/reports"
        ]
        
        endpoint = random.choice(endpoints)
        response = self.client.get(endpoint)
        
        # Accept any response - we're testing system stability
        if response.status_code < 500:
            pass


# Custom performance test events
from locust import events

@events.request.add_listener
def request_handler(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Custom request handler for performance monitoring."""
    if exception:
        print(f"Request failed: {name} - {exception}")
    elif response_time > 5000:  # Log slow requests (>5 seconds)
        print(f"Slow request detected: {name} - {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print("Performance test starting...")
    print(f"Target host: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("Performance test completed.")
    
    # Print summary statistics
    stats = environment.stats
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Total failures: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Max response time: {stats.total.max_response_time}ms")