#!/usr/bin/env python3
"""
Advanced Configuration Management System
Provides versioning, templates, environment-specific configs, and validation
"""

import json
import yaml
import toml
import os
import shutil
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import git
import sqlite3
import uuid
from enum import Enum
import jsonschema
from copy import deepcopy

class ConfigFormat(Enum):
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    INI = "ini"

@dataclass
class ConfigVersion:
    """Represents a configuration version."""
    id: str
    name: str
    description: str
    config_data: Dict
    format: ConfigFormat
    created_at: datetime
    created_by: str
    tags: List[str]
    is_template: bool = False
    parent_version: Optional[str] = None
    checksum: str = ""

@dataclass
class ConfigTemplate:
    """Represents a configuration template."""
    id: str
    name: str
    description: str
    template_data: Dict
    variables: List[str]
    format: ConfigFormat
    category: str
    created_at: datetime
    usage_count: int = 0

@dataclass
class EnvironmentConfig:
    """Represents environment-specific configuration."""
    environment: str
    base_config: str
    overrides: Dict
    variables: Dict[str, str]
    conditions: List[Dict]

class ConfigValidator:
    """Configuration validation engine."""
    
    def __init__(self):
        self.schemas = {}
        self._load_default_schemas()
    
    def _load_default_schemas(self):
        """Load default validation schemas."""
        self.schemas['apps'] = {
            "type": "object",
            "properties": {
                "apps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "manager": {"type": "string"},
                            "package": {"type": "string"},
                            "version": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "priority": {"type": "integer"},
                            "arguments": {"type": "array", "items": {"type": "string"}},
                            "pre_install": {"type": "string"},
                            "post_install": {"type": "string"},
                            "dependencies": {"type": "array", "items": {"type": "string"}},
                            "conditions": {"type": "object"}
                        },
                        "required": ["name", "manager", "package"]
                    }
                },
                "settings": {
                    "type": "object",
                    "properties": {
                        "workers": {"type": "integer"},
                        "timeout": {"type": "integer"},
                        "retry_attempts": {"type": "integer"},
                        "log_level": {"type": "string"}
                    }
                }
            },
            "required": ["apps"]
        }
    
    def validate_config(self, config_data: Dict, schema_name: str = 'apps') -> List[str]:
        """Validate configuration against schema."""
        errors = []
        
        if schema_name not in self.schemas:
            errors.append(f"Schema '{schema_name}' not found")
            return errors
        
        try:
            jsonschema.validate(config_data, self.schemas[schema_name])
        except jsonschema.ValidationError as e:
            errors.append(f"Validation error: {e.message}")
        except Exception as e:
            errors.append(f"Validation failed: {str(e)}")
        
        return errors
    
    def add_schema(self, name: str, schema: Dict):
        """Add a custom validation schema."""
        self.schemas[name] = schema
    
    def get_schema(self, name: str) -> Optional[Dict]:
        """Get a validation schema."""
        return self.schemas.get(name)

