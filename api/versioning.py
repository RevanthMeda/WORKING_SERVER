"""
API versioning and backward compatibility management.
"""
from flask import request, jsonify, current_app
from functools import wraps
from datetime import datetime, timedelta
import re


class APIVersion:
    """API version representation."""
    
    def __init__(self, major, minor, patch=0):
        self.major = major
        self.minor = minor
        self.patch = patch
    
    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __repr__(self):
        return f"APIVersion({self.major}, {self.minor}, {self.patch})"
    
    def __eq__(self, other):
        if not isinstance(other, APIVersion):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
    
    def __lt__(self, other):
        if not isinstance(other, APIVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __le__(self, other):
        return self == other or self < other
    
    def __gt__(self, other):
        return not self <= other
    
    def __ge__(self, other):
        return not self < other
    
    @classmethod
    def from_string(cls, version_string):
        """Create APIVersion from string like '1.2.3'."""
        match = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?$', version_string)
        if not match:
            raise ValueError(f"Invalid version string: {version_string}")
        
        major = int(match.group(1))
        minor = int(match.group(2))
        patch = int(match.group(3)) if match.group(3) else 0
        
        return cls(major, minor, patch)
    
    def is_compatible_with(self, other):
        """Check if this version is backward compatible with another."""
        if not isinstance(other, APIVersion):
            return False
        
        # Same major version is compatible
        if self.major == other.major:
            return self >= other
        
        # Different major versions are not compatible
        return False


class VersionManager:
    """API version management."""
    
    # Supported API versions
    SUPPORTED_VERSIONS = [
        APIVersion(1, 0, 0),
        # Future versions will be added here
        # APIVersion(1, 1, 0),
        # APIVersion(2, 0, 0),
    ]
    
    # Current/latest version
    CURRENT_VERSION = SUPPORTED_VERSIONS[-1]
    
    # Deprecated versions with sunset dates
    DEPRECATED_VERSIONS = {
        # APIVersion(1, 0, 0): datetime(2024, 12, 31),  # Example
    }
    
    @classmethod
    def get_requested_version(cls):
        """Get the API version requested by the client."""
        # Check Accept header for version
        accept_header = request.headers.get('Accept', '')
        version_match = re.search(r'application/vnd\.satreportgenerator\.v(\d+(?:\.\d+)?)', accept_header)
        
        if version_match:
            version_str = version_match.group(1)
            # Pad with .0 if only major version provided
            if '.' not in version_str:
                version_str += '.0'
            try:
                return APIVersion.from_string(version_str)
            except ValueError:
                pass
        
        # Check custom header
        version_header = request.headers.get('API-Version')
        if version_header:
            try:
                return APIVersion.from_string(version_header)
            except ValueError:
                pass
        
        # Check URL path for version (e.g., /api/v1/)
        path_match = re.search(r'/api/v(\d+)/', request.path)
        if path_match:
            major_version = int(path_match.group(1))
            # Find the latest minor version for this major version
            compatible_versions = [
                v for v in cls.SUPPORTED_VERSIONS 
                if v.major == major_version
            ]
            if compatible_versions:
                return max(compatible_versions)
        
        # Default to current version
        return cls.CURRENT_VERSION
    
    @classmethod
    def is_version_supported(cls, version):
        """Check if a version is supported."""
        return version in cls.SUPPORTED_VERSIONS
    
    @classmethod
    def is_version_deprecated(cls, version):
        """Check if a version is deprecated."""
        return version in cls.DEPRECATED_VERSIONS
    
    @classmethod
    def get_deprecation_date(cls, version):
        """Get the deprecation/sunset date for a version."""
        return cls.DEPRECATED_VERSIONS.get(version)
    
    @classmethod
    def get_compatible_version(cls, requested_version):
        """Get the best compatible version for a requested version."""
        if cls.is_version_supported(requested_version):
            return requested_version
        
        # Find the highest compatible version
        compatible_versions = [
            v for v in cls.SUPPORTED_VERSIONS
            if v.is_compatible_with(requested_version)
        ]
        
        if compatible_versions:
            return max(compatible_versions)
        
        return None


def version_required(min_version=None, max_version=None):
    """Decorator to enforce API version requirements."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            requested_version = VersionManager.get_requested_version()
            
            # Check if version is supported
            if not VersionManager.is_version_supported(requested_version):
                compatible_version = VersionManager.get_compatible_version(requested_version)
                
                if not compatible_version:
                    return jsonify({
                        'error': {
                            'message': f'API version {requested_version} is not supported',
                            'code': 'UNSUPPORTED_VERSION',
                            'supported_versions': [str(v) for v in VersionManager.SUPPORTED_VERSIONS],
                            'current_version': str(VersionManager.CURRENT_VERSION)
                        }
                    }), 400
                
                # Use compatible version
                requested_version = compatible_version
            
            # Check minimum version requirement
            if min_version and requested_version < APIVersion.from_string(min_version):
                return jsonify({
                    'error': {
                        'message': f'This endpoint requires API version {min_version} or higher',
                        'code': 'VERSION_TOO_LOW',
                        'requested_version': str(requested_version),
                        'minimum_version': min_version
                    }
                }), 400
            
            # Check maximum version requirement
            if max_version and requested_version > APIVersion.from_string(max_version):
                return jsonify({
                    'error': {
                        'message': f'This endpoint is not available in API version {requested_version}',
                        'code': 'VERSION_TOO_HIGH',
                        'requested_version': str(requested_version),
                        'maximum_version': max_version
                    }
                }), 400
            
            # Check if version is deprecated
            if VersionManager.is_version_deprecated(requested_version):
                deprecation_date = VersionManager.get_deprecation_date(requested_version)
                current_app.logger.warning(
                    f"Deprecated API version {requested_version} used. "
                    f"Sunset date: {deprecation_date}"
                )
            
            # Add version info to request context
            request.api_version = requested_version
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def add_version_headers(response):
    """Add version-related headers to response."""
    if hasattr(request, 'api_version'):
        version = request.api_version
        
        # Add version headers
        response.headers['API-Version'] = str(version)
        response.headers['API-Supported-Versions'] = ', '.join(
            str(v) for v in VersionManager.SUPPORTED_VERSIONS
        )
        
        # Add deprecation warning if applicable
        if VersionManager.is_version_deprecated(version):
            deprecation_date = VersionManager.get_deprecation_date(version)
            response.headers['Deprecation'] = deprecation_date.strftime('%a, %d %b %Y %H:%M:%S GMT')
            response.headers['Sunset'] = deprecation_date.strftime('%a, %d %b %Y %H:%M:%S GMT')
            response.headers['Warning'] = (
                f'299 - "API version {version} is deprecated and will be '
                f'removed on {deprecation_date.strftime("%Y-%m-%d")}"'
            )
    
    return response


class BackwardCompatibility:
    """Handle backward compatibility transformations."""
    
    @staticmethod
    def transform_request_data(data, from_version, to_version):
        """Transform request data from one version to another."""
        if from_version == to_version:
            return data
        
        # Add transformation logic here as versions evolve
        # Example:
        # if from_version < APIVersion(1, 1, 0) and to_version >= APIVersion(1, 1, 0):
        #     # Transform data from v1.0 to v1.1
        #     data = transform_v10_to_v11(data)
        
        return data
    
    @staticmethod
    def transform_response_data(data, from_version, to_version):
        """Transform response data from one version to another."""
        if from_version == to_version:
            return data
        
        # Add transformation logic here as versions evolve
        # Example:
        # if from_version >= APIVersion(1, 1, 0) and to_version < APIVersion(1, 1, 0):
        #     # Transform data from v1.1 to v1.0
        #     data = transform_v11_to_v10(data)
        
        return data


def backward_compatible(f):
    """Decorator to handle backward compatibility transformations."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        requested_version = getattr(request, 'api_version', VersionManager.CURRENT_VERSION)
        current_version = VersionManager.CURRENT_VERSION
        
        # Transform request data if needed
        if hasattr(request, 'json') and request.json:
            request._json = BackwardCompatibility.transform_request_data(
                request.json, requested_version, current_version
            )
        
        # Execute the function
        result = f(*args, **kwargs)
        
        # Transform response data if needed
        if isinstance(result, tuple) and len(result) >= 1:
            response_data = result[0]
            if isinstance(response_data, dict):
                transformed_data = BackwardCompatibility.transform_response_data(
                    response_data, current_version, requested_version
                )
                result = (transformed_data,) + result[1:]
        
        return result
    
    return decorated_function


# Version-specific feature flags
class FeatureFlags:
    """Feature flags for different API versions."""
    
    @staticmethod
    def is_feature_enabled(feature_name, version=None):
        """Check if a feature is enabled for a specific version."""
        if version is None:
            version = getattr(request, 'api_version', VersionManager.CURRENT_VERSION)
        
        # Define feature availability by version
        features = {
            'advanced_search': APIVersion(1, 1, 0),
            'bulk_operations': APIVersion(1, 2, 0),
            'webhooks': APIVersion(2, 0, 0),
            'graphql': APIVersion(2, 1, 0),
        }
        
        required_version = features.get(feature_name)
        if not required_version:
            return True  # Feature doesn't have version requirements
        
        return version >= required_version


def feature_required(feature_name):
    """Decorator to require a specific feature."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not FeatureFlags.is_feature_enabled(feature_name):
                version = getattr(request, 'api_version', VersionManager.CURRENT_VERSION)
                return jsonify({
                    'error': {
                        'message': f'Feature "{feature_name}" is not available in API version {version}',
                        'code': 'FEATURE_NOT_AVAILABLE',
                        'feature': feature_name,
                        'api_version': str(version)
                    }
                }), 400
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
