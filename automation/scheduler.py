#!/usr/bin/env python3
"""
Advanced Automation and Scheduling System
Provides cron-like scheduling, event-driven triggers, and conditional installations
"""

import schedule
import time
import threading
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import subprocess
import psutil
import platform
import hashlib
from enum import Enum
import yaml
import sqlite3
import uuid
from collections import defaultdict

class TriggerType(Enum):
    SCHEDULE = "schedule"
    EVENT = "event"
    CONDITION = "condition"
    MANUAL = "manual"

class EventType(Enum):
    SYSTEM_STARTUP = "system_startup"
    USER_LOGIN = "user_login"
    FILE_CHANGE = "file_change"
    NETWORK_AVAILABLE = "network_available"
    DISK_SPACE_LOW = "disk_space_low"
    HIGH_CPU_USAGE = "high_cpu_usage"
    CUSTOM = "custom"

@dataclass
class AutomationRule:
    """Represents an automation rule."""
    id: str
    name: str
    description: str
    trigger_type: TriggerType
    schedule_expression: Optional[str] = None
    event_type: Optional[EventType] = None
    conditions: Optional[List[Dict]] = None
    config_file: str = "apps.json"
    tags: Optional[List[str]] = None
    workers: int = 1
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Condition:
    """Represents a condition for triggering automation."""
    type: str  # system_specs, time, network, custom
    operator: str  # >, <, ==, !=, >=, <=, contains, exists
    value: Any
    field: Optional[str] = None

