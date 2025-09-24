#!/usr/bin/env python3
"""
Performance test runner script for SAT Report Generator.
"""
import os
import sys
import argparse
import subprocess
import json
from datetime import datetime


def run_locust_test(scenario, host, duration=300, users=50, spawn_rate=5, output_dir='performance_results'):
    """Run Locust performance test."""
    print(f"Running Locust performance test: {scenario}")
    print(f"Target: {host}")
    print(f"Users: {users}, Duration: {duration}s, Spawn rate: {spawn_rate}")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp for unique filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Output files
    html_report = os.path.join(output_dir, f'locust_report_{scenario}_{timestamp}.html')
    csv_stats = os.path.join(output_dir, f'locust_stats_{scenario}_{timestamp}.csv')
    
    # Locust command
    cmd = [
        'locust',
        '-f', 'tests/performance/locustfile.py',
        '--host', host,
        '--users', str(users),
        '--spawn-rate', str(spawn_rate),
        '--run-time', f'{duration}s',
        '--html', html_report,
        '--csv', csv_stats.replace('.csv', ''),  # Locust adds suffixes
        '--headless'
    ]
    
    try:
        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='SERVER')
        
        if result.returncode == 0:
            print("✅ Locust test completed successfully")
            print(f"📊 HTML report: {html_report}")
            print(f"📈 CSV stats: {csv_stats}")
            
            # Print summary from stdout
            if result.stdout:
                print("\n📋 Test Summary:")
                print(result.stdout)
        else:
            print("❌ Locust test failed")
            print(f"Error: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ Locust not found. Install with: pip install locust")
        return False
    except Exception as e:
        print(f"❌ Error running Locust: {e}")
        return False
    
    return True


