"""
Configuration management API endpoints.
"""
from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
from flask_login import current_user

from security.authentication import enhanced_login_required, role_required_api
from config import config_manager
from config.secrets import secrets_manager
from api.errors import APIError

# Create namespace
config_ns = Namespace('config', description='Configuration management operations')

# Response models
config_source_model = config_ns.model('ConfigSource', {
    'name': fields.String(description='Source name'),
    'path': fields.String(description='File path'),
    'priority': fields.Integer(description='Priority level'),
    'is_valid': fields.Boolean(description='Whether source is valid'),
    'error_message': fields.String(description='Error message if invalid'),
    'last_modified': fields.String(description='Last modification time'),
    'keys_count': fields.Integer(description='Number of configuration keys')
})

config_status_model = config_ns.model('ConfigStatus', {
    'sources': fields.List(fields.Nested(config_source_model), description='Configuration sources'),
    'merged_config_keys': fields.List(fields.String, description='Available configuration keys'),
    'watchers_active': fields.Boolean(description='Whether file watchers are active'),
    'reload_callbacks': fields.Integer(description='Number of reload callbacks')
})

config_value_model = config_ns.model('ConfigValue', {
    'key': fields.String(description='Configuration key'),
    'value': fields.Raw(description='Configuration value'),
    'source': fields.String(description='Source of the value')
})

secrets_status_model = config_ns.model('SecretsStatus', {
    'vault_available': fields.Boolean(description='Whether Vault is available'),
    'local_available': fields.Boolean(description='Whether local storage is available'),
    'cached_secrets': fields.Integer(description='Number of cached secrets'),
    'rotation_enabled': fields.Boolean(description='Whether rotation is enabled'),
    'scheduled_rotations': fields.Integer(description='Number of scheduled rotations'),
    'next_rotation': fields.String(description='Next rotation time')
})


