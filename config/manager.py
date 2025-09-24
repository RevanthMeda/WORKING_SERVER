"""
Hierarchical configuration management system for SAT Report Generator.
"""
import os
import yaml
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from marshmallow import Schema, fields, ValidationError, validate
from flask import current_app

logger = logging.getLogger(__name__)


@dataclass
class ConfigSource:
    """Configuration source metadata."""
    name: str
    path: Optional[str] = None
    priority: int = 0
    last_modified: Optional[datetime] = None
    data: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    error_message: Optional[str] = None


class ConfigValidationSchema(Schema):
    """Schema for validating configuration structure."""
    
    class Meta:
        # Allow unknown fields to be passed through
        unknown = 'INCLUDE'
    
    # Application settings
    app_name = fields.Str(load_default='SAT Report Generator')
    port = fields.Int(validate=validate.Range(min=1, max=65535), load_default=5000)
    debug = fields.Bool(load_default=False)
    environment = fields.Str(validate=validate.OneOf(['development', 'testing', 'staging', 'production']), load_default='development')
    
    # Security settings
    secret_key = fields.Str(required=True, validate=validate.Length(min=32))
    session_timeout = fields.Int(validate=validate.Range(min=300, max=86400), load_default=1800)  # 5 min to 24 hours
    csrf_enabled = fields.Bool(load_default=True)
    
    # Database settings
    database = fields.Dict(load_default=lambda: {
        'uri': 'sqlite:///instance/database.db',
        'pool_size': 10,
        'pool_timeout': 30,
        'pool_recycle': 3600
    })
    
    # Email settings
    email = fields.Dict(load_default=lambda: {
        'smtp_server': 'localhost',
        'smtp_port': 587,
        'use_tls': True,
        'username': '',
        'password': '',
        'default_sender': ''
    })
    
    # File upload settings
    uploads = fields.Dict(load_default=lambda: {
        'max_file_size': 16777216,  # 16MB
        'allowed_extensions': ['png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'],
        'upload_path': 'static/uploads'
    })
    
    # Logging settings
    logging = fields.Dict(load_default=lambda: {
        'level': 'INFO',
        'format': '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
        'file': 'logs/app.log',
        'max_bytes': 10485760,  # 10MB
        'backup_count': 5
    })
    
    # Feature flags
    features = fields.Dict(load_default=lambda: {
        'email_notifications': True,
        'pdf_export': False,
        'api_enabled': True,
        'metrics_enabled': True
    })
    
    # Additional fields that may be present in the config
    api = fields.Dict(load_default={})
    ssl = fields.Dict(load_default={})
    backup = fields.Dict(load_default={})
    approvers = fields.List(fields.Dict(), load_default=[])
    monitoring = fields.Dict(load_default={})
    cache = fields.Dict(load_default={})
    security = fields.Dict(load_default={})
    session = fields.Dict(load_default={})
    templates = fields.Dict(load_default={})


class ConfigFileWatcher(FileSystemEventHandler):
    """Watch configuration files for changes."""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.debounce_time = 1.0  # 1 second debounce
        self.last_reload = {}
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Check if this is a config file
        if not any(file_path.endswith(ext) for ext in ['.yaml', '.yml', '.json', '.env']):
            return
        
        # Debounce rapid file changes
        now = time.time()
        if file_path in self.last_reload:
            if now - self.last_reload[file_path] < self.debounce_time:
                return
        
        self.last_reload[file_path] = now
        
        logger.info(f"Configuration file changed: {file_path}")
        
        # Reload configuration in a separate thread to avoid blocking
        threading.Thread(
            target=self.config_manager.reload_configuration,
            args=(file_path,),
            daemon=True
        ).start()


