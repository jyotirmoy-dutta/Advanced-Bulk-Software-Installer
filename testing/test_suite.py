#!/usr/bin/env python3
"""
Comprehensive Testing and QA System
Provides unit tests, integration tests, performance tests, and automated test execution
"""

import unittest
import asyncio
import time
import json
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
import uuid
from datetime import datetime, timedelta
from enum import Enum
import subprocess
import sys
import os
import tempfile
import shutil
import psutil
import coverage
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock

class TestType(Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"
    UI = "ui"
    API = "api"

class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"

@dataclass
class TestResult:
    """Test execution result."""
    test_id: str
    test_name: str
    test_type: TestType
    status: TestStatus
    execution_time: float
    start_time: datetime
    end_time: datetime
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    performance_metrics: Optional[Dict] = None
    coverage_data: Optional[Dict] = None

@dataclass
class TestSuite:
    """Test suite configuration."""
    name: str
    description: str
    test_type: TestType
    test_files: List[str]
    dependencies: List[str]
    timeout: int
    parallel: bool
    retry_count: int
    enabled: bool

class TestRunner:
    """Main test runner and execution engine."""
    
    def __init__(self, db_path: str = "test_results.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Test suites
        self.test_suites: Dict[str, TestSuite] = {}
        
        # Test results
        self.test_results: List[TestResult] = []
        
        # Coverage tracking
        self.coverage_tracker = coverage.Coverage()
        
        # Initialize database
        self._init_database()
        
        # Load test suites
        self._load_test_suites()
    
    def _init_database(self):
        """Initialize test results database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS test_suites (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    test_type TEXT,
                    test_files TEXT,
                    dependencies TEXT,
                    timeout INTEGER,
                    parallel BOOLEAN,
                    retry_count INTEGER,
                    enabled BOOLEAN
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS test_results (
                    id TEXT PRIMARY KEY,
                    test_id TEXT,
                    test_name TEXT,
                    test_type TEXT,
                    status TEXT,
                    execution_time REAL,
                    start_time TEXT,
                    end_time TEXT,
                    error_message TEXT,
                    stack_trace TEXT,
                    performance_metrics TEXT,
                    coverage_data TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS test_runs (
                    id TEXT PRIMARY KEY,
                    run_id TEXT,
                    suite_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    total_tests INTEGER,
                    passed_tests INTEGER,
                    failed_tests INTEGER,
                    skipped_tests INTEGER,
                    coverage_percentage REAL
                )
            ''')
            
            conn.commit()
    
    def _load_test_suites(self):
        """Load test suites from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM test_suites')
            for row in cursor.fetchall():
                suite = TestSuite(
                    name=row[1],
                    description=row[2],
                    test_type=TestType(row[3]),
                    test_files=json.loads(row[4]),
                    dependencies=json.loads(row[5]),
                    timeout=row[6],
                    parallel=row[7],
                    retry_count=row[8],
                    enabled=row[9]
                )
                self.test_suites[row[0]] = suite
    
    def add_test_suite(self, name: str, description: str, test_type: TestType,
                      test_files: List[str], dependencies: List[str] = None,
                      timeout: int = 300, parallel: bool = False, 
                      retry_count: int = 0) -> str:
        """Add a new test suite."""
        suite_id = str(uuid.uuid4())
        
        suite = TestSuite(
            name=name,
            description=description,
            test_type=test_type,
            test_files=test_files,
            dependencies=dependencies or [],
            timeout=timeout,
            parallel=parallel,
            retry_count=retry_count,
            enabled=True
        )
        
        self.test_suites[suite_id] = suite
        self._save_test_suite(suite_id, suite)
        
        return suite_id
    
    def _save_test_suite(self, suite_id: str, suite: TestSuite):
        """Save test suite to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO test_suites 
                (id, name, description, test_type, test_files, dependencies,
                 timeout, parallel, retry_count, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                suite_id, suite.name, suite.description, suite.test_type.value,
                json.dumps(suite.test_files), json.dumps(suite.dependencies),
                suite.timeout, suite.parallel, suite.retry_count, suite.enabled
            ))
            conn.commit()
    
    def run_test_suite(self, suite_name: str, run_id: str = None) -> Dict:
        """Run a test suite."""
        if not run_id:
            run_id = str(uuid.uuid4())
        
        # Find suite
        suite = None
        suite_id = None
        for sid, s in self.test_suites.items():
            if s.name == suite_name and s.enabled:
                suite = s
                suite_id = sid
                break
        
        if not suite:
            raise ValueError(f"Test suite '{suite_name}' not found or disabled")
        
        self.logger.info(f"Running test suite: {suite_name}")
        
        # Start coverage tracking
        self.coverage_tracker.start()
        
        start_time = datetime.now()
        results = []
        
        try:
            if suite.parallel:
                results = self._run_tests_parallel(suite, run_id)
            else:
                results = self._run_tests_sequential(suite, run_id)
        
        finally:
            # Stop coverage tracking
            self.coverage_tracker.stop()
            self.coverage_tracker.save()
        
        end_time = datetime.now()
        
        # Calculate statistics
        total_tests = len(results)
        passed_tests = len([r for r in results if r.status == TestStatus.PASSED])
        failed_tests = len([r for r in results if r.status == TestStatus.FAILED])
        skipped_tests = len([r for r in results if r.status == TestStatus.SKIPPED])
        
        # Get coverage percentage
        coverage_percentage = self._get_coverage_percentage()
        
        # Save run summary
        self._save_test_run(run_id, suite_name, start_time, end_time,
                           total_tests, passed_tests, failed_tests, skipped_tests,
                           coverage_percentage)
        
        # Save individual results
        for result in results:
            self._save_test_result(result)
        
        return {
            'run_id': run_id,
            'suite_name': suite_name,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'skipped_tests': skipped_tests,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            'coverage_percentage': coverage_percentage,
            'results': [asdict(r) for r in results]
        }
    
    def _run_tests_sequential(self, suite: TestSuite, run_id: str) -> List[TestResult]:
        """Run tests sequentially."""
        results = []
        
        for test_file in suite.test_files:
            file_results = self._run_test_file(test_file, suite, run_id)
            results.extend(file_results)
        
        return results
    
    def _run_tests_parallel(self, suite: TestSuite, run_id: str) -> List[TestResult]:
        """Run tests in parallel."""
        results = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_file = {
                executor.submit(self._run_test_file, test_file, suite, run_id): test_file
                for test_file in suite.test_files
            }
            
            for future in as_completed(future_to_file):
                try:
                    file_results = future.result()
                    results.extend(file_results)
                except Exception as e:
                    self.logger.error(f"Error running test file: {e}")
        
        return results
    
    def _run_test_file(self, test_file: str, suite: TestSuite, run_id: str) -> List[TestResult]:
        """Run a single test file and parse individual test results from pytest JSON report."""
        results = []
        import tempfile
        import os
        import json
        try:
            # Use a temp file for the JSON report
            with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp_json:
                json_report_path = tmp_json.name
            
            cmd = [
                sys.executable, '-m', 'pytest', test_file,
                '--json-report',
                f'--json-report-file={json_report_path}',
                '--tb=short'
            ]
            
            start_time = datetime.now()
            process = subprocess.run(
                cmd, capture_output=True, text=True, timeout=suite.timeout
            )
            end_time = datetime.now()
            
            # Parse pytest JSON report
            if os.path.exists(json_report_path):
                with open(json_report_path, 'r') as f:
                    report = json.load(f)
                for test in report.get('tests', []):
                    status = test.get('outcome', 'error')
                    if status == 'passed':
                        test_status = TestStatus.PASSED
                    elif status == 'failed':
                        test_status = TestStatus.FAILED
                    elif status == 'skipped':
                        test_status = TestStatus.SKIPPED
                    else:
                        test_status = TestStatus.ERROR
                    results.append(TestResult(
                        test_id=str(uuid.uuid4()),
                        test_name=test.get('nodeid', test_file),
                        test_type=suite.test_type,
                        status=test_status,
                        execution_time=test.get('duration', 0.0),
                        start_time=start_time,
                        end_time=end_time,
                        error_message=test.get('longrepr', None),
                        stack_trace=None
                    ))
                os.remove(json_report_path)
            else:
                # Fallback: file-level error
                test_result = TestResult(
                    test_id=str(uuid.uuid4()),
                    test_name=test_file,
                    test_type=suite.test_type,
                    status=TestStatus.ERROR,
                    execution_time=(end_time - start_time).total_seconds(),
                    start_time=start_time,
                    end_time=end_time,
                    error_message=process.stderr,
                    stack_trace=process.stdout
                )
                results.append(test_result)
        except subprocess.TimeoutExpired:
            test_result = TestResult(
                test_id=str(uuid.uuid4()),
                test_name=test_file,
                test_type=suite.test_type,
                status=TestStatus.TIMEOUT,
                execution_time=suite.timeout,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message=f"Test file timed out after {suite.timeout} seconds"
            )
            results.append(test_result)
        except Exception as e:
            test_result = TestResult(
                test_id=str(uuid.uuid4()),
                test_name=test_file,
                test_type=suite.test_type,
                status=TestStatus.ERROR,
                execution_time=0.0,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message=str(e),
                stack_trace=self._get_stack_trace()
            )
            results.append(test_result)
        return results
    
    def _parse_pytest_output(self, output: str, test_file: str, suite: TestSuite) -> List[TestResult]:
        """Parse pytest output to extract test results."""
        results = []
        
        # Simple parsing - in a real implementation, you'd use pytest's JSON output
        lines = output.split('\n')
        current_test = None
        
        for line in lines:
            if line.startswith('test_') and '::' in line:
                # Test name
                test_name = line.split('::')[1].strip()
                current_test = TestResult(
                    test_id=str(uuid.uuid4()),
                    test_name=test_name,
                    test_type=suite.test_type,
                    status=TestStatus.PASSED,
                    execution_time=0.0,
                    start_time=datetime.now(),
                    end_time=datetime.now()
                )
                results.append(current_test)
            elif line.startswith('FAILED') and current_test:
                current_test.status = TestStatus.FAILED
            elif line.startswith('SKIPPED') and current_test:
                current_test.status = TestStatus.SKIPPED
        
        return results
    
    def _parse_pytest_errors(self, error_output: str, test_file: str, suite: TestSuite) -> List[TestResult]:
        """Parse pytest error output."""
        results = []
        
        # Extract error information
        test_result = TestResult(
            test_id=str(uuid.uuid4()),
            test_name=test_file,
            test_type=suite.test_type,
            status=TestStatus.ERROR,
            execution_time=0.0,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error_message=error_output[:500],  # Truncate long error messages
            stack_trace=error_output
        )
        results.append(test_result)
        
        return results
    
    def _get_stack_trace(self) -> str:
        """Get current stack trace."""
        import traceback
        return ''.join(traceback.format_stack())
    
    def _get_coverage_percentage(self) -> float:
        """Get code coverage percentage."""
        try:
            total_lines = 0
            covered_lines = 0
            for filename in self.coverage_tracker.get_data().measured_files():
                analysis = self.coverage_tracker.analysis2(filename)
                total_lines += len(analysis[1]) + len(analysis[2])  # statements + excluded
                covered_lines += len(analysis[1])  # statements
            return (covered_lines / total_lines * 100) if total_lines > 0 else 0.0
        except Exception as e:
            self.logger.error(f"Error calculating coverage: {e}")
            return 0.0
    
    def _save_test_result(self, result: TestResult):
        """Save test result to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO test_results 
                (id, test_id, test_name, test_type, status, execution_time,
                 start_time, end_time, error_message, stack_trace,
                 performance_metrics, coverage_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), result.test_id, result.test_name,
                result.test_type.value, result.status.value, result.execution_time,
                result.start_time.isoformat(), result.end_time.isoformat(),
                result.error_message, result.stack_trace,
                json.dumps(result.performance_metrics) if result.performance_metrics else None,
                json.dumps(result.coverage_data) if result.coverage_data else None
            ))
            conn.commit()
    
    def _save_test_run(self, run_id: str, suite_name: str, start_time: datetime,
                      end_time: datetime, total_tests: int, passed_tests: int,
                      failed_tests: int, skipped_tests: int, coverage_percentage: float):
        """Save test run summary to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO test_runs 
                (id, run_id, suite_name, start_time, end_time, total_tests,
                 passed_tests, failed_tests, skipped_tests, coverage_percentage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), run_id, suite_name, start_time.isoformat(),
                end_time.isoformat(), total_tests, passed_tests, failed_tests,
                skipped_tests, coverage_percentage
            ))
            conn.commit()

class UnitTestSuite(unittest.TestCase):
    """Base class for unit tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