class ConfigManager:
    """Advanced configuration management system."""
    
    def __init__(self, config_dir: str = "configs", db_path: str = "config_manager.db"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.validator = ConfigValidator()
        self.versions: Dict[str, ConfigVersion] = {}
        self.templates: Dict[str, ConfigTemplate] = {}
        self.environments: Dict[str, EnvironmentConfig] = {}
        
        # Initialize database
        self._init_database()
        
        # Load existing data
        self._load_versions()
        self._load_templates()
        self._load_environments()
        
        # Initialize git repository if not exists
        self._init_git_repo()
    
    def _init_database(self):
        """Initialize configuration management database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS config_versions (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    config_data TEXT,
                    format TEXT,
                    created_at TEXT,
                    created_by TEXT,
                    tags TEXT,
                    is_template BOOLEAN,
                    parent_version TEXT,
                    checksum TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS config_templates (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    template_data TEXT,
                    variables TEXT,
                    format TEXT,
                    category TEXT,
                    created_at TEXT,
                    usage_count INTEGER
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS environment_configs (
                    environment TEXT PRIMARY KEY,
                    base_config TEXT,
                    overrides TEXT,
                    variables TEXT,
                    conditions TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS config_history (
                    id TEXT PRIMARY KEY,
                    config_id TEXT,
                    action TEXT,
                    timestamp TEXT,
                    user TEXT,
                    changes TEXT
                )
            ''')
            
            conn.commit()
    
    def _init_git_repo(self):
        """Initialize git repository for version control."""
        git_dir = self.config_dir / ".git"
        if not git_dir.exists():
            try:
                repo = git.Repo.init(self.config_dir)
                self.logger.info("Initialized git repository for configuration versioning")
            except Exception as e:
                self.logger.warning(f"Could not initialize git repository: {e}")
    
    def _load_versions(self):
        """Load configuration versions from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM config_versions')
            for row in cursor.fetchall():
                version = ConfigVersion(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    config_data=json.loads(row[3]),
                    format=ConfigFormat(row[4]),
                    created_at=datetime.fromisoformat(row[5]),
                    created_by=row[6],
                    tags=json.loads(row[7]),
                    is_template=row[8],
                    parent_version=row[9],
                    checksum=row[10]
                )
                self.versions[version.id] = version
    
    def _load_templates(self):
        """Load configuration templates from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM config_templates')
            for row in cursor.fetchall():
                template = ConfigTemplate(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    template_data=json.loads(row[3]),
                    variables=json.loads(row[4]),
                    format=ConfigFormat(row[5]),
                    category=row[6],
                    created_at=datetime.fromisoformat(row[7]),
                    usage_count=row[8]
                )
                self.templates[template.id] = template
    
    def _load_environments(self):
        """Load environment configurations from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM environment_configs')
            for row in cursor.fetchall():
                env_config = EnvironmentConfig(
                    environment=row[0],
                    base_config=row[1],
                    overrides=json.loads(row[2]),
                    variables=json.loads(row[3]),
                    conditions=json.loads(row[4])
                )
                self.environments[env_config.environment] = env_config
    
    def create_version(self, name: str, description: str, config_data: Dict,
                      format: ConfigFormat = ConfigFormat.JSON, created_by: str = "system",
                      tags: List[str] = None, parent_version: Optional[str] = None) -> str:
        """Create a new configuration version."""
        # Validate configuration
        errors = self.validator.validate_config(config_data)
        if errors:
            raise ValueError(f"Configuration validation failed: {errors}")
        
        version_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Calculate checksum
        config_str = json.dumps(config_data, sort_keys=True)
        checksum = hashlib.sha256(config_str.encode()).hexdigest()
        
        version = ConfigVersion(
            id=version_id,
            name=name,
            description=description,
            config_data=config_data,
            format=format,
            created_at=now,
            created_by=created_by,
            tags=tags or [],
            parent_version=parent_version,
            checksum=checksum
        )
        
        # Save to database
        self._save_version(version)
        self.versions[version_id] = version
        
        # Save to file system
        self._save_version_file(version)
        
        # Commit to git
        self._git_commit(f"Add configuration version: {name}")
        
        # Log history
        self._log_history(version_id, "create", created_by, {"name": name, "description": description})
        
        return version_id
    
    def create_template(self, name: str, description: str, template_data: Dict,
                       variables: List[str], format: ConfigFormat = ConfigFormat.JSON,
                       category: str = "general") -> str:
        """Create a configuration template."""
        template_id = str(uuid.uuid4())
        now = datetime.now()
        
        template = ConfigTemplate(
            id=template_id,
            name=name,
            description=description,
            template_data=template_data,
            variables=variables,
            format=format,
            category=category,
            created_at=now
        )
        
        # Save to database
        self._save_template(template)
        self.templates[template_id] = template
        
        return template_id
    
    def create_environment_config(self, environment: str, base_config: str,
                                overrides: Dict = None, variables: Dict[str, str] = None,
                                conditions: List[Dict] = None) -> str:
        """Create environment-specific configuration."""
        env_config = EnvironmentConfig(
            environment=environment,
            base_config=base_config,
            overrides=overrides or {},
            variables=variables or {},
            conditions=conditions or []
        )
        
        # Save to database
        self._save_environment_config(env_config)
        self.environments[environment] = env_config
        
        return environment
    
    def instantiate_template(self, template_id: str, variables: Dict[str, str],
                           name: str, description: str, created_by: str = "system") -> str:
        """Instantiate a template with variables."""
        if template_id not in self.templates:
            raise ValueError(f"Template {template_id} not found")
        
        template = self.templates[template_id]
        
        # Check if all required variables are provided
        missing_vars = set(template.variables) - set(variables.keys())
        if missing_vars:
            raise ValueError(f"Missing required variables: {missing_vars}")
        
        # Instantiate template
        config_data = deepcopy(template.template_data)
        config_str = json.dumps(config_data)
        
        for var_name, var_value in variables.items():
            config_str = config_str.replace(f"${{{var_name}}}", str(var_value))
        
        config_data = json.loads(config_str)
        
        # Create version from instantiated template
        version_id = self.create_version(
            name=name,
            description=description,
            config_data=config_data,
            format=template.format,
            created_by=created_by,
            tags=[f"template:{template.name}"]
        )
        
        # Update template usage count
        template.usage_count += 1
        self._update_template(template)
        
        return version_id
    
    def get_config_for_environment(self, environment: str, variables: Dict[str, str] = None) -> Dict:
        """Get configuration for a specific environment."""
        if environment not in self.environments:
            raise ValueError(f"Environment {environment} not found")
        
        env_config = self.environments[environment]
        
        # Get base configuration
        if env_config.base_config not in self.versions:
            raise ValueError(f"Base configuration {env_config.base_config} not found")
        
        base_version = self.versions[env_config.base_config]
        config_data = deepcopy(base_version.config_data)
        
        # Apply overrides
        self._apply_overrides(config_data, env_config.overrides)
        
        # Apply variables
        if variables:
            self._apply_variables(config_data, variables)
        
        # Apply environment variables
        self._apply_variables(config_data, env_config.variables)
        
        return config_data
    
    def _apply_overrides(self, config_data: Dict, overrides: Dict):
        """Apply configuration overrides."""
        for key, value in overrides.items():
            if isinstance(value, dict) and key in config_data and isinstance(config_data[key], dict):
                config_data[key].update(value)
            else:
                config_data[key] = value
    
    def _apply_variables(self, config_data: Dict, variables: Dict[str, str]):
        """Apply variables to configuration."""
        config_str = json.dumps(config_data)
        
        for var_name, var_value in variables.items():
            config_str = config_str.replace(f"${{{var_name}}}", str(var_value))
        
        config_data.clear()
        config_data.update(json.loads(config_str))
    
    def export_config(self, version_id: str, format: ConfigFormat = None, 
                     output_path: str = None) -> str:
        """Export configuration to file."""
        if version_id not in self.versions:
            raise ValueError(f"Version {version_id} not found")
        
        version = self.versions[version_id]
        export_format = format or version.format
        
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = f"configs/export_{version.name}_{timestamp}.{export_format.value}"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)
        
        if export_format == ConfigFormat.JSON:
            with open(output_path, 'w') as f:
                json.dump(version.config_data, f, indent=2)
        elif export_format == ConfigFormat.YAML:
            with open(output_path, 'w') as f:
                yaml.dump(version.config_data, f, default_flow_style=False)
        elif export_format == ConfigFormat.TOML:
            with open(output_path, 'w') as f:
                toml.dump(version.config_data, f)
        
        return str(output_path)
    
    def import_config(self, file_path: str, name: str, description: str,
                     format: ConfigFormat = None, created_by: str = "system") -> str:
        """Import configuration from file."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file {file_path} not found")
        
        # Detect format if not specified
        if not format:
            if file_path.suffix.lower() == '.json':
                format = ConfigFormat.JSON
            elif file_path.suffix.lower() in ['.yml', '.yaml']:
                format = ConfigFormat.YAML
            elif file_path.suffix.lower() == '.toml':
                format = ConfigFormat.TOML
            else:
                format = ConfigFormat.JSON
        
        # Load configuration
        with open(file_path, 'r') as f:
            if format == ConfigFormat.JSON:
                config_data = json.load(f)
            elif format == ConfigFormat.YAML:
                config_data = yaml.safe_load(f)
            elif format == ConfigFormat.TOML:
                config_data = toml.load(f)
        
        # Create version
        return self.create_version(
            name=name,
            description=description,
            config_data=config_data,
            format=format,
            created_by=created_by,
            tags=[f"imported:{file_path.name}"]
        )
    
    def diff_versions(self, version1_id: str, version2_id: str) -> Dict:
        """Compare two configuration versions."""
        if version1_id not in self.versions or version2_id not in self.versions:
            raise ValueError("One or both versions not found")
        
        v1 = self.versions[version1_id]
        v2 = self.versions[version2_id]
        
        # Simple diff implementation
        diff = {
            'added': {},
            'removed': {},
            'modified': {},
            'unchanged': {}
        }
        
        # Compare configurations
        self._compare_dicts(v1.config_data, v2.config_data, diff)
        
        return diff
    
    def _compare_dicts(self, dict1: Dict, dict2: Dict, diff: Dict, path: str = ""):
        """Recursively compare dictionaries."""
        all_keys = set(dict1.keys()) | set(dict2.keys())
        
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            
            if key not in dict1:
                # Added in dict2
                self._set_nested(diff['added'], current_path, dict2[key])
            elif key not in dict2:
                # Removed from dict1
                self._set_nested(diff['removed'], current_path, dict1[key])
            elif dict1[key] != dict2[key]:
                # Modified
                if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                    self._compare_dicts(dict1[key], dict2[key], diff, current_path)
                else:
                    self._set_nested(diff['modified'], current_path, {
                        'old': dict1[key],
                        'new': dict2[key]
                    })
            else:
                # Unchanged
                self._set_nested(diff['unchanged'], current_path, dict1[key])
    
    def _set_nested(self, d: Dict, path: str, value: Any):
        """Set value in nested dictionary using dot notation."""
        keys = path.split('.')
        current = d
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _save_version(self, version: ConfigVersion):
        """Save version to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO config_versions 
                (id, name, description, config_data, format, created_at, created_by,
                 tags, is_template, parent_version, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                version.id, version.name, version.description,
                json.dumps(version.config_data), version.format.value,
                version.created_at.isoformat(), version.created_by,
                json.dumps(version.tags), version.is_template,
                version.parent_version, version.checksum
            ))
            conn.commit()
    
    def _save_template(self, template: ConfigTemplate):
        """Save template to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO config_templates 
                (id, name, description, template_data, variables, format, category, created_at, usage_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                template.id, template.name, template.description,
                json.dumps(template.template_data), json.dumps(template.variables),
                template.format.value, template.category,
                template.created_at.isoformat(), template.usage_count
            ))
            conn.commit()
    
    def _save_environment_config(self, env_config: EnvironmentConfig):
        """Save environment configuration to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO environment_configs 
                (environment, base_config, overrides, variables, conditions)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                env_config.environment, env_config.base_config,
                json.dumps(env_config.overrides), json.dumps(env_config.variables),
                json.dumps(env_config.conditions)
            ))
            conn.commit()
    
    def _update_template(self, template: ConfigTemplate):
        """Update template in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE config_templates 
                SET usage_count = ?
                WHERE id = ?
            ''', (template.usage_count, template.id))
            conn.commit()
    
    def _save_version_file(self, version: ConfigVersion):
        """Save version to file system."""
        file_path = self.config_dir / f"{version.name}_{version.id}.{version.format.value}"
        
        with open(file_path, 'w') as f:
            if version.format == ConfigFormat.JSON:
                json.dump(version.config_data, f, indent=2)
            elif version.format == ConfigFormat.YAML:
                yaml.dump(version.config_data, f, default_flow_style=False)
            elif version.format == ConfigFormat.TOML:
                toml.dump(version.config_data, f)
    
    def _git_commit(self, message: str):
        """Commit changes to git repository."""
        try:
            repo = git.Repo(self.config_dir)
            repo.index.add('*')
            repo.index.commit(message)
        except Exception as e:
            self.logger.warning(f"Could not commit to git: {e}")
    
    def _log_history(self, config_id: str, action: str, user: str, changes: Dict):
        """Log configuration history."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO config_history 
                (id, config_id, action, timestamp, user, changes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()), config_id, action,
                datetime.now().isoformat(), user, json.dumps(changes)
            ))
            conn.commit()
    
    def get_versions(self, tags: List[str] = None) -> List[ConfigVersion]:
        """Get configuration versions, optionally filtered by tags."""
        versions = list(self.versions.values())
        
        if tags:
            versions = [v for v in versions if any(tag in v.tags for tag in tags)]
        
        return sorted(versions, key=lambda v: v.created_at, reverse=True)
    
    def get_templates(self, category: str = None) -> List[ConfigTemplate]:
        """Get configuration templates, optionally filtered by category."""
        templates = list(self.templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        return sorted(templates, key=lambda t: t.usage_count, reverse=True)
    
    def get_environments(self) -> List[str]:
        """Get available environments."""
        return list(self.environments.keys())
    
    def get_history(self, config_id: str = None, limit: int = 100) -> List[Dict]:
        """Get configuration history."""
        with sqlite3.connect(self.db_path) as conn:
            if config_id:
                cursor = conn.execute('''
                    SELECT * FROM config_history 
                    WHERE config_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', [config_id, limit])
            else:
                cursor = conn.execute('''
                    SELECT * FROM config_history 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', [limit])
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'id': row[0],
                    'config_id': row[1],
                    'action': row[2],
                    'timestamp': row[3],
                    'user': row[4],
                    'changes': json.loads(row[5])
                })
            
            return history

# Global configuration manager instance
config_manager = ConfigManager() 