@config_ns.route('/status')
class ConfigStatusResource(Resource):
    """Configuration system status."""
    
    @config_ns.marshal_with(config_status_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get configuration system status."""
        try:
            return config_manager.get_status(), 200
            
        except Exception as e:
            raise APIError(f"Failed to get config status: {str(e)}", 500)


@config_ns.route('/reload')
class ConfigReloadResource(Resource):
    """Configuration reload endpoint."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Reload configuration from all sources."""
        try:
            config_manager.reload_configuration()
            return {'message': 'Configuration reloaded successfully'}, 200
            
        except Exception as e:
            raise APIError(f"Failed to reload configuration: {str(e)}", 500)


@config_ns.route('/get/<string:key>')
class ConfigGetResource(Resource):
    """Get configuration value."""
    
    @config_ns.marshal_with(config_value_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self, key):
        """Get configuration value by key."""
        try:
            value = config_manager.get(key)
            
            if value is None:
                return {'message': f'Configuration key not found: {key}'}, 404
            
            return {
                'key': key,
                'value': value,
                'source': 'merged'
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get configuration: {str(e)}", 500)


@config_ns.route('/set')
class ConfigSetResource(Resource):
    """Set configuration value."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Set configuration value at runtime."""
        try:
            data = request.get_json()
            
            if not data or 'key' not in data or 'value' not in data:
                return {'message': 'Key and value are required'}, 400
            
            key = data['key']
            value = data['value']
            source = data.get('source', 'runtime')
            
            config_manager.set(key, value, source)
            
            return {
                'message': f'Configuration updated: {key}',
                'key': key,
                'value': value,
                'source': source
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to set configuration: {str(e)}", 500)


@config_ns.route('/export')
class ConfigExportResource(Resource):
    """Export configuration."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Export current configuration."""
        try:
            format_type = request.args.get('format', 'yaml').lower()
            include_sensitive = request.args.get('include_sensitive', 'false').lower() == 'true'
            
            if format_type not in ['yaml', 'json']:
                return {'message': 'Format must be yaml or json'}, 400
            
            exported_config = config_manager.export_config(format_type, include_sensitive)
            
            return {
                'format': format_type,
                'include_sensitive': include_sensitive,
                'config': exported_config
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to export configuration: {str(e)}", 500)


@config_ns.route('/validate')
class ConfigValidateResource(Resource):
    """Validate configuration."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Validate configuration data."""
        try:
            data = request.get_json()
            
            if not data:
                return {'message': 'Configuration data is required'}, 400
            
            # Validate the configuration
            validated_config = config_manager.validate_configuration(data)
            
            return {
                'message': 'Configuration is valid',
                'validated_config': validated_config
            }, 200
            
        except Exception as e:
            return {
                'message': 'Configuration validation failed',
                'errors': str(e)
            }, 400


@config_ns.route('/keys')
class ConfigKeysResource(Resource):
    """List configuration keys."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get list of all configuration keys."""
        try:
            def get_all_keys(config, prefix=''):
                """Recursively get all configuration keys."""
                keys = []
                
                for key, value in config.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    keys.append(full_key)
                    
                    if isinstance(value, dict):
                        keys.extend(get_all_keys(value, full_key))
                
                return keys
            
            all_keys = get_all_keys(config_manager.merged_config)
            
            return {
                'keys': sorted(all_keys),
                'total_keys': len(all_keys)
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get configuration keys: {str(e)}", 500)


@config_ns.route('/search')
class ConfigSearchResource(Resource):
    """Search configuration keys and values."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Search configuration by key or value."""
        try:
            query = request.args.get('q', '').lower()
            search_values = request.args.get('search_values', 'false').lower() == 'true'
            
            if not query:
                return {'message': 'Query parameter is required'}, 400
            
            def search_config(config, prefix=''):
                """Recursively search configuration."""
                results = []
                
                for key, value in config.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    
                    # Search in key
                    if query in key.lower() or query in full_key.lower():
                        results.append({
                            'key': full_key,
                            'value': value,
                            'match_type': 'key'
                        })
                    
                    # Search in value if enabled
                    elif search_values and isinstance(value, str) and query in value.lower():
                        results.append({
                            'key': full_key,
                            'value': value,
                            'match_type': 'value'
                        })
                    
                    # Recurse into nested dictionaries
                    if isinstance(value, dict):
                        results.extend(search_config(value, full_key))
                
                return results
            
            results = search_config(config_manager.merged_config)
            
            return {
                'query': query,
                'search_values': search_values,
                'results': results,
                'total_matches': len(results)
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to search configuration: {str(e)}", 500)


@config_ns.route('/defaults')
class ConfigDefaultsResource(Resource):
    """Create default configuration files."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Create default configuration files."""
        try:
            config_manager.create_default_configs()
            
            return {
                'message': 'Default configuration files created successfully',
                'config_directory': str(config_manager.base_path)
            }, 201
            
        except Exception as e:
            raise APIError(f"Failed to create default configs: {str(e)}", 500)


@config_ns.route('/secrets/status')
class SecretsStatusResource(Resource):
    """Secrets management status."""
    
    @config_ns.marshal_with(secrets_status_model)
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """Get secrets management status."""
        try:
            return secrets_manager.get_status(), 200
            
        except Exception as e:
            raise APIError(f"Failed to get secrets status: {str(e)}", 500)


@config_ns.route('/secrets/<string:key>')
class SecretResource(Resource):
    """Individual secret management."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self, key):
        """Get secret value (returns masked value for security)."""
        try:
            value = secrets_manager.get_secret(key)
            
            if value is None:
                return {'message': f'Secret not found: {key}'}, 404
            
            # Return masked value for security
            if isinstance(value, str):
                masked_value = value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '***'
            else:
                masked_value = '***'
            
            return {
                'key': key,
                'value': masked_value,
                'exists': True
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to get secret: {str(e)}", 500)
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def put(self, key):
        """Store secret value."""
        try:
            data = request.get_json()
            
            if not data or 'value' not in data:
                return {'message': 'Secret value is required'}, 400
            
            value = data['value']
            backend = data.get('backend', 'auto')
            
            success = secrets_manager.put_secret(key, value, backend)
            
            if success:
                return {
                    'message': f'Secret stored successfully: {key}',
                    'key': key,
                    'backend': backend
                }, 200
            else:
                return {'message': f'Failed to store secret: {key}'}, 500
                
        except Exception as e:
            raise APIError(f"Failed to store secret: {str(e)}", 500)
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def delete(self, key):
        """Delete secret."""
        try:
            backend = request.args.get('backend', 'all')
            success = secrets_manager.delete_secret(key, backend)
            
            if success:
                return {'message': f'Secret deleted successfully: {key}'}, 200
            else:
                return {'message': f'Failed to delete secret: {key}'}, 500
                
        except Exception as e:
            raise APIError(f"Failed to delete secret: {str(e)}", 500)


@config_ns.route('/secrets')
class SecretsListResource(Resource):
    """List secrets."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def get(self):
        """List all secret keys."""
        try:
            backend = request.args.get('backend', 'all')
            secrets = secrets_manager.list_secrets(backend)
            
            return {
                'secrets': secrets,
                'total': len(secrets),
                'backend': backend
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to list secrets: {str(e)}", 500)


@config_ns.route('/secrets/cache/clear')
class SecretsCacheClearResource(Resource):
    """Clear secrets cache."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self):
        """Clear the secrets cache."""
        try:
            secrets_manager.clear_cache()
            return {'message': 'Secrets cache cleared successfully'}, 200
            
        except Exception as e:
            raise APIError(f"Failed to clear secrets cache: {str(e)}", 500)


@config_ns.route('/secrets/<string:key>/rotate')
class SecretRotationResource(Resource):
    """Secret rotation management."""
    
    @enhanced_login_required
    @role_required_api(['Admin'])
    def post(self, key):
        """Schedule secret rotation."""
        try:
            data = request.get_json() or {}
            interval_days = data.get('interval_days', 30)
            
            from datetime import timedelta
            secrets_manager.schedule_rotation(key, timedelta(days=interval_days))
            
            return {
                'message': f'Secret rotation scheduled for {key}',
                'interval_days': interval_days
            }, 200
            
        except Exception as e:
            raise APIError(f"Failed to schedule rotation: {str(e)}", 500)
