#!/usr/bin/env python3
"""
Bulk Software Installer - Cross Platform
Supports Windows, macOS, and Linux with multiple package managers
"""

import json
import os
import sys
import subprocess
import platform
import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import shutil
import requests
import zipfile
import tarfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class Platform(Enum):
    WINDOWS = "windows"
    MACOS = "macos"
    LINUX = "linux"

class PackageManager(Enum):
    WINGET = "winget"
    CHOCO = "choco"
    SCOOP = "scoop"
    BREW = "brew"
    APT = "apt"
    YUM = "yum"
    DNF = "dnf"
    PACMAN = "pacman"
    SNAP = "snap"
    FLATPAK = "flatpak"
    PIP = "pip"
    NPM = "npm"
    CARGO = "cargo"
    GO = "go"

class OperationMode(Enum):
    INSTALL = "install"
    UNINSTALL = "uninstall"
    UPDATE = "update"
    UPGRADE = "upgrade"
    SEARCH = "search"
    LIST = "list"
    DRY_RUN = "dry-run"
    VERIFY = "verify"
    CLEANUP = "cleanup"

@dataclass
class AppConfig:
    name: str
    manager: Optional[str] = None
    custom_args: Optional[str] = None
    version: Optional[str] = None
    source: Optional[str] = None
    dependencies: Optional[List[str]] = None
    post_install: Optional[List[str]] = None
    pre_install: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    priority: int = 0
    force: bool = False
    skip_if_exists: bool = True

@dataclass
class InstallResult:
    app_name: str
    manager: str
    success: bool
    message: str
    duration: float
    version_installed: Optional[str] = None
    size_downloaded: Optional[int] = None