def run_pytest_performance_tests(test_pattern='tests/performance/', output_dir='performance_results'):
    """Run pytest performance tests."""
    print("Running pytest performance tests...")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp for unique filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Output files
    junit_xml = os.path.join(output_dir, f'pytest_performance_{timestamp}.xml')
    html_report = os.path.join(output_dir, f'pytest_performance_{timestamp}.html')
    
    # Pytest command
    cmd = [
        'python', '-m', 'pytest',
        test_pattern,
        '-v',
        '--tb=short',
        '-m', 'performance',
        f'--junitxml={junit_xml}',
        f'--html={html_report}',
        '--self-contained-html'
    ]
    
    try:
        print(f"Executing: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd='SERVER')
        
        if result.returncode == 0:
            print("✅ Pytest performance tests completed successfully")
            print(f"📊 HTML report: {html_report}")
            print(f"📋 JUnit XML: {junit_xml}")
        else:
            print("❌ Some pytest performance tests failed")
            return False
            
    except Exception as e:
        print(f"❌ Error running pytest: {e}")
        return False
    
    return True


def run_database_benchmarks(output_dir='performance_results'):
    """Run database performance benchmarks."""
    print("Running database performance benchmarks...")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Run specific database performance tests
    cmd = [
        'python', '-m', 'pytest',
        'tests/performance/test_database_performance.py',
        '-v',
        '--tb=short',
        '-s'  # Show print statements
    ]
    
    try:
        result = subprocess.run(cmd, cwd='SERVER')
        
        if result.returncode == 0:
            print("✅ Database benchmarks completed successfully")
        else:
            print("❌ Database benchmarks failed")
            return False
            
    except Exception as e:
        print(f"❌ Error running database benchmarks: {e}")
        return False
    
    return True


def run_api_benchmarks(host='http://localhost:5000', output_dir='performance_results'):
    """Run API performance benchmarks."""
    print("Running API performance benchmarks...")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Set environment variable for test host
    env = os.environ.copy()
    env['TEST_HOST'] = host
    
    # Run API performance tests
    cmd = [
        'python', '-m', 'pytest',
        'tests/performance/test_api_performance.py',
        '-v',
        '--tb=short',
        '-s'
    ]
    
    try:
        result = subprocess.run(cmd, cwd='SERVER', env=env)
        
        if result.returncode == 0:
            print("✅ API benchmarks completed successfully")
        else:
            print("❌ API benchmarks failed")
            return False
            
    except Exception as e:
        print(f"❌ Error running API benchmarks: {e}")
        return False
    
    return True


def generate_summary_report(output_dir='performance_results'):
    """Generate a summary report of all performance tests."""
    print("Generating performance summary report...")
    
    summary = {
        'timestamp': datetime.now().isoformat(),
        'tests_run': [],
        'overall_status': 'PASSED',
        'recommendations': []
    }
    
    # Look for test result files
    if os.path.exists(output_dir):
        files = os.listdir(output_dir)
        
        # Count different types of reports
        locust_reports = [f for f in files if f.startswith('locust_report_')]
        pytest_reports = [f for f in files if f.startswith('pytest_performance_')]
        
        summary['tests_run'] = {
            'locust_load_tests': len(locust_reports),
            'pytest_performance_tests': len(pytest_reports)
        }
        
        if locust_reports:
            summary['recommendations'].append("Review Locust HTML reports for detailed performance metrics")
        
        if pytest_reports:
            summary['recommendations'].append("Check pytest HTML reports for individual test results")
    
    # Save summary
    summary_file = os.path.join(output_dir, f'performance_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"📋 Summary report saved: {summary_file}")
    
    # Print summary to console
    print("\n" + "="*60)
    print("PERFORMANCE TEST SUMMARY")
    print("="*60)
    print(f"Timestamp: {summary['timestamp']}")
    print(f"Overall Status: {summary['overall_status']}")
    print(f"Tests Run: {summary['tests_run']}")
    
    if summary['recommendations']:
        print("\nRecommendations:")
        for rec in summary['recommendations']:
            print(f"  • {rec}")
    
    print("="*60)


def main():
    """Main performance test runner."""
    parser = argparse.ArgumentParser(description='Run performance tests for SAT Report Generator')
    
    parser.add_argument('--host', default='http://localhost:5000',
                       help='Target host for performance tests')
    parser.add_argument('--users', type=int, default=50,
                       help='Number of concurrent users for load tests')
    parser.add_argument('--duration', type=int, default=300,
                       help='Test duration in seconds')
    parser.add_argument('--spawn-rate', type=int, default=5,
                       help='User spawn rate per second')
    parser.add_argument('--output-dir', default='performance_results',
                       help='Output directory for test results')
    parser.add_argument('--test-type', choices=['all', 'locust', 'pytest', 'database', 'api'],
                       default='all', help='Type of performance tests to run')
    parser.add_argument('--scenario', default='load_test',
                       help='Locust test scenario to run')
    
    args = parser.parse_args()
    
    print("🚀 Starting SAT Report Generator Performance Tests")
    print(f"Target Host: {args.host}")
    print(f"Output Directory: {args.output_dir}")
    print(f"Test Type: {args.test_type}")
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    success = True
    
    if args.test_type in ['all', 'locust']:
        print("\n" + "="*50)
        print("RUNNING LOCUST LOAD TESTS")
        print("="*50)
        success &= run_locust_test(
            scenario=args.scenario,
            host=args.host,
            duration=args.duration,
            users=args.users,
            spawn_rate=args.spawn_rate,
            output_dir=args.output_dir
        )
    
    if args.test_type in ['all', 'pytest']:
        print("\n" + "="*50)
        print("RUNNING PYTEST PERFORMANCE TESTS")
        print("="*50)
        success &= run_pytest_performance_tests(output_dir=args.output_dir)
    
    if args.test_type in ['all', 'database']:
        print("\n" + "="*50)
        print("RUNNING DATABASE BENCHMARKS")
        print("="*50)
        success &= run_database_benchmarks(output_dir=args.output_dir)
    
    if args.test_type in ['all', 'api']:
        print("\n" + "="*50)
        print("RUNNING API BENCHMARKS")
        print("="*50)
        success &= run_api_benchmarks(host=args.host, output_dir=args.output_dir)
    
    # Generate summary report
    print("\n" + "="*50)
    print("GENERATING SUMMARY REPORT")
    print("="*50)
    generate_summary_report(output_dir=args.output_dir)
    
    if success:
        print("\n✅ All performance tests completed successfully!")
        return 0
    else:
        print("\n❌ Some performance tests failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())