class HierarchicalConfigManager:
    """Hierarchical configuration management with hot-reloading."""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or 'config')
        self.sources: List[ConfigSource] = []
        self.merged_config: Dict[str, Any] = {}
        self.validation_schema = ConfigValidationSchema()
        self.observers: List[Observer] = []
        self.lock = threading.RLock()
        self.reload_callbacks: List[callable] = []
        
        # Environment variable prefix
        self.env_prefix = 'SAT_'
        
        # Create config directory if it doesn't exist
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def add_source(self, name: str, path: str = None, priority: int = 0) -> ConfigSource:
        """Add a configuration source."""
        source = ConfigSource(name=name, path=path, priority=priority)
        
        if path and os.path.exists(path):
            try:
                source.data = self._load_file(path)
                source.last_modified = datetime.fromtimestamp(os.path.getmtime(path))
                source.is_valid = True
            except Exception as e:
                source.is_valid = False
                source.error_message = str(e)
                logger.error(f"Failed to load config source {name}: {e}")
        
        with self.lock:
            self.sources.append(source)
            # Sort by priority (higher priority first)
            self.sources.sort(key=lambda x: x.priority, reverse=True)
        
        return source
    
    def _load_file(self, file_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        path = Path(file_path)
        
        if not path.exists():
            return {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f) or {}
                elif path.suffix.lower() == '.json':
                    return json.load(f) or {}
                elif path.suffix.lower() == '.env':
                    return self._parse_env_file(f)
                else:
                    logger.warning(f"Unsupported config file format: {path.suffix}")
                    return {}
        except Exception as e:
            logger.error(f"Failed to load config file {file_path}: {e}")
            raise
    
    def _parse_env_file(self, file_handle) -> Dict[str, Any]:
        """Parse .env file format."""
        config = {}
        
        for line in file_handle:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                
                # Convert to nested dict if key contains dots
                if '.' in key:
                    self._set_nested_value(config, key, value)
                else:
                    config[key] = self._convert_value(value)
        
        return config
    
    def _set_nested_value(self, config: Dict, key: str, value: Any):
        """Set nested dictionary value using dot notation."""
        keys = key.split('.')
        current = config
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = self._convert_value(value)
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type."""
        # Boolean conversion
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False
        
        # Number conversion
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def load_environment_variables(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        for key, value in os.environ.items():
            if key.startswith(self.env_prefix):
                # Remove prefix and convert to lowercase
                config_key = key[len(self.env_prefix):].lower()
                
                # Convert to nested dict if key contains underscores
                if '_' in config_key:
                    nested_key = config_key.replace('_', '.')
                    self._set_nested_value(config, nested_key, value)
                else:
                    config[config_key] = self._convert_value(value)
        
        return config
    
    def merge_configurations(self) -> Dict[str, Any]:
        """Merge all configuration sources."""
        merged = {}
        
        with self.lock:
            # Start with lowest priority sources
            for source in reversed(self.sources):
                if source.is_valid and source.data:
                    merged = self._deep_merge(merged, source.data)
            
            # Environment variables have highest priority
            env_config = self.load_environment_variables()
            if env_config:
                merged = self._deep_merge(merged, env_config)
        
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate configuration against schema."""
        try:
            validated_config = self.validation_schema.load(config)
            logger.info("Configuration validation passed")
            return validated_config
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e.messages}")
            raise
    
    def reload_configuration(self, changed_file: str = None):
        """Reload configuration from all sources."""
        try:
            logger.info(f"Reloading configuration (triggered by: {changed_file or 'manual'})")
            
            # Reload specific source if file path provided
            if changed_file:
                with self.lock:
                    for source in self.sources:
                        if source.path == changed_file:
                            try:
                                source.data = self._load_file(changed_file)
                                source.last_modified = datetime.fromtimestamp(os.path.getmtime(changed_file))
                                source.is_valid = True
                                source.error_message = None
                                logger.info(f"Reloaded config source: {source.name}")
                            except Exception as e:
                                source.is_valid = False
                                source.error_message = str(e)
                                logger.error(f"Failed to reload config source {source.name}: {e}")
                            break
            
            # Merge and validate configuration
            merged_config = self.merge_configurations()
            validated_config = self.validate_configuration(merged_config)
            
            with self.lock:
                self.merged_config = validated_config
            
            # Notify callbacks
            for callback in self.reload_callbacks:
                try:
                    callback(validated_config)
                except Exception as e:
                    logger.error(f"Configuration reload callback failed: {e}")
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Configuration reload failed: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        with self.lock:
            return self._get_nested_value(self.merged_config, key, default)
    
    def _get_nested_value(self, config: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Get nested value using dot notation."""
        keys = key.split('.')
        current = config
        
        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any, source_name: str = 'runtime'):
        """Set configuration value at runtime."""
        with self.lock:
            # Find or create runtime source
            runtime_source = None
            for source in self.sources:
                if source.name == source_name:
                    runtime_source = source
                    break
            
            if not runtime_source:
                runtime_source = ConfigSource(name=source_name, priority=1000)  # High priority
                self.sources.append(runtime_source)
                self.sources.sort(key=lambda x: x.priority, reverse=True)
            
            # Set the value
            self._set_nested_value(runtime_source.data, key, value)
            
            # Reload configuration
            self.reload_configuration()
    
    def start_file_watching(self):
        """Start watching configuration files for changes."""
        if not self.observers:
            event_handler = ConfigFileWatcher(self)
            
            # Watch the config directory
            if self.base_path.exists():
                observer = Observer()
                observer.schedule(event_handler, str(self.base_path), recursive=True)
                observer.start()
                self.observers.append(observer)
                logger.info(f"Started watching config directory: {self.base_path}")
            
            # Watch individual config files
            for source in self.sources:
                if source.path and os.path.exists(source.path):
                    file_path = Path(source.path)
                    if file_path.parent != self.base_path:
                        observer = Observer()
                        observer.schedule(event_handler, str(file_path.parent), recursive=False)
                        observer.start()
                        self.observers.append(observer)
                        logger.info(f"Started watching config file: {source.path}")
    
    def stop_file_watching(self):
        """Stop watching configuration files."""
        for observer in self.observers:
            observer.stop()
            observer.join()
        self.observers.clear()
        logger.info("Stopped watching configuration files")
    
    def add_reload_callback(self, callback: callable):
        """Add callback to be called when configuration is reloaded."""
        self.reload_callbacks.append(callback)
    
    def get_status(self) -> Dict[str, Any]:
        """Get configuration manager status."""
        with self.lock:
            return {
                'sources': [
                    {
                        'name': source.name,
                        'path': source.path,
                        'priority': source.priority,
                        'is_valid': source.is_valid,
                        'error_message': source.error_message,
                        'last_modified': source.last_modified.isoformat() if source.last_modified else None,
                        'keys_count': len(source.data) if source.data else 0
                    }
                    for source in self.sources
                ],
                'merged_config_keys': list(self.merged_config.keys()),
                'watchers_active': len(self.observers) > 0,
                'reload_callbacks': len(self.reload_callbacks)
            }
    
    def export_config(self, format: str = 'yaml', include_sensitive: bool = False) -> str:
        """Export current configuration."""
        config_copy = self.merged_config.copy()
        
        if not include_sensitive:
            # Remove sensitive keys
            sensitive_keys = ['secret_key', 'password', 'api_key', 'token']
            config_copy = self._remove_sensitive_keys(config_copy, sensitive_keys)
        
        if format.lower() == 'yaml':
            return yaml.dump(config_copy, default_flow_style=False, indent=2)
        elif format.lower() == 'json':
            return json.dumps(config_copy, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _remove_sensitive_keys(self, config: Dict[str, Any], sensitive_keys: List[str]) -> Dict[str, Any]:
        """Remove sensitive keys from configuration."""
        cleaned = {}
        
        for key, value in config.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                cleaned[key] = '***REDACTED***'
            elif isinstance(value, dict):
                cleaned[key] = self._remove_sensitive_keys(value, sensitive_keys)
            else:
                cleaned[key] = value
        
        return cleaned
    
    def create_default_configs(self):
        """Create default configuration files."""
        # Create default application config
        default_app_config = {
            'app_name': 'SAT Report Generator',
            'port': 5000,
            'debug': False,
            'environment': 'development',
            'secret_key': 'change-this-in-production-' + os.urandom(16).hex(),
            'database': {
                'uri': 'sqlite:///instance/database.db',
                'pool_size': 10,
                'pool_timeout': 30,
                'pool_recycle': 3600
            },
            'email': {
                'smtp_server': 'localhost',
                'smtp_port': 587,
                'use_tls': True,
                'username': '',
                'password': '',
                'default_sender': ''
            },
            'uploads': {
                'max_file_size': 16777216,
                'allowed_extensions': ['png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'],
                'upload_path': 'static/uploads'
            },
            'logging': {
                'level': 'INFO',
                'format': '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
                'file': 'logs/app.log',
                'max_bytes': 10485760,
                'backup_count': 5
            },
            'features': {
                'email_notifications': True,
                'pdf_export': False,
                'api_enabled': True,
                'metrics_enabled': True
            }
        }
        
        # Write default config files
        configs = {
            'app.yaml': default_app_config,
            'development.yaml': {
                'debug': True,
                'logging': {'level': 'DEBUG'},
                'database': {'uri': 'sqlite:///instance/dev.db'}
            },
            'production.yaml': {
                'debug': False,
                'logging': {'level': 'WARNING'},
                'session_timeout': 3600,
                'features': {'metrics_enabled': True}
            }
        }
        
        for filename, config in configs.items():
            config_path = self.base_path / filename
            if not config_path.exists():
                with open(config_path, 'w') as f:
                    yaml.dump(config, f, default_flow_style=False, indent=2)
                logger.info(f"Created default config file: {config_path}")


# Global configuration manager instance
config_manager = HierarchicalConfigManager()


def init_config_system(app, config_dir: str = None):
    """Initialize the hierarchical configuration system."""
    global config_manager
    
    if config_dir:
        config_manager = HierarchicalConfigManager(config_dir)
    
    # Create default config files if they don't exist
    config_manager.create_default_configs()
    
    # Add configuration sources in priority order (lowest to highest)
    config_manager.add_source('defaults', str(config_manager.base_path / 'app.yaml'), priority=0)
    
    # Environment-specific config
    env = os.environ.get('FLASK_ENV', 'development')
    env_config_path = config_manager.base_path / f'{env}.yaml'
    if env_config_path.exists():
        config_manager.add_source(f'{env}_config', str(env_config_path), priority=100)
    
    # Local overrides (highest priority file)
    local_config_path = config_manager.base_path / 'local.yaml'
    if local_config_path.exists():
        config_manager.add_source('local_overrides', str(local_config_path), priority=200)
    
    # Load and merge all configurations
    config_manager.reload_configuration()
    
    # Start file watching for hot-reload
    config_manager.start_file_watching()
    
    # Add Flask app configuration update callback
    def update_flask_config(new_config):
        """Update Flask app configuration when config changes."""
        try:
            # Update Flask config with new values
            app.config.update({
                'SECRET_KEY': new_config.get('secret_key'),
                'DEBUG': new_config.get('debug', False),
                'SQLALCHEMY_DATABASE_URI': new_config.get('database.uri'),
                'MAX_CONTENT_LENGTH': new_config.get('uploads.max_file_size'),
                # Add more mappings as needed
            })
            logger.info("Flask configuration updated from config manager")
        except Exception as e:
            logger.error(f"Failed to update Flask configuration: {e}")
    
    config_manager.add_reload_callback(update_flask_config)
    
    # Store config manager in app
    app.config_manager = config_manager
    
    logger.info("Hierarchical configuration system initialized")
    return config_manager