class BulkInstaller:
    def __init__(self, config_path: str = "apps.json", log_level: str = "INFO"):
        self.config_path = Path(config_path)
        self.platform = self._detect_platform()
        self.available_managers = self._get_available_managers()
        self.results = {
            "installed": [],
            "uninstalled": [],
            "updated": [],
            "skipped": [],
            "failed": [],
            "total": 0,
            "start_time": time.time(),
            "end_time": None
        }
        
        # Setup logging
        self._setup_logging(log_level)
        
        # Thread lock for results
        self.results_lock = threading.Lock()
        
    def _detect_platform(self) -> Platform:
        """Detect the current operating system."""
        system = platform.system().lower()
        if system == "windows":
            return Platform.WINDOWS
        elif system == "darwin":
            return Platform.MACOS
        elif system == "linux":
            return Platform.LINUX
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
    
    def _setup_logging(self, level: str):
        """Setup logging configuration."""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format=log_format,
            handlers=[
                logging.FileHandler('bulk_installer.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _get_available_managers(self) -> List[PackageManager]:
        """Get list of available package managers for current platform."""
        managers = []
        
        if self.platform == Platform.WINDOWS:
            if self._check_command("winget"):
                managers.append(PackageManager.WINGET)
            if self._check_command("choco"):
                managers.append(PackageManager.CHOCO)
            if self._check_command("scoop"):
                managers.append(PackageManager.SCOOP)
        
        elif self.platform == Platform.MACOS:
            if self._check_command("brew"):
                managers.append(PackageManager.BREW)
            if self._check_command("pip3"):
                managers.append(PackageManager.PIP)
            if self._check_command("npm"):
                managers.append(PackageManager.NPM)
            if self._check_command("cargo"):
                managers.append(PackageManager.CARGO)
            if self._check_command("go"):
                managers.append(PackageManager.GO)
        
        elif self.platform == Platform.LINUX:
            # System package managers
            if self._check_command("apt"):
                managers.append(PackageManager.APT)
            if self._check_command("yum"):
                managers.append(PackageManager.YUM)
            if self._check_command("dnf"):
                managers.append(PackageManager.DNF)
            if self._check_command("pacman"):
                managers.append(PackageManager.PACMAN)
            if self._check_command("snap"):
                managers.append(PackageManager.SNAP)
            if self._check_command("flatpak"):
                managers.append(PackageManager.FLATPAK)
            
            # Language package managers
            if self._check_command("pip3"):
                managers.append(PackageManager.PIP)
            if self._check_command("npm"):
                managers.append(PackageManager.NPM)
            if self._check_command("cargo"):
                managers.append(PackageManager.CARGO)
            if self._check_command("go"):
                managers.append(PackageManager.GO)
        
        return managers
    
    def _check_command(self, command: str) -> bool:
        """Check if a command is available."""
        try:
            subprocess.run([command, "--version"], 
                         capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _install_package_manager(self, manager: PackageManager) -> bool:
        """Install a package manager if not available."""
        self.logger.info(f"Installing package manager: {manager.value}")
        
        install_commands = {
            PackageManager.CHOCO: {
                "command": "powershell",
                "args": ["-Command", "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"],
                "platform": Platform.WINDOWS
            },
            PackageManager.SCOOP: {
                "command": "powershell",
                "args": ["-Command", "Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force; irm get.scoop.sh | iex"],
                "platform": Platform.WINDOWS
            },
            PackageManager.BREW: {
                "command": "/bin/bash",
                "args": ["-c", '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'],
                "platform": Platform.MACOS
            },
            PackageManager.PIP: {
                "command": "python3",
                "args": ["-m", "ensurepip", "--upgrade"],
                "platform": Platform.LINUX
            }
        }
        
        if manager in install_commands:
            cmd_info = install_commands[manager]
            if cmd_info["platform"] == self.platform:
                try:
                    subprocess.run([cmd_info["command"]] + cmd_info["args"], 
                                 check=True, timeout=300)
                    return True
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Failed to install {manager.value}: {e}")
                    return False
        
        return False
    
    def _is_app_installed(self, app_name: str, manager: PackageManager) -> bool:
        """Check if an application is installed via a specific package manager."""
        check_commands = {
            PackageManager.WINGET: ["winget", "list", "--name", app_name],
            PackageManager.CHOCO: ["choco", "list", "--local-only", app_name],
            PackageManager.SCOOP: ["scoop", "list"],
            PackageManager.BREW: ["brew", "list", app_name],
            PackageManager.APT: ["dpkg", "-l", app_name],
            PackageManager.YUM: ["rpm", "-q", app_name],
            PackageManager.DNF: ["rpm", "-q", app_name],
            PackageManager.PACMAN: ["pacman", "-Q", app_name],
            PackageManager.SNAP: ["snap", "list", app_name],
            PackageManager.FLATPAK: ["flatpak", "list", "--app", app_name],
            PackageManager.PIP: ["pip3", "show", app_name],
            PackageManager.NPM: ["npm", "list", "-g", app_name],
            PackageManager.CARGO: ["cargo", "install", "--list"],
            PackageManager.GO: ["go", "list", "-m", app_name]
        }
        
        if manager in check_commands:
            try:
                result = subprocess.run(check_commands[manager], 
                                      capture_output=True, text=True, timeout=30)
                return result.returncode == 0 and app_name in result.stdout
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return False
        
        return False
    
    def _install_app(self, app: AppConfig, manager: PackageManager) -> InstallResult:
        """Install an application using the specified package manager."""
        start_time = time.time()
        
        install_commands = {
            PackageManager.WINGET: ["winget", "install", "--id", app.name, "--silent", "--accept-package-agreements", "--accept-source-agreements"],
            PackageManager.CHOCO: ["choco", "install", app.name, "-y", "--no-progress"],
            PackageManager.SCOOP: ["scoop", "install", app.name],
            PackageManager.BREW: ["brew", "install", app.name],
            PackageManager.APT: ["sudo", "apt", "install", "-y", app.name],
            PackageManager.YUM: ["sudo", "yum", "install", "-y", app.name],
            PackageManager.DNF: ["sudo", "dnf", "install", "-y", app.name],
            PackageManager.PACMAN: ["sudo", "pacman", "-S", "--noconfirm", app.name],
            PackageManager.SNAP: ["sudo", "snap", "install", app.name],
            PackageManager.FLATPAK: ["flatpak", "install", "-y", "flathub", app.name],
            PackageManager.PIP: ["pip3", "install", app.name],
            PackageManager.NPM: ["npm", "install", "-g", app.name],
            PackageManager.CARGO: ["cargo", "install", app.name],
            PackageManager.GO: ["go", "install", app.name]
        }
        
        if manager not in install_commands:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message=f"Unsupported package manager: {manager.value}",
                duration=time.time() - start_time
            )
        
        cmd = install_commands[manager].copy()
        if app.custom_args:
            cmd.extend(app.custom_args.split())
        
        try:
            # Run pre-install commands
            if app.pre_install:
                for pre_cmd in app.pre_install:
                    subprocess.run(pre_cmd.split(), check=True, timeout=60)
            
            # Install the app
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            # Run post-install commands
            if app.post_install and result.returncode == 0:
                for post_cmd in app.post_install:
                    subprocess.run(post_cmd.split(), check=True, timeout=60)
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                return InstallResult(
                    app_name=app.name,
                    manager=manager.value,
                    success=True,
                    message=f"Successfully installed {app.name} with {manager.value}",
                    duration=duration
                )
            else:
                return InstallResult(
                    app_name=app.name,
                    manager=manager.value,
                    success=False,
                    message=f"Installation failed: {result.stderr}",
                    duration=duration
                )
                
        except subprocess.TimeoutExpired:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message="Installation timed out",
                duration=time.time() - start_time
            )
        except Exception as e:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message=f"Installation error: {str(e)}",
                duration=time.time() - start_time
            )
    
    def _uninstall_app(self, app: AppConfig, manager: PackageManager) -> InstallResult:
        """Uninstall an application using the specified package manager."""
        start_time = time.time()
        
        uninstall_commands = {
            PackageManager.WINGET: ["winget", "uninstall", "--id", app.name, "--silent"],
            PackageManager.CHOCO: ["choco", "uninstall", app.name, "-y"],
            PackageManager.SCOOP: ["scoop", "uninstall", app.name],
            PackageManager.BREW: ["brew", "uninstall", app.name],
            PackageManager.APT: ["sudo", "apt", "remove", "-y", app.name],
            PackageManager.YUM: ["sudo", "yum", "remove", "-y", app.name],
            PackageManager.DNF: ["sudo", "dnf", "remove", "-y", app.name],
            PackageManager.PACMAN: ["sudo", "pacman", "-R", "--noconfirm", app.name],
            PackageManager.SNAP: ["sudo", "snap", "remove", app.name],
            PackageManager.FLATPAK: ["flatpak", "uninstall", "-y", app.name],
            PackageManager.PIP: ["pip3", "uninstall", "-y", app.name],
            PackageManager.NPM: ["npm", "uninstall", "-g", app.name],
            PackageManager.CARGO: ["cargo", "uninstall", app.name],
            PackageManager.GO: ["go", "clean", "-i", app.name]
        }
        
        if manager not in uninstall_commands:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message=f"Unsupported package manager: {manager.value}",
                duration=time.time() - start_time
            )
        
        cmd = uninstall_commands[manager].copy()
        if app.custom_args:
            cmd.extend(app.custom_args.split())
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            duration = time.time() - start_time
            
            if result.returncode == 0:
                return InstallResult(
                    app_name=app.name,
                    manager=manager.value,
                    success=True,
                    message=f"Successfully uninstalled {app.name} with {manager.value}",
                    duration=duration
                )
            else:
                return InstallResult(
                    app_name=app.name,
                    manager=manager.value,
                    success=False,
                    message=f"Uninstallation failed: {result.stderr}",
                    duration=duration
                )
                
        except subprocess.TimeoutExpired:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message="Uninstallation timed out",
                duration=time.time() - start_time
            )
        except Exception as e:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message=f"Uninstallation error: {str(e)}",
                duration=time.time() - start_time
            )
    
    def _update_app(self, app: AppConfig, manager: PackageManager) -> InstallResult:
        """Update an application using the specified package manager."""
        start_time = time.time()
        
        update_commands = {
            PackageManager.WINGET: ["winget", "upgrade", "--id", app.name, "--silent"],
            PackageManager.CHOCO: ["choco", "upgrade", app.name, "-y"],
            PackageManager.SCOOP: ["scoop", "update", app.name],
            PackageManager.BREW: ["brew", "upgrade", app.name],
            PackageManager.APT: ["sudo", "apt", "upgrade", "-y", app.name],
            PackageManager.YUM: ["sudo", "yum", "update", "-y", app.name],
            PackageManager.DNF: ["sudo", "dnf", "upgrade", "-y", app.name],
            PackageManager.PACMAN: ["sudo", "pacman", "-Syu", "--noconfirm", app.name],
            PackageManager.SNAP: ["sudo", "snap", "refresh", app.name],
            PackageManager.FLATPAK: ["flatpak", "update", "-y", app.name],
            PackageManager.PIP: ["pip3", "install", "--upgrade", app.name],
            PackageManager.NPM: ["npm", "update", "-g", app.name],
            PackageManager.CARGO: ["cargo", "install", "--force", app.name],
            PackageManager.GO: ["go", "get", "-u", app.name]
        }
        
        if manager not in update_commands:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message=f"Unsupported package manager: {manager.value}",
                duration=time.time() - start_time
            )
        
        cmd = update_commands[manager].copy()
        if app.custom_args:
            cmd.extend(app.custom_args.split())
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            duration = time.time() - start_time
            
            if result.returncode == 0:
                return InstallResult(
                    app_name=app.name,
                    manager=manager.value,
                    success=True,
                    message=f"Successfully updated {app.name} with {manager.value}",
                    duration=duration
                )
            else:
                return InstallResult(
                    app_name=app.name,
                    manager=manager.value,
                    success=False,
                    message=f"Update failed: {result.stderr}",
                    duration=duration
                )
                
        except subprocess.TimeoutExpired:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message="Update timed out",
                duration=time.time() - start_time
            )
        except Exception as e:
            return InstallResult(
                app_name=app.name,
                manager=manager.value,
                success=False,
                message=f"Update error: {str(e)}",
                duration=time.time() - start_time
            )
    
    def _load_config(self) -> List[AppConfig]:
        """Load application configuration from JSON file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            data = json.load(f)
        
        apps = []
        for item in data:
            app = AppConfig(
                name=item["name"],
                manager=item.get("manager"),
                custom_args=item.get("customArgs"),
                version=item.get("version"),
                source=item.get("source"),
                dependencies=item.get("dependencies", []),
                post_install=item.get("postInstall", []),
                pre_install=item.get("preInstall", []),
                tags=item.get("tags", []),
                priority=item.get("priority", 0),
                force=item.get("force", False),
                skip_if_exists=item.get("skipIfExists", True)
            )
            apps.append(app)
        
        # Sort by priority (higher priority first)
        apps.sort(key=lambda x: x.priority, reverse=True)
        return apps
    
    def _process_app(self, app: AppConfig, mode: OperationMode, max_workers: int = 1) -> InstallResult:
        """Process a single application."""
        self.logger.info(f"Processing: {app.name}")
        
        # Determine which managers to try
        managers_to_try = []
        if app.manager:
            try:
                managers_to_try.append(PackageManager(app.manager))
            except ValueError:
                self.logger.warning(f"Invalid package manager: {app.manager}")
        
        if not managers_to_try:
            managers_to_try = self.available_managers
        
        for manager in managers_to_try:
            # Check if app is installed
            installed = self._is_app_installed(app.name, manager)
            
            if mode == OperationMode.INSTALL:
                if installed and app.skip_if_exists:
                    with self.results_lock:
                        self.results["skipped"].append(f"{app.name} ({manager.value})")
                    return InstallResult(
                        app_name=app.name,
                        manager=manager.value,
                        success=True,
                        message=f"{app.name} already installed via {manager.value}",
                        duration=0
                    )
                else:
                    result = self._install_app(app, manager)
            
            elif mode == OperationMode.UNINSTALL:
                if not installed:
                    with self.results_lock:
                        self.results["skipped"].append(f"{app.name} ({manager.value})")
                    return InstallResult(
                        app_name=app.name,
                        manager=manager.value,
                        success=True,
                        message=f"{app.name} not installed via {manager.value}",
                        duration=0
                    )
                else:
                    result = self._uninstall_app(app, manager)
            
            elif mode == OperationMode.UPDATE:
                if not installed:
                    with self.results_lock:
                        self.results["skipped"].append(f"{app.name} ({manager.value})")
                    return InstallResult(
                        app_name=app.name,
                        manager=manager.value,
                        success=True,
                        message=f"{app.name} not installed via {manager.value}",
                        duration=0
                    )
                else:
                    result = self._update_app(app, manager)
            
            elif mode == OperationMode.DRY_RUN:
                return InstallResult(
                    app_name=app.name,
                    manager=manager.value,
                    success=True,
                    message=f"Would process {app.name} with {manager.value}",
                    duration=0
                )
            
            # If successful, return the result
            if result.success:
                with self.results_lock:
                    if mode == OperationMode.INSTALL:
                        self.results["installed"].append(f"{app.name} ({manager.value})")
                    elif mode == OperationMode.UNINSTALL:
                        self.results["uninstalled"].append(f"{app.name} ({manager.value})")
                    elif mode == OperationMode.UPDATE:
                        self.results["updated"].append(f"{app.name} ({manager.value})")
                return result
        
        # If we get here, all managers failed
        with self.results_lock:
            self.results["failed"].append(app.name)
        
        return InstallResult(
            app_name=app.name,
            manager="unknown",
            success=False,
            message=f"Failed to process {app.name} with any available manager",
            duration=0
        )
    
    def run(self, mode: OperationMode, max_workers: int = 1, filter_tags: Optional[List[str]] = None) -> Dict:
        """Run the bulk installer with the specified mode."""
        self.logger.info(f"Starting Bulk Software Installer in {mode.value} mode")
        
        try:
            apps = self._load_config()
            self.results["total"] = len(apps)
            
            # Filter by tags if specified
            if filter_tags:
                apps = [app for app in apps if app.tags and any(tag in app.tags for tag in filter_tags)]
                self.logger.info(f"Filtered to {len(apps)} apps with tags: {filter_tags}")
            
            if max_workers > 1:
                # Parallel processing
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(self._process_app, app, mode, max_workers) for app in apps]
                    for future in as_completed(futures):
                        result = future.result()
                        self.logger.info(f"{result.app_name}: {result.message}")
            else:
                # Sequential processing
                for app in apps:
                    result = self._process_app(app, mode, max_workers)
                    self.logger.info(f"{result.app_name}: {result.message}")
            
            self.results["end_time"] = time.time()
            self._print_summary(mode)
            
        except Exception as e:
            self.logger.error(f"Error during execution: {e}")
            raise
        
        return self.results
    
    def _print_summary(self, mode: OperationMode):
        """Print a summary of the results."""
        duration = self.results["end_time"] - self.results["start_time"]
        
        print(f"\n{'='*50}")
        print(f"BULK SOFTWARE INSTALLER SUMMARY")
        print(f"{'='*50}")
        print(f"Mode: {mode.value}")
        print(f"Platform: {self.platform.value}")
        print(f"Total apps processed: {self.results['total']}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Available package managers: {[m.value for m in self.available_managers]}")
        
        if self.results["installed"]:
            print(f"\n✅ Successfully installed:")
            for item in self.results["installed"]:
                print(f"  • {item}")
        
        if self.results["uninstalled"]:
            print(f"\n🗑️  Successfully uninstalled:")
            for item in self.results["uninstalled"]:
                print(f"  • {item}")
        
        if self.results["updated"]:
            print(f"\n🔄 Successfully updated:")
            for item in self.results["updated"]:
                print(f"  • {item}")
        
        if self.results["skipped"]:
            print(f"\n⏭️  Skipped:")
            for item in self.results["skipped"]:
                print(f"  • {item}")
        
        if self.results["failed"]:
            print(f"\n❌ Failed:")
            for item in self.results["failed"]:
                print(f"  • {item}")
        
        print(f"\n📋 Log file: bulk_installer.log")
        print(f"{'='*50}")

def main():
    parser = argparse.ArgumentParser(description="Cross-platform Bulk Software Installer")
    parser.add_argument("mode", choices=[m.value for m in OperationMode], 
                       default="install", nargs="?", help="Operation mode")
    parser.add_argument("--config", "-c", default="apps.json", 
                       help="Configuration file path")
    parser.add_argument("--workers", "-w", type=int, default=1, 
                       help="Number of parallel workers")
    parser.add_argument("--tags", "-t", nargs="+", 
                       help="Filter apps by tags")
    parser.add_argument("--log-level", "-l", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    parser.add_argument("--install-managers", action="store_true",
                       help="Install missing package managers")
    
    args = parser.parse_args()
    
    try:
        installer = BulkInstaller(args.config, args.log_level)
        
        # Install missing package managers if requested
        if args.install_managers:
            installer.logger.info("Installing missing package managers...")
            # This would be implemented to install missing managers
        
        # Run the installer
        mode = OperationMode(args.mode)
        results = installer.run(mode, args.workers, args.tags)
        
        # Exit with error code if any failures
        if results["failed"]:
            sys.exit(1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 