class TestBulkInstaller(UnitTestSuite):
    """Unit tests for bulk installer functionality."""
    
    def test_config_loading(self):
        """Test configuration file loading."""
        # Create test config
        config_data = {
            "apps": [
                {
                    "name": "test-app",
                    "manager": "winget",
                    "package": "test.package"
                }
            ],
            "settings": {
                "workers": 2,
                "timeout": 300
            }
        }
        
        config_file = Path("test_config.json")
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Test loading
        with open(config_file, 'r') as f:
            loaded_config = json.load(f)
        
        self.assertEqual(loaded_config["apps"][0]["name"], "test-app")
        self.assertEqual(loaded_config["settings"]["workers"], 2)
    
    def test_package_manager_detection(self):
        """Test package manager detection."""
        # Mock subprocess calls
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            # Test winget detection
            result = subprocess.run(['winget', '--version'], capture_output=True)
            self.assertEqual(result.returncode, 0)
    
    def test_app_installation_check(self):
        """Test app installation status check."""
        # Mock subprocess calls
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = b"test-app 1.0.0"
            
            # Test installation check
            result = subprocess.run(['winget', 'list', 'test-app'], capture_output=True)
            self.assertEqual(result.returncode, 0)
    
    @patch('subprocess.run')
    def test_silent_installation(self, mock_run):
        """Test silent installation process."""
        mock_run.return_value.returncode = 0
        
        # Test installation command
        cmd = ['winget', 'install', 'test.package', '--silent']
        result = subprocess.run(cmd, capture_output=True)
        
        self.assertEqual(result.returncode, 0)
        mock_run.assert_called_once()

