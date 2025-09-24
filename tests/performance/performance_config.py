"""
Performance testing configuration and utilities.
"""
import os
import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PerformanceThresholds:
    """Performance threshold configuration."""
    
    # Response time thresholds (milliseconds)
    api_response_time_avg: float = 200.0
    api_response_time_max: float = 1000.0
    page_load_time_avg: float = 1000.0
    page_load_time_max: float = 3000.0
    
    # Throughput thresholds (requests per second)
    min_throughput: float = 50.0
    target_throughput: float = 100.0
    
    # Resource usage thresholds
    max_memory_usage_mb: float = 500.0
    max_cpu_usage_percent: float = 80.0
    
    # Database performance thresholds
    db_query_time_avg: float = 100.0
    db_query_time_max: float = 500.0
    
    # Concurrent user thresholds
    max_concurrent_users: int = 100
    target_concurrent_users: int = 50


class PerformanceMonitor:
    """Monitor and record performance metrics."""
    
    def __init__(self):
        self.metrics = []
        self.start_time = None
        self.end_time = None
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        self.metrics = []
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.end_time = time.time()
    
    def record_metric(self, name: str, value: float, unit: str = 'ms', tags: Optional[Dict] = None):
        """Record a performance metric."""
        metric = {
            'name': name,
            'value': value,
            'unit': unit,
            'timestamp': time.time(),
            'tags': tags or {}
        }
        self.metrics.append(metric)
    
    def get_metrics_summary(self) -> Dict:
        """Get summary of recorded metrics."""
        if not self.metrics:
            return {}
        
        summary = {}
        
        # Group metrics by name
        metric_groups = {}
        for metric in self.metrics:
            name = metric['name']
            if name not in metric_groups:
                metric_groups[name] = []
            metric_groups[name].append(metric['value'])
        
        # Calculate statistics for each metric
        for name, values in metric_groups.items():
            summary[name] = {
                'count': len(values),
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'total': sum(values)
            }
        
        # Add overall test duration
        if self.start_time and self.end_time:
            summary['test_duration'] = {
                'value': self.end_time - self.start_time,
                'unit': 'seconds'
            }
        
        return summary
    
    def export_metrics(self, filepath: str):
        """Export metrics to JSON file."""
        data = {
            'start_time': self.start_time,
            'end_time': self.end_time,
            'metrics': self.metrics,
            'summary': self.get_metrics_summary()
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


class LoadTestScenario:
    """Define load testing scenarios."""
    
    def __init__(self, name: str, users: int, duration: int, ramp_up: int = 0):
        self.name = name
        self.users = users
        self.duration = duration
        self.ramp_up = ramp_up
        self.tasks = []
    
    def add_task(self, endpoint: str, weight: int = 1, method: str = 'GET', data: Optional[Dict] = None):
        """Add a task to the scenario."""
        task = {
            'endpoint': endpoint,
            'weight': weight,
            'method': method,
            'data': data
        }
        self.tasks.append(task)
    
    def to_locust_config(self) -> Dict:
        """Convert to Locust configuration format."""
        return {
            'name': self.name,
            'users': self.users,
            'spawn_rate': self.users / max(self.ramp_up, 1),
            'run_time': f"{self.duration}s",
            'tasks': self.tasks
        }


# Predefined performance test scenarios
PERFORMANCE_SCENARIOS = {
    'smoke_test': LoadTestScenario(
        name='Smoke Test',
        users=5,
        duration=60,
        ramp_up=10
    ),
    
    'load_test': LoadTestScenario(
        name='Load Test',
        users=50,
        duration=300,
        ramp_up=60
    ),
    
    'stress_test': LoadTestScenario(
        name='Stress Test',
        users=100,
        duration=600,
        ramp_up=120
    ),
    
    'spike_test': LoadTestScenario(
        name='Spike Test',
        users=200,
        duration=180,
        ramp_up=30
    ),
    
    'endurance_test': LoadTestScenario(
        name='Endurance Test',
        users=30,
        duration=3600,  # 1 hour
        ramp_up=300
    )
}

# Add common tasks to scenarios
for scenario in PERFORMANCE_SCENARIOS.values():
    scenario.add_task('/health', weight=3)
    scenario.add_task('/dashboard', weight=2)
    scenario.add_task('/reports', weight=2)
    scenario.add_task('/api/check-auth', weight=1)


class PerformanceTestRunner:
    """Run and manage performance tests."""
    
    def __init__(self, base_url: str = 'http://localhost:5000'):
        self.base_url = base_url
        self.monitor = PerformanceMonitor()
        self.thresholds = PerformanceThresholds()
    
    def run_scenario(self, scenario_name: str) -> Dict:
        """Run a predefined performance scenario."""
        if scenario_name not in PERFORMANCE_SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_name}")
        
        scenario = PERFORMANCE_SCENARIOS[scenario_name]
        
        print(f"Running performance scenario: {scenario.name}")
        print(f"Users: {scenario.users}, Duration: {scenario.duration}s")
        
        self.monitor.start_monitoring()
        
        # In a real implementation, this would integrate with Locust
        # For now, we'll simulate the test
        import time
        time.sleep(2)  # Simulate test execution
        
        self.monitor.stop_monitoring()
        
        # Generate mock results
        results = {
            'scenario': scenario.name,
            'users': scenario.users,
            'duration': scenario.duration,
            'total_requests': scenario.users * scenario.duration // 2,
            'failed_requests': 0,
            'avg_response_time': 150.0,
            'max_response_time': 800.0,
            'requests_per_second': scenario.users * 2.5,
            'passed_thresholds': True
        }
        
        return results
    
    def validate_thresholds(self, results: Dict) -> Dict:
        """Validate results against performance thresholds."""
        validation = {
            'passed': True,
            'failures': []
        }
        
        # Check response time thresholds
        if results.get('avg_response_time', 0) > self.thresholds.api_response_time_avg:
            validation['passed'] = False
            validation['failures'].append(
                f"Average response time {results['avg_response_time']:.2f}ms "
                f"exceeds threshold {self.thresholds.api_response_time_avg}ms"
            )
        
        if results.get('max_response_time', 0) > self.thresholds.api_response_time_max:
            validation['passed'] = False
            validation['failures'].append(
                f"Max response time {results['max_response_time']:.2f}ms "
                f"exceeds threshold {self.thresholds.api_response_time_max}ms"
            )
        
        # Check throughput thresholds
        if results.get('requests_per_second', 0) < self.thresholds.min_throughput:
            validation['passed'] = False
            validation['failures'].append(
                f"Throughput {results['requests_per_second']:.2f} req/s "
                f"below minimum {self.thresholds.min_throughput} req/s"
            )
        
        # Check error rate
        total_requests = results.get('total_requests', 1)
        failed_requests = results.get('failed_requests', 0)
        error_rate = (failed_requests / total_requests) * 100
        
        if error_rate > 5.0:  # 5% error rate threshold
            validation['passed'] = False
            validation['failures'].append(
                f"Error rate {error_rate:.2f}% exceeds 5% threshold"
            )
        
        return validation
    
    def generate_report(self, results: Dict, output_file: str = None):
        """Generate performance test report."""
        validation = self.validate_thresholds(results)
        
        report = {
            'test_summary': {
                'scenario': results['scenario'],
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'passed': validation['passed']
            },
            'performance_metrics': results,
            'threshold_validation': validation,
            'recommendations': self._generate_recommendations(results, validation)
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
        
        return report
    
    def _generate_recommendations(self, results: Dict, validation: Dict) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        if not validation['passed']:
            recommendations.append("Performance thresholds not met. Consider optimization.")
        
        avg_response_time = results.get('avg_response_time', 0)
        if avg_response_time > 500:
            recommendations.append("High response times detected. Consider caching implementation.")
        
        throughput = results.get('requests_per_second', 0)
        if throughput < self.thresholds.target_throughput:
            recommendations.append("Low throughput detected. Consider database optimization.")
        
        error_rate = (results.get('failed_requests', 0) / results.get('total_requests', 1)) * 100
        if error_rate > 1:
            recommendations.append("Errors detected. Review application logs and error handling.")
        
        if not recommendations:
            recommendations.append("Performance meets all thresholds. Consider load testing with higher user counts.")
        
        return recommendations


# Performance test utilities
def measure_execution_time(func):
    """Decorator to measure function execution time."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = (time.time() - start_time) * 1000  # Convert to ms
        
        print(f"{func.__name__} executed in {execution_time:.2f}ms")
        return result
    
    return wrapper


def create_performance_test_data(db_session, num_users=100, num_reports=500):
    """Create test data for performance testing."""
    from tests.factories import UserFactory, ReportFactory
    
    print(f"Creating performance test data: {num_users} users, {num_reports} reports")
    
    # Create users in batches
    batch_size = 50
    users = []
    
    for i in range(0, num_users, batch_size):
        batch_users = []
        for j in range(min(batch_size, num_users - i)):
            user = UserFactory(email=f'perf_user_{i+j}@test.com')
            batch_users.append(user)
        
        db_session.add_all(batch_users)
        users.extend(batch_users)
    
    db_session.commit()
    
    # Create reports in batches
    reports = []
    
    for i in range(0, num_reports, batch_size):
        batch_reports = []
        for j in range(min(batch_size, num_reports - i)):
            user = users[(i + j) % len(users)]  # Distribute reports among users
            report = ReportFactory(
                user_email=user.email,
                id=f'perf-report-{i+j:04d}'
            )
            batch_reports.append(report)
        
        db_session.add_all(batch_reports)
        reports.extend(batch_reports)
    
    db_session.commit()
    
    print(f"Created {len(users)} users and {len(reports)} reports")
    return users, reports


def cleanup_performance_test_data(db_session):
    """Clean up performance test data."""
    from models import User, Report
    
    # Delete performance test data
    User.query.filter(User.email.like('perf_user_%')).delete()
    Report.query.filter(Report.id.like('perf-report-%')).delete()
    
    db_session.commit()
    
    print("Performance test data cleaned up")


# Configuration for different environments
ENVIRONMENT_CONFIGS = {
    'development': {
        'base_url': 'http://localhost:5000',
        'thresholds': PerformanceThresholds(
            api_response_time_avg=500.0,
            api_response_time_max=2000.0,
            min_throughput=20.0
        )
    },
    
    'staging': {
        'base_url': 'https://staging.example.com',
        'thresholds': PerformanceThresholds(
            api_response_time_avg=300.0,
            api_response_time_max=1500.0,
            min_throughput=40.0
        )
    },
    
    'production': {
        'base_url': 'https://production.example.com',
        'thresholds': PerformanceThresholds()  # Use default strict thresholds
    }
}