class AutomationScheduler:
    """Advanced automation and scheduling system."""
    
    def __init__(self, db_path: str = "automation.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.rules: Dict[str, AutomationRule] = {}
        self.running = False
        self.scheduler_thread = None
        
        # Initialize database
        self._init_database()
        
        # Load existing rules
        self._load_rules()
        
        # Event listeners
        self.event_listeners: Dict[EventType, List[Callable]] = defaultdict(list)
        
        # System monitoring
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._system_monitoring, daemon=True)
        self.monitor_thread.start()
    
    def _init_database(self):
        """Initialize automation database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS automation_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    trigger_type TEXT,
                    schedule_expression TEXT,
                    event_type TEXT,
                    conditions TEXT,
                    config_file TEXT,
                    tags TEXT,
                    workers INTEGER,
                    enabled BOOLEAN,
                    last_run TEXT,
                    next_run TEXT,
                    run_count INTEGER,
                    success_count INTEGER,
                    failure_count INTEGER,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS automation_logs (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT,
                    execution_time TEXT,
                    success BOOLEAN,
                    output TEXT,
                    error_message TEXT,
                    duration REAL
                )
            ''')
            
            conn.commit()
    
    def _load_rules(self):
        """Load automation rules from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM automation_rules WHERE enabled = 1')
            for row in cursor.fetchall():
                rule = AutomationRule(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    trigger_type=TriggerType(row[3]),
                    schedule_expression=row[4],
                    event_type=EventType(row[5]) if row[5] else None,
                    conditions=json.loads(row[6]) if row[6] else None,
                    config_file=row[7],
                    tags=json.loads(row[8]) if row[8] else None,
                    workers=row[9],
                    enabled=row[10],
                    last_run=datetime.fromisoformat(row[11]) if row[11] else None,
                    next_run=datetime.fromisoformat(row[12]) if row[12] else None,
                    run_count=row[13],
                    success_count=row[14],
                    failure_count=row[15],
                    created_at=datetime.fromisoformat(row[16]) if row[16] else None,
                    updated_at=datetime.fromisoformat(row[17]) if row[17] else None
                )
                self.rules[rule.id] = rule
    
    def create_scheduled_rule(self, name: str, description: str, schedule_expr: str,
                            config_file: str = "apps.json", tags: Optional[List[str]] = None,
                            workers: int = 1) -> str:
        """Create a scheduled automation rule."""
        rule_id = str(uuid.uuid4())
        now = datetime.now()
        
        rule = AutomationRule(
            id=rule_id,
            name=name,
            description=description,
            trigger_type=TriggerType.SCHEDULE,
            schedule_expression=schedule_expr,
            config_file=config_file,
            tags=tags,
            workers=workers,
            created_at=now,
            updated_at=now
        )
        
        # Parse schedule expression and set next run
        rule.next_run = self._parse_schedule_expression(schedule_expr)
        
        # Save to database
        self._save_rule(rule)
        self.rules[rule_id] = rule
        
        # Schedule the job
        self._schedule_job(rule)
        
        return rule_id
    
    def create_event_triggered_rule(self, name: str, description: str, event_type: EventType,
                                  config_file: str = "apps.json", tags: Optional[List[str]] = None,
                                  workers: int = 1) -> str:
        """Create an event-triggered automation rule."""
        rule_id = str(uuid.uuid4())
        now = datetime.now()
        
        rule = AutomationRule(
            id=rule_id,
            name=name,
            description=description,
            trigger_type=TriggerType.EVENT,
            event_type=event_type,
            config_file=config_file,
            tags=tags,
            workers=workers,
            created_at=now,
            updated_at=now
        )
        
        # Save to database
        self._save_rule(rule)
        self.rules[rule_id] = rule
        
        # Register event listener
        self._register_event_listener(rule)
        
        return rule_id
    
    def create_conditional_rule(self, name: str, description: str, conditions: List[Condition],
                              config_file: str = "apps.json", tags: Optional[List[str]] = None,
                              workers: int = 1) -> str:
        """Create a condition-based automation rule."""
        rule_id = str(uuid.uuid4())
        now = datetime.now()
        
        rule = AutomationRule(
            id=rule_id,
            name=name,
            description=description,
            trigger_type=TriggerType.CONDITION,
            conditions=[asdict(cond) for cond in conditions],
            config_file=config_file,
            tags=tags,
            workers=workers,
            created_at=now,
            updated_at=now
        )
        
        # Save to database
        self._save_rule(rule)
        self.rules[rule_id] = rule
        
        return rule_id
    
    def _parse_schedule_expression(self, expr: str) -> datetime:
        """Parse cron-like schedule expression."""
        # Simple cron-like parser (minute hour day month weekday)
        parts = expr.split()
        if len(parts) != 5:
            raise ValueError("Schedule expression must have 5 parts: minute hour day month weekday")
        
        minute, hour, day, month, weekday = parts
        
        # Calculate next run time
        now = datetime.now()
        
        # This is a simplified parser - in production, use a proper cron parser
        if minute == "*":
            next_minute = now.minute + 1
        else:
            next_minute = int(minute)
        
        if hour == "*":
            next_hour = now.hour
        else:
            next_hour = int(hour)
        
        # Calculate next run
        next_run = now.replace(minute=next_minute, hour=next_hour, second=0, microsecond=0)
        
        # If next run is in the past, add one hour
        if next_run <= now:
            next_run += timedelta(hours=1)
        
        return next_run
    
    def _schedule_job(self, rule: AutomationRule):
        """Schedule a job using the schedule library."""
        if rule.trigger_type == TriggerType.SCHEDULE and rule.schedule_expression:
            # Parse cron expression and schedule
            parts = rule.schedule_expression.split()
            minute, hour, day, month, weekday = parts
            
            if minute != "*" and hour != "*":
                # Daily at specific time
                schedule.every().day.at(f"{hour.zfill(2)}:{minute.zfill(2)}").do(
                    self._execute_rule, rule.id
                )
            elif minute != "*":
                # Every hour at specific minute
                schedule.every().hour.at(f":{minute.zfill(2)}").do(
                    self._execute_rule, rule.id
                )
            else:
                # Every minute (default)
                schedule.every().minute.do(self._execute_rule, rule.id)
    
    def _register_event_listener(self, rule: AutomationRule):
        """Register event listener for event-triggered rules."""
        if rule.event_type:
            self.event_listeners[rule.event_type].append(
                lambda: self._execute_rule(rule.id)
            )
    
    def _execute_rule(self, rule_id: str):
        """Execute an automation rule."""
        if rule_id not in self.rules:
            self.logger.error(f"Rule {rule_id} not found")
            return
        
        rule = self.rules[rule_id]
        start_time = datetime.now()
        
        try:
            self.logger.info(f"Executing rule: {rule.name}")
            
            # Build command
            cmd = ["python", "bulk_installer.py", "install"]
            cmd.extend(["--config", rule.config_file])
            cmd.extend(["--workers", str(rule.workers)])
            
            if rule.tags:
                cmd.extend(["--tags", ",".join(rule.tags)])
            
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            # Update rule statistics
            rule.last_run = start_time
            rule.run_count += 1
            
            if result.returncode == 0:
                rule.success_count += 1
                success = True
                output = result.stdout
                error_message = None
            else:
                rule.failure_count += 1
                success = False
                output = result.stdout
                error_message = result.stderr
            
            # Calculate next run for scheduled rules
            if rule.trigger_type == TriggerType.SCHEDULE and rule.schedule_expression:
                rule.next_run = self._parse_schedule_expression(rule.schedule_expression)
            
            # Update database
            self._update_rule(rule)
            
            # Log execution
            self._log_execution(rule_id, start_time, success, output, error_message, 
                              (datetime.now() - start_time).total_seconds())
            
            self.logger.info(f"Rule {rule.name} executed successfully" if success else f"Rule {rule.name} failed")
            
        except Exception as e:
            self.logger.error(f"Error executing rule {rule.name}: {e}")
            rule.failure_count += 1
            self._update_rule(rule)
            self._log_execution(rule_id, start_time, False, "", str(e), 
                              (datetime.now() - start_time).total_seconds())
    
    def _save_rule(self, rule: AutomationRule):
        """Save rule to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO automation_rules 
                (id, name, description, trigger_type, schedule_expression, event_type,
                 conditions, config_file, tags, workers, enabled, last_run, next_run,
                 run_count, success_count, failure_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                rule.id, rule.name, rule.description, rule.trigger_type.value,
                rule.schedule_expression, rule.event_type.value if rule.event_type else None,
                json.dumps(rule.conditions) if rule.conditions else None,
                rule.config_file, json.dumps(rule.tags) if rule.tags else None,
                rule.workers, rule.enabled,
                rule.last_run.isoformat() if rule.last_run else None,
                rule.next_run.isoformat() if rule.next_run else None,
                rule.run_count, rule.success_count, rule.failure_count,
                rule.created_at.isoformat() if rule.created_at else None,
                rule.updated_at.isoformat() if rule.updated_at else None
            ))
            conn.commit()
    
    def _update_rule(self, rule: AutomationRule):
        """Update rule in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE automation_rules 
                SET last_run = ?, next_run = ?, run_count = ?, success_count = ?, 
                    failure_count = ?, updated_at = ?
                WHERE id = ?
            ''', (
                rule.last_run.isoformat() if rule.last_run else None,
                rule.next_run.isoformat() if rule.next_run else None,
                rule.run_count, rule.success_count, rule.failure_count,
                datetime.now().isoformat(), rule.id
            ))
            conn.commit()
    
    def _log_execution(self, rule_id: str, execution_time: datetime, success: bool,
                      output: str, error_message: Optional[str], duration: float):
        """Log rule execution."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO automation_logs 
                (id, rule_id, execution_time, success, output, error_message, duration)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), rule_id, execution_time.isoformat(),
                success, output, error_message, duration
            ))
            conn.commit()
    
    def _system_monitoring(self):
        """Monitor system for events and conditions."""
        while self.monitoring_active:
            try:
                # Check for system events
                self._check_system_events()
                
                # Check conditional rules
                self._check_conditional_rules()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in system monitoring: {e}")
                time.sleep(60)
    
    def _check_system_events(self):
        """Check for system events and trigger listeners."""
        # Check for network availability
        if self._is_network_available():
            for listener in self.event_listeners[EventType.NETWORK_AVAILABLE]:
                listener()
        
        # Check for disk space
        if self._is_disk_space_low():
            for listener in self.event_listeners[EventType.DISK_SPACE_LOW]:
                listener()
        
        # Check for high CPU usage
        if self._is_high_cpu_usage():
            for listener in self.event_listeners[EventType.HIGH_CPU_USAGE]:
                listener()
    
    def _check_conditional_rules(self):
        """Check conditional rules and execute if conditions are met."""
        for rule in self.rules.values():
            if rule.trigger_type == TriggerType.CONDITION and rule.conditions:
                if self._evaluate_conditions(rule.conditions):
                    self._execute_rule(rule.id)
    
    def _evaluate_conditions(self, conditions: List[Dict]) -> bool:
        """Evaluate conditions for a rule."""
        for condition in conditions:
            if not self._evaluate_single_condition(condition):
                return False
        return True
    
    def _evaluate_single_condition(self, condition: Dict) -> bool:
        """Evaluate a single condition."""
        condition_type = condition['type']
        operator = condition['operator']
        value = condition['value']
        field = condition.get('field')
        
        if condition_type == 'system_specs':
            return self._evaluate_system_condition(operator, field, value)
        elif condition_type == 'time':
            return self._evaluate_time_condition(operator, value)
        elif condition_type == 'network':
            return self._evaluate_network_condition(operator, value)
        elif condition_type == 'custom':
            return self._evaluate_custom_condition(operator, value)
        
        return False
    
    def _evaluate_system_condition(self, operator: str, field: Optional[str], value: Any) -> bool:
        """Evaluate system-related conditions."""
        if field == 'cpu_usage':
            current_value = psutil.cpu_percent()
        elif field == 'memory_usage':
            current_value = psutil.virtual_memory().percent
        elif field == 'disk_usage':
            current_value = psutil.disk_usage('/').percent
        else:
            return False
        
        return self._compare_values(current_value, operator, value)
    
    def _evaluate_time_condition(self, operator: str, value: Any) -> bool:
        """Evaluate time-related conditions."""
        now = datetime.now()
        
        if operator == 'between':
            start_time, end_time = value
            return start_time <= now.time() <= end_time
        elif operator == 'weekday':
            return now.weekday() in value
        elif operator == 'month':
            return now.month in value
        
        return False
    
    def _evaluate_network_condition(self, operator: str, value: Any) -> bool:
        """Evaluate network-related conditions."""
        if operator == 'available':
            return self._is_network_available()
        elif operator == 'speed':
            # Simplified network speed check
            return True  # Implement actual speed measurement
        
        return False
    
    def _evaluate_custom_condition(self, operator: str, value: Any) -> bool:
        """Evaluate custom conditions."""
        # This can be extended with custom condition logic
        return True
    
    def _compare_values(self, current: Any, operator: str, target: Any) -> bool:
        """Compare values using the specified operator."""
        if operator == '>':
            return current > target
        elif operator == '<':
            return current < target
        elif operator == '==':
            return current == target
        elif operator == '!=':
            return current != target
        elif operator == '>=':
            return current >= target
        elif operator == '<=':
            return current <= target
        elif operator == 'contains':
            return target in current
        elif operator == 'exists':
            return current is not None
        
        return False
    
    def _is_network_available(self) -> bool:
        """Check if network is available."""
        try:
            import urllib.request
            urllib.request.urlopen('http://www.google.com', timeout=3)
            return True
        except:
            return False
    
    def _is_disk_space_low(self, threshold: float = 90.0) -> bool:
        """Check if disk space is low."""
        return psutil.disk_usage('/').percent > threshold
    
    def _is_high_cpu_usage(self, threshold: float = 80.0) -> bool:
        """Check if CPU usage is high."""
        return psutil.cpu_percent() > threshold
    
    def start(self):
        """Start the automation scheduler."""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("Automation scheduler started")
    
    def stop(self):
        """Stop the automation scheduler."""
        self.running = False
        self.monitoring_active = False
        self.logger.info("Automation scheduler stopped")
    
    def _run_scheduler(self):
        """Run the scheduler loop."""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"Error in scheduler: {e}")
                time.sleep(5)
    
    def get_rules(self) -> List[AutomationRule]:
        """Get all automation rules."""
        return list(self.rules.values())
    
    def get_rule(self, rule_id: str) -> Optional[AutomationRule]:
        """Get a specific automation rule."""
        return self.rules.get(rule_id)
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete an automation rule."""
        if rule_id not in self.rules:
            return False
        
        # Remove from database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM automation_rules WHERE id = ?', [rule_id])
            conn.commit()
        
        # Remove from memory
        del self.rules[rule_id]
        
        return True
    
    def enable_rule(self, rule_id: str) -> bool:
        """Enable an automation rule."""
        if rule_id not in self.rules:
            return False
        
        rule = self.rules[rule_id]
        rule.enabled = True
        rule.updated_at = datetime.now()
        
        self._update_rule(rule)
        return True
    
    def disable_rule(self, rule_id: str) -> bool:
        """Disable an automation rule."""
        if rule_id not in self.rules:
            return False
        
        rule = self.rules[rule_id]
        rule.enabled = False
        rule.updated_at = datetime.now()
        
        self._update_rule(rule)
        return True
    
    def get_execution_logs(self, rule_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get execution logs."""
        with sqlite3.connect(self.db_path) as conn:
            if rule_id:
                cursor = conn.execute('''
                    SELECT * FROM automation_logs 
                    WHERE rule_id = ? 
                    ORDER BY execution_time DESC 
                    LIMIT ?
                ''', [rule_id, limit])
            else:
                cursor = conn.execute('''
                    SELECT * FROM automation_logs 
                    ORDER BY execution_time DESC 
                    LIMIT ?
                ''', [limit])
            
            logs = []
            for row in cursor.fetchall():
                logs.append({
                    'id': row[0],
                    'rule_id': row[1],
                    'execution_time': row[2],
                    'success': row[3],
                    'output': row[4],
                    'error_message': row[5],
                    'duration': row[6]
                })
            
            return logs

# Global scheduler instance
automation_scheduler = AutomationScheduler() 