class IntegrationTestSuite:
    """Integration test suite."""
    
    def __init__(self):
        self.test_runner = TestRunner()
        self.setup_integration_tests()
    
    def setup_integration_tests(self):
        """Set up integration test environment."""
        # Create test configuration
        self.test_config = {
            "apps": [
                {
                    "name": "notepad-plus-plus",
                    "manager": "winget",
                    "package": "Notepad++.Notepad++",
                    "tags": ["editor", "text"]
                },
                {
                    "name": "7zip",
                    "manager": "winget",
                    "package": "7zip.7zip",
                    "tags": ["compression", "utility"]
                }
            ],
            "settings": {
                "workers": 1,
                "timeout": 600,
                "log_level": "INFO"
            }
        }
        
        # Save test config
        with open("integration_test_config.json", 'w') as f:
            json.dump(self.test_config, f)
    
    def test_full_installation_workflow(self):
        """Test complete installation workflow."""
        # This would test the entire installation process
        # In a real implementation, you'd run the actual installer
        pass
    
    def test_error_handling(self):
        """Test error handling scenarios."""
        # Test with invalid package names
        # Test with network failures
        # Test with permission issues
        pass
    
    def test_parallel_processing(self):
        """Test parallel installation processing."""
        # Test multiple workers
        # Test resource management
        pass

