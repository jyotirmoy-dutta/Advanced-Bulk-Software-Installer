#!/usr/bin/env python3
"""
Advanced Bulk Software Installer
Integrates analytics, automation, configuration management, network distribution, search, and testing
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
from datetime import datetime
from enum import Enum

# Import all advanced modules
from analytics.analytics_engine import analytics_engine, InstallationMetrics, SystemMetrics, UserMetrics
from automation.scheduler import automation_scheduler, TriggerType, EventType
from config.config_manager import config_manager, ConfigFormat
from network.distribution_manager import distribution_manager, DistributionMode
from search.package_discovery import package_discovery, SearchIndex
from testing.test_suite import test_runner, TestType

# Import core functionality
from bulk_installer import BulkInstaller, PackageManager

class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if isinstance(obj, tuple):
            return list(obj)
        return super().default(obj)

class AdvancedBulkInstaller(BulkInstaller):
    """Advanced bulk installer with all integrated features."""
    
    def __init__(self, config_file: str = "apps.json"):
        super().__init__(config_file)
        self.logger = logging.getLogger(__name__)
        
        # Initialize advanced features
        self.analytics_enabled = True
        self.automation_enabled = True
        self.distribution_enabled = True
        self.search_enabled = True
        self.testing_enabled = True
        
        # Start background services
        self._start_background_services()
    
    def _start_background_services(self):
        """Start background services for advanced features."""
        # Start automation scheduler
        if self.automation_enabled:
            automation_scheduler.start()
            self.logger.info("Automation scheduler started")
        
        # Start analytics monitoring
        if self.analytics_enabled:
            self.logger.info("Analytics monitoring active")
        
        # Start distribution services
        if self.distribution_enabled:
            self.logger.info("Distribution services active")
    
    def _get_apps_to_install(self, tags: Optional[List[str]] = None) -> List[Dict]:
        """Get list of apps to install, optionally filtered by tags."""
        try:
            apps = self._load_config()
            
            if tags:
                apps = [app for app in apps if app.tags and any(tag in app.tags for tag in tags)]
                self.logger.info(f"Filtered to {len(apps)} apps with tags: {tags}")
            
            # Convert AppConfig objects to dictionaries for compatibility
            return [{"name": app.name, "manager": app.manager, "tags": app.tags or []} for app in apps]
        except Exception as e:
            self.logger.error(f"Error loading apps: {e}")
            return []

    async def install_apps_advanced(self, tags: Optional[List[str]] = None, 
                                  workers: int = 1, dry_run: bool = False,
                                  use_p2p: bool = True, search_first: bool = False) -> Dict:
        """Advanced installation with all features integrated."""
        start_time = datetime.now()
        
        # Record user action
        if self.analytics_enabled:
            user_metrics = UserMetrics(
                user_id="system",
                action="install",
                timestamp=start_time,
                config_file=str(self.config_path),
                tags_used=tags or [],
                workers_used=workers,
                success=True
            )
            analytics_engine.record_user_action(user_metrics)
        
        # Search for packages if requested
        if search_first and self.search_enabled:
            await self._search_and_discover_packages(tags)
        
        # Get apps to install
        apps_to_install = self._get_apps_to_install(tags)
        
        if not apps_to_install:
            return {"message": "No apps found to install", "success": False}
        
        # Pre-installation analytics
        if self.analytics_enabled:
            self._record_pre_installation_metrics(apps_to_install)
        
        # Install apps with advanced features
        results = []
        failed_apps = []
        
        for app in apps_to_install:
            try:
                # Check if already installed
                if app['manager']:
                    try:
                        manager = PackageManager(app['manager'])
                        if self._is_app_installed(app['name'], manager):
                            self.logger.info(f"{app['name']} is already installed")
                            continue
                    except ValueError:
                        self.logger.warning(f"Invalid package manager: {app['manager']}")
                        continue
                
                # Download package if distribution is enabled
                if self.distribution_enabled and not dry_run:
                    await self._download_package_advanced(app, use_p2p)
                
                # Install app
                if not dry_run:
                    result = await self._install_app_advanced(app, workers)
                else:
                    result = {"status": "dry_run", "app": app['name']}
                
                results.append(result)
                
                # Record installation metrics
                if self.analytics_enabled:
                    self._record_installation_metrics(app, result, start_time)
                
            except Exception as e:
                error_msg = f"Failed to install {app['name']}: {str(e)}"
                self.logger.error(error_msg)
                failed_apps.append({"app": app['name'], "error": str(e)})
                
                # Record failure metrics
                if self.analytics_enabled:
                    self._record_installation_metrics(app, {"status": "failed", "error": str(e)}, start_time)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # Generate summary
        summary = {
            "total_apps": len(apps_to_install),
            "successful_installations": len([r for r in results if r.get("status") == "success"]),
            "failed_installations": len(failed_apps),
            "total_time": total_time,
            "results": results,
            "failed_apps": failed_apps,
            "analytics": self._get_installation_analytics() if self.analytics_enabled else None
        }
        
        return summary
    
    async def _search_and_discover_packages(self, tags: Optional[List[str]] = None):
        """Search and discover packages before installation."""
        if not self.search_enabled:
            return
        
        self.logger.info("Searching for packages...")
        
        # Search for packages by tags
        if tags:
            for tag in tags:
                search_results = package_discovery.search(tag, limit=5)
                self.logger.info(f"Found {len(search_results)} packages for tag '{tag}'")
                
                for result in search_results:
                    self.logger.info(f"  - {result.package.name} ({result.package.manager})")
        
        # Get recommendations
        context = {
            "current_packages": self._get_installed_packages(),
            "interests": tags or []
        }
        
        recommendations = package_discovery.get_recommendations(context, limit=3)
        self.logger.info(f"Recommended packages: {len(recommendations)}")
        
        for rec in recommendations:
            self.logger.info(f"  - {rec.package.name} (confidence: {rec.confidence:.2f})")
    
    async def _download_package_advanced(self, app: Dict, use_p2p: bool = True):
        """Download package using advanced distribution system."""
        if not self.distribution_enabled:
            return
        
        try:
            package_path = await distribution_manager.download_package(
                app['name'], app['manager'], use_p2p=use_p2p
            )
            self.logger.info(f"Downloaded {app['name']} to {package_path}")
        except Exception as e:
            self.logger.warning(f"Failed to download {app['name']}: {e}")
    
    async def _install_app_advanced(self, app: Dict, workers: int) -> Dict:
        """Install app with advanced features."""
        start_time = datetime.now()
        
        try:
            # Use parent class installation method
            result = await super()._install_app(app, workers)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "status": "success",
                "app": app['name'],
                "duration": duration,
                "manager": app['manager']
            }
        
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            return {
                "status": "failed",
                "app": app['name'],
                "error": str(e),
                "duration": duration,
                "manager": app['manager']
            }
    
    def _record_pre_installation_metrics(self, apps: List[Dict]):
        """Record pre-installation analytics."""
        if not self.analytics_enabled:
            return
        
        # Record system metrics before installation
        system_metrics = SystemMetrics(
            timestamp=datetime.now(),
            cpu_usage=0.0,  # Would get actual CPU usage
            memory_usage=0.0,  # Would get actual memory usage
            disk_usage=0.0,  # Would get actual disk usage
            network_io={},
            active_processes=0
        )
        analytics_engine.record_system_metrics(system_metrics)
    
    def _record_installation_metrics(self, app: Dict, result: Dict, start_time: datetime):
        """Record installation analytics."""
        if not self.analytics_enabled:
            return
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        installation_metrics = InstallationMetrics(
            app_name=app['name'],
            manager=app['manager'],
            platform=self._get_platform(),
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=result.get("status") == "success",
            error_message=result.get("error"),
            package_size=app.get("size"),
            download_speed=app.get("download_speed"),
            system_resources={
                "cpu_usage": 0.0,  # Would get actual values
                "memory_usage": 0.0,
                "disk_usage": 0.0
            }
        )
        
        analytics_engine.record_installation(installation_metrics)
    
    def _get_installation_analytics(self) -> Dict:
        """Get installation analytics summary."""
        if not self.analytics_enabled:
            return {}
        
        return {
            "real_time_stats": analytics_engine.get_real_time_stats(),
            "performance_report": analytics_engine.generate_performance_report(),
            "user_activity": analytics_engine.generate_user_activity_report()
        }
    
    def _get_platform(self) -> str:
        """Get current platform."""
        import platform
        return platform.system().lower()
    
    def _get_installed_packages(self) -> List[str]:
        """Get list of currently installed packages."""
        # This would query the system for installed packages
        # For now, return empty list
        return []
    
    def create_automation_rule(self, name: str, description: str, 
                             trigger_type: str, schedule_expr: str = None,
                             event_type: str = None, tags: List[str] = None) -> str:
        """Create an automation rule for installations."""
        if not self.automation_enabled:
            raise ValueError("Automation is not enabled")
        
        if trigger_type == "schedule" and schedule_expr:
            return automation_scheduler.create_scheduled_rule(
                name, description, schedule_expr, str(self.config_path), tags
            )
        elif trigger_type == "event" and event_type:
            return automation_scheduler.create_event_triggered_rule(
                name, description, EventType(event_type), str(self.config_path), tags
            )
        else:
            raise ValueError("Invalid trigger type or missing parameters")
    
    def search_packages(self, query: str, limit: int = 20, filters: Dict = None) -> List[Dict]:
        """Search for packages using the discovery system."""
        if not self.search_enabled:
            return []
        
        results = package_discovery.search(query, limit, filters)
        return [asdict(result) for result in results]
    
    def get_recommendations(self, context: Dict, algorithm: str = 'hybrid', 
                          limit: int = 10) -> List[Dict]:
        """Get package recommendations."""
        if not self.search_enabled:
            return []
        
        recommendations = package_discovery.get_recommendations(context, algorithm, limit)
        return [asdict(rec) for rec in recommendations]
    
    def run_tests(self, suite_name: str = "unit_tests") -> Dict:
        """Run test suite."""
        if not self.testing_enabled:
            return {"message": "Testing is not enabled"}
        
        try:
            result = test_runner.run_test_suite(suite_name)
            # Convert Enums to strings for JSON serialization
            def convert(obj):
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, dict):
                    return {k: convert(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [convert(i) for i in obj]
                return obj
            return convert(result)
        except Exception as e:
            return {"error": str(e), "success": False}
    
    def generate_reports(self) -> Dict:
        """Generate comprehensive reports."""
        reports = {}
        
        # Analytics reports
        if self.analytics_enabled:
            reports["analytics"] = {
                "installation_report": analytics_engine.generate_installation_report(),
                "performance_report": analytics_engine.generate_performance_report(),
                "user_activity_report": analytics_engine.generate_user_activity_report(),
                "visualization_report": analytics_engine.create_visualization_report()
            }
        
        # Distribution reports
        if self.distribution_enabled:
            reports["distribution"] = distribution_manager.get_distribution_stats()
        
        # Search reports
        if self.search_enabled:
            reports["search"] = package_discovery.get_search_statistics()
        
        # Configuration reports
        reports["configuration"] = {
            "versions": [asdict(v) for v in config_manager.get_versions()],
            "templates": [asdict(t) for t in config_manager.get_templates()],
            "environments": config_manager.get_environments()
        }
        
        return reports
    
    def export_data(self, format: str = 'json') -> str:
        """Export all data in specified format."""
        # Export analytics data
        if self.analytics_enabled:
            analytics_path = analytics_engine.export_data(format)
        
        # Export configuration data
        config_path = config_manager.export_config(ConfigFormat.JSON)
        
        # Export test results
        if self.testing_enabled:
            # This would export test results
            pass
        
        return {
            "analytics": analytics_path if self.analytics_enabled else None,
            "configuration": config_path
        }
    
    def cleanup(self):
        """Clean up resources and stop background services."""
        # Stop automation scheduler
        if self.automation_enabled:
            automation_scheduler.stop()
        
        # Clean up distribution cache
        if self.distribution_enabled:
            distribution_manager.cleanup_cache()
        
        # Clean up old analytics data
        if self.analytics_enabled:
            analytics_engine.cleanup_old_data()
        
        self.logger.info("Advanced bulk installer cleanup completed")

async def main():
    """Main function for advanced bulk installer."""
    parser = argparse.ArgumentParser(description="Advanced Bulk Software Installer")
    parser.add_argument("action", choices=["install", "uninstall", "update", "search", "test", "report", "automate"],
                       help="Action to perform")
    parser.add_argument("--config", "-c", default="apps.json", help="Configuration file")
    parser.add_argument("--tags", "-t", nargs="+", help="Filter apps by tags")
    parser.add_argument("--workers", "-w", type=int, default=1, help="Number of workers")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--p2p", action="store_true", help="Use P2P distribution")
    parser.add_argument("--search-first", action="store_true", help="Search before installing")
    parser.add_argument("--query", "-q", help="Search query")
    parser.add_argument("--suite", default="unit_tests", help="Test suite to run")
    parser.add_argument("--format", choices=["json", "html", "xml"], default="json", help="Report format")
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize advanced installer
    installer = AdvancedBulkInstaller(args.config)
    
    try:
        if args.action == "install":
            result = await installer.install_apps_advanced(
                tags=args.tags,
                workers=args.workers,
                dry_run=args.dry_run,
                use_p2p=args.p2p,
                search_first=args.search_first
            )
            print(json.dumps(result, indent=2, cls=EnhancedJSONEncoder))
        
        elif args.action == "search":
            if not args.query:
                print("Please provide a search query with --query")
                return
            
            results = installer.search_packages(args.query, limit=20)
            print(json.dumps(results, indent=2, cls=EnhancedJSONEncoder))
        
        elif args.action == "test":
            result = installer.run_tests(args.suite)
            print(json.dumps(result, indent=2, cls=EnhancedJSONEncoder))
        
        elif args.action == "report":
            reports = installer.generate_reports()
            print(json.dumps(reports, indent=2, cls=EnhancedJSONEncoder))
        
        elif args.action == "automate":
            # Create a sample automation rule
            rule_id = installer.create_automation_rule(
                name="Daily Updates",
                description="Automatically update packages daily",
                trigger_type="schedule",
                schedule_expr="0 2 * * *",  # Daily at 2 AM
                tags=["auto-update"]
            )
            print(f"Created automation rule: {rule_id}")
        
        else:
            print(f"Action '{args.action}' not implemented yet")
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
        logging.error(f"Error in main: {e}", exc_info=True)
    finally:
        installer.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 