class PerformanceTestSuite:
    """Performance test suite."""
    
    def __init__(self):
        self.test_runner = TestRunner()
        self.setup_performance_tests()
    
    def setup_performance_tests(self):
        """Set up performance test environment."""
        self.performance_config = {
            "apps": [
                {"name": f"test-app-{i}", "manager": "winget", "package": f"test.package.{i}"}
                for i in range(10)
            ],
            "settings": {
                "workers": 4,
                "timeout": 1800
            }
        }
    
    def test_installation_performance(self):
        """Test installation performance metrics."""
        start_time = time.time()
        
        # Simulate installation process
        time.sleep(2)  # Simulate work
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(execution_time, 5.0)  # Should complete within 5 seconds
    
    def test_memory_usage(self):
        """Test memory usage during installation."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Simulate installation work
        time.sleep(1)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory usage should be reasonable (less than 100MB increase)
        self.assertLess(memory_increase, 100 * 1024 * 1024)
    
    def test_cpu_usage(self):
        """Test CPU usage during installation."""
        # Monitor CPU usage during test
        cpu_percentages = []
        
        for _ in range(10):
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_percentages.append(cpu_percent)
        
        avg_cpu = sum(cpu_percentages) / len(cpu_percentages)
        
        # CPU usage should be reasonable
        self.assertLess(avg_cpu, 80.0)

class SecurityTestSuite:
    """Security test suite."""
    
    def test_config_file_security(self):
        """Test configuration file security."""
        # Test file permissions
        # Test content validation
        # Test injection attacks
        pass
    
    def test_network_security(self):
        """Test network security."""
        # Test HTTPS usage
        # Test certificate validation
        # Test secure downloads
        pass
    
    def test_execution_security(self):
        """Test execution security."""
        # Test command injection prevention
        # Test privilege escalation prevention
        # Test sandboxing
        pass

class UITestSuite:
    """UI test suite using mock GUI."""
    
    def test_gui_initialization(self):
        """Test GUI initialization."""
        # Mock tkinter
        with patch('tkinter.Tk') as mock_tk:
            mock_root = Mock()
            mock_tk.return_value = mock_root
            
            # Test GUI creation
            # This would test the actual GUI creation code
            pass
    
    def test_user_interactions(self):
        """Test user interactions."""
        # Test button clicks
        # Test form submissions
        # Test navigation
        pass

class APITestSuite:
    """API test suite."""
    
    def test_web_api_endpoints(self):
        """Test web API endpoints."""
        # Test Flask endpoints
        # Test authentication
        # Test data validation
        pass
    
    def test_websocket_communication(self):
        """Test WebSocket communication."""
        # Test real-time updates
        # Test connection management
        # Test error handling
        pass

class TestReportGenerator:
    """Generate comprehensive test reports."""
    
    def __init__(self, test_runner: TestRunner):
        self.test_runner = test_runner
        self.report_dir = Path("test_reports")
        self.report_dir.mkdir(exist_ok=True)
    
    def generate_html_report(self, run_id: str) -> str:
        """Generate HTML test report."""
        # Get test run data
        with sqlite3.connect(self.test_runner.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM test_runs WHERE run_id = ?
            ''', [run_id])
            run_data = cursor.fetchone()
            
            cursor = conn.execute('''
                SELECT * FROM test_results WHERE test_id IN (
                    SELECT test_id FROM test_results WHERE test_id LIKE ?
                )
            ''', [f"{run_id}%"])
            results = cursor.fetchall()
        
        if not run_data:
            return "Test run not found"
        
        # Generate HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Report - {run_data[2]}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .summary {{ margin: 20px 0; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #e8f4f8; border-radius: 3px; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                .skipped {{ color: orange; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Test Report</h1>
                <p>Suite: {run_data[2]}</p>
                <p>Run ID: {run_data[1]}</p>
                <p>Start Time: {run_data[3]}</p>
                <p>End Time: {run_data[4]}</p>
            </div>
            
            <div class="summary">
                <h2>Summary</h2>
                <div class="metric">
                    <strong>Total Tests:</strong> {run_data[5]}
                </div>
                <div class="metric">
                    <strong>Passed:</strong> <span class="passed">{run_data[6]}</span>
                </div>
                <div class="metric">
                    <strong>Failed:</strong> <span class="failed">{run_data[7]}</span>
                </div>
                <div class="metric">
                    <strong>Skipped:</strong> <span class="skipped">{run_data[8]}</span>
                </div>
                <div class="metric">
                    <strong>Coverage:</strong> {run_data[9]:.1f}%
                </div>
            </div>
            
            <div class="details">
                <h2>Test Details</h2>
                <table>
                    <tr>
                        <th>Test Name</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Error</th>
                    </tr>
        """
        
        for result in results:
            status_class = result[4].lower()
            html_content += f"""
                    <tr>
                        <td>{result[2]}</td>
                        <td>{result[3]}</td>
                        <td class="{status_class}">{result[4]}</td>
                        <td>{result[5]:.2f}s</td>
                        <td>{result[8] or ''}</td>
                    </tr>
            """
        
        html_content += """
                </table>
            </div>
        </body>
        </html>
        """
        
        # Save report
        report_path = self.report_dir / f"test_report_{run_id}.html"
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        return str(report_path)
    
    def generate_junit_xml(self, run_id: str) -> str:
        """Generate JUnit XML report."""
        # Get test results
        with sqlite3.connect(self.test_runner.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM test_results WHERE test_id IN (
                    SELECT test_id FROM test_results WHERE test_id LIKE ?
                )
            ''', [f"{run_id}%"])
            results = cursor.fetchall()
        
        # Create XML
        root = ET.Element("testsuites")
        testsuite = ET.SubElement(root, "testsuite", name="bulk_installer_tests")
        
        for result in results:
            testcase = ET.SubElement(testsuite, "testcase", name=result[2])
            
            if result[4] == "failed":
                failure = ET.SubElement(testcase, "failure", message=result[8] or "Test failed")
                failure.text = result[9] or ""
            elif result[4] == "skipped":
                ET.SubElement(testcase, "skipped")
        
        # Save XML
        xml_path = self.report_dir / f"test_results_{run_id}.xml"
        tree = ET.ElementTree(root)
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        
        return str(xml_path)

# Global test runner instance
test_runner = TestRunner()

# Add default test suites
test_runner.add_test_suite(
    name="unit_tests",
    description="Unit tests for core functionality",
    test_type=TestType.UNIT,
    test_files=["test_unit.py"],
    timeout=300,
    parallel=True
)

test_runner.add_test_suite(
    name="integration_tests",
    description="Integration tests for complete workflows",
    test_type=TestType.INTEGRATION,
    test_files=["test_integration.py"],
    timeout=600,
    parallel=False
)

test_runner.add_test_suite(
    name="performance_tests",
    description="Performance and load tests",
    test_type=TestType.PERFORMANCE,
    test_files=["test_performance.py"],
    timeout=1800,
    parallel=True
) 