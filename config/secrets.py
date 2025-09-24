"""
Secrets management system with HashiCorp Vault integration.
"""
import os
import json
import logging
import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import secrets

logger = logging.getLogger(__name__)


@dataclass
class SecretMetadata:
    """Metadata for a secret."""
    key: str
    version: int = 1
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    source: str = 'vault'
    encrypted: bool = True


class VaultClient:
    """HashiCorp Vault client for secret management."""
    
    def __init__(self, vault_url: str, vault_token: str = None, vault_role_id: str = None, vault_secret_id: str = None):
        self.vault_url = vault_url.rstrip('/')
        self.vault_token = vault_token
        self.vault_role_id = vault_role_id
        self.vault_secret_id = vault_secret_id
        self.session = requests.Session()
        self.token_expires_at = None
        self.lock = threading.Lock()
        
        # Set up session headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
        # Authenticate if credentials provided
        if vault_token:
            self.set_token(vault_token)
        elif vault_role_id and vault_secret_id:
            self.authenticate_approle()
    
    def set_token(self, token: str):
        """Set Vault token."""
        self.vault_token = token
        self.session.headers['X-Vault-Token'] = token
        
        # Get token info to determine expiration
        try:
            response = self.session.get(f"{self.vault_url}/v1/auth/token/lookup-self")
            if response.status_code == 200:
                token_info = response.json()
                ttl = token_info.get('data', {}).get('ttl', 0)
                if ttl > 0:
                    self.token_expires_at = datetime.now() + timedelta(seconds=ttl)
        except Exception as e:
            logger.warning(f"Failed to get token info: {e}")
    
    def authenticate_approle(self):
        """Authenticate using AppRole method."""
        try:
            auth_data = {
                'role_id': self.vault_role_id,
                'secret_id': self.vault_secret_id
            }
            
            response = self.session.post(
                f"{self.vault_url}/v1/auth/approle/login",
                json=auth_data
            )
            
            if response.status_code == 200:
                auth_info = response.json()
                token = auth_info['auth']['client_token']
                self.set_token(token)
                logger.info("Successfully authenticated with Vault using AppRole")
            else:
                raise Exception(f"AppRole authentication failed: {response.text}")
                
        except Exception as e:
            logger.error(f"Vault AppRole authentication failed: {e}")
            raise
    
    def is_token_valid(self) -> bool:
        """Check if current token is valid."""
        if not self.vault_token:
            return False
        
        if self.token_expires_at and datetime.now() >= self.token_expires_at:
            return False
        
        try:
            response = self.session.get(f"{self.vault_url}/v1/auth/token/lookup-self")
            return response.status_code == 200
        except Exception:
            return False
    
    def renew_token(self):
        """Renew the current token."""
        try:
            response = self.session.post(f"{self.vault_url}/v1/auth/token/renew-self")
            if response.status_code == 200:
                token_info = response.json()
                ttl = token_info.get('auth', {}).get('lease_duration', 0)
                if ttl > 0:
                    self.token_expires_at = datetime.now() + timedelta(seconds=ttl)
                logger.info("Vault token renewed successfully")
            else:
                logger.warning(f"Token renewal failed: {response.text}")
        except Exception as e:
            logger.error(f"Token renewal failed: {e}")
    
    def get_secret(self, path: str, version: int = None) -> Optional[Dict[str, Any]]:
        """Get secret from Vault."""
        with self.lock:
            if not self.is_token_valid():
                if self.vault_role_id and self.vault_secret_id:
                    self.authenticate_approle()
                else:
                    raise Exception("Vault token is invalid and no AppRole credentials available")
            
            try:
                url = f"{self.vault_url}/v1/secret/data/{path}"
                if version:
                    url += f"?version={version}"
                
                response = self.session.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('data', {}).get('data', {})
                elif response.status_code == 404:
                    return None
                else:
                    logger.error(f"Failed to get secret {path}: {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"Error getting secret {path}: {e}")
                return None
    
    def put_secret(self, path: str, data: Dict[str, Any]) -> bool:
        """Store secret in Vault."""
        with self.lock:
            if not self.is_token_valid():
                if self.vault_role_id and self.vault_secret_id:
                    self.authenticate_approle()
                else:
                    raise Exception("Vault token is invalid and no AppRole credentials available")
            
            try:
                url = f"{self.vault_url}/v1/secret/data/{path}"
                payload = {'data': data}
                
                response = self.session.post(url, json=payload)
                
                if response.status_code in [200, 204]:
                    logger.info(f"Secret stored successfully: {path}")
                    return True
                else:
                    logger.error(f"Failed to store secret {path}: {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error storing secret {path}: {e}")
                return False
    
    def delete_secret(self, path: str) -> bool:
        """Delete secret from Vault."""
        with self.lock:
            if not self.is_token_valid():
                if self.vault_role_id and self.vault_secret_id:
                    self.authenticate_approle()
                else:
                    raise Exception("Vault token is invalid and no AppRole credentials available")
            
            try:
                url = f"{self.vault_url}/v1/secret/metadata/{path}"
                response = self.session.delete(url)
                
                if response.status_code in [200, 204]:
                    logger.info(f"Secret deleted successfully: {path}")
                    return True
                else:
                    logger.error(f"Failed to delete secret {path}: {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error deleting secret {path}: {e}")
                return False
    
    def list_secrets(self, path: str = "") -> List[str]:
        """List secrets at path."""
        with self.lock:
            if not self.is_token_valid():
                if self.vault_role_id and self.vault_secret_id:
                    self.authenticate_approle()
                else:
                    raise Exception("Vault token is invalid and no AppRole credentials available")
            
            try:
                url = f"{self.vault_url}/v1/secret/metadata/{path}"
                response = self.session.request('LIST', url)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('data', {}).get('keys', [])
                else:
                    logger.error(f"Failed to list secrets at {path}: {response.text}")
                    return []
                    
            except Exception as e:
                logger.error(f"Error listing secrets at {path}: {e}")
                return []


class LocalSecretsManager:
    """Local encrypted secrets manager for development/fallback."""
    
    def __init__(self, secrets_file: str = 'secrets.enc', master_key: str = None):
        self.secrets_file = Path(secrets_file)
        self.master_key = master_key or os.environ.get('SECRETS_MASTER_KEY')
        self.secrets_cache: Dict[str, Any] = {}
        self.metadata_cache: Dict[str, SecretMetadata] = {}
        self.lock = threading.Lock()
        
        # Generate master key if not provided
        if not self.master_key:
            self.master_key = self._generate_master_key()
            logger.warning("Generated new master key for local secrets. Store this securely!")
        
        # Initialize encryption
        self.cipher = self._get_cipher()
        
        # Load existing secrets
        self._load_secrets()
    
    def _generate_master_key(self) -> str:
        """Generate a new master key."""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
    
    def _get_cipher(self) -> Fernet:
        """Get Fernet cipher from master key."""
        # Derive key from master key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'sat_secrets_salt',  # In production, use random salt
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key.encode()))
        return Fernet(key)
    
    def _load_secrets(self):
        """Load secrets from encrypted file."""
        if not self.secrets_file.exists():
            return
        
        try:
            with open(self.secrets_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            data = json.loads(decrypted_data.decode())
            
            self.secrets_cache = data.get('secrets', {})
            
            # Load metadata
            metadata = data.get('metadata', {})
            for key, meta in metadata.items():
                self.metadata_cache[key] = SecretMetadata(
                    key=key,
                    version=meta.get('version', 1),
                    created_at=datetime.fromisoformat(meta['created_at']) if meta.get('created_at') else None,
                    expires_at=datetime.fromisoformat(meta['expires_at']) if meta.get('expires_at') else None,
                    last_accessed=datetime.fromisoformat(meta['last_accessed']) if meta.get('last_accessed') else None,
                    access_count=meta.get('access_count', 0),
                    source=meta.get('source', 'local'),
                    encrypted=meta.get('encrypted', True)
                )
            
            logger.info(f"Loaded {len(self.secrets_cache)} secrets from local storage")
            
        except Exception as e:
            logger.error(f"Failed to load local secrets: {e}")
    
    def _save_secrets(self):
        """Save secrets to encrypted file."""
        try:
            # Prepare data
            data = {
                'secrets': self.secrets_cache,
                'metadata': {
                    key: {
                        'version': meta.version,
                        'created_at': meta.created_at.isoformat() if meta.created_at else None,
                        'expires_at': meta.expires_at.isoformat() if meta.expires_at else None,
                        'last_accessed': meta.last_accessed.isoformat() if meta.last_accessed else None,
                        'access_count': meta.access_count,
                        'source': meta.source,
                        'encrypted': meta.encrypted
                    }
                    for key, meta in self.metadata_cache.items()
                }
            }
            
            # Encrypt and save
            json_data = json.dumps(data).encode()
            encrypted_data = self.cipher.encrypt(json_data)
            
            # Ensure directory exists
            self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.secrets_file, 'wb') as f:
                f.write(encrypted_data)
            
            logger.debug("Secrets saved to local storage")
            
        except Exception as e:
            logger.error(f"Failed to save local secrets: {e}")
    
    def get_secret(self, key: str) -> Optional[Any]:
        """Get secret value."""
        with self.lock:
            if key not in self.secrets_cache:
                return None
            
            # Update access metadata
            if key in self.metadata_cache:
                self.metadata_cache[key].last_accessed = datetime.now()
                self.metadata_cache[key].access_count += 1
            
            # Check expiration
            if key in self.metadata_cache and self.metadata_cache[key].expires_at:
                if datetime.now() > self.metadata_cache[key].expires_at:
                    logger.warning(f"Secret {key} has expired")
                    return None
            
            return self.secrets_cache[key]
    
    def put_secret(self, key: str, value: Any, expires_at: datetime = None) -> bool:
        """Store secret value."""
        with self.lock:
            try:
                self.secrets_cache[key] = value
                
                # Update metadata
                now = datetime.now()
                if key in self.metadata_cache:
                    self.metadata_cache[key].version += 1
                else:
                    self.metadata_cache[key] = SecretMetadata(
                        key=key,
                        created_at=now,
                        source='local'
                    )
                
                if expires_at:
                    self.metadata_cache[key].expires_at = expires_at
                
                self._save_secrets()
                return True
                
            except Exception as e:
                logger.error(f"Failed to store secret {key}: {e}")
                return False
    
    def delete_secret(self, key: str) -> bool:
        """Delete secret."""
        with self.lock:
            try:
                if key in self.secrets_cache:
                    del self.secrets_cache[key]
                
                if key in self.metadata_cache:
                    del self.metadata_cache[key]
                
                self._save_secrets()
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete secret {key}: {e}")
                return False
    
    def list_secrets(self) -> List[str]:
        """List all secret keys."""
        with self.lock:
            return list(self.secrets_cache.keys())


class SecretsManager:
    """Unified secrets management with multiple backends."""
    
    def __init__(self):
        self.vault_client: Optional[VaultClient] = None
        self.local_manager: Optional[LocalSecretsManager] = None
        self.cache: Dict[str, Any] = {}
        self.cache_ttl: Dict[str, datetime] = {}
        self.default_cache_duration = timedelta(minutes=5)
        self.lock = threading.Lock()
        self.rotation_schedule: Dict[str, datetime] = {}
        
        # Auto-rotation thread
        self.rotation_thread = None
        self.rotation_enabled = False
    
    def init_vault(self, vault_url: str, vault_token: str = None, vault_role_id: str = None, vault_secret_id: str = None):
        """Initialize Vault client."""
        try:
            self.vault_client = VaultClient(vault_url, vault_token, vault_role_id, vault_secret_id)
            logger.info("Vault client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Vault client: {e}")
            self.vault_client = None
    
    def init_local(self, secrets_file: str = None, master_key: str = None):
        """Initialize local secrets manager."""
        try:
            self.local_manager = LocalSecretsManager(secrets_file, master_key)
            logger.info("Local secrets manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize local secrets manager: {e}")
            self.local_manager = None
    
    def get_secret(self, key: str, use_cache: bool = True) -> Optional[Any]:
        """Get secret from available backends."""
        with self.lock:
            # Check cache first
            if use_cache and key in self.cache:
                if key not in self.cache_ttl or datetime.now() < self.cache_ttl[key]:
                    return self.cache[key]
                else:
                    # Cache expired
                    del self.cache[key]
                    del self.cache_ttl[key]
            
            # Try Vault first
            if self.vault_client:
                try:
                    vault_data = self.vault_client.get_secret(key)
                    if vault_data:
                        # Cache the result
                        if use_cache:
                            self.cache[key] = vault_data
                            self.cache_ttl[key] = datetime.now() + self.default_cache_duration
                        return vault_data
                except Exception as e:
                    logger.warning(f"Failed to get secret from Vault: {e}")
            
            # Fallback to local manager
            if self.local_manager:
                try:
                    local_data = self.local_manager.get_secret(key)
                    if local_data is not None:
                        # Cache the result
                        if use_cache:
                            self.cache[key] = local_data
                            self.cache_ttl[key] = datetime.now() + self.default_cache_duration
                        return local_data
                except Exception as e:
                    logger.warning(f"Failed to get secret from local storage: {e}")
            
            # Check environment variables as last resort
            env_key = f"SECRET_{key.upper().replace('/', '_')}"
            env_value = os.environ.get(env_key)
            if env_value:
                logger.info(f"Retrieved secret {key} from environment variable")
                return env_value
            
            return None
    
    def put_secret(self, key: str, value: Any, backend: str = 'auto') -> bool:
        """Store secret in specified backend."""
        success = False
        
        # Clear cache
        with self.lock:
            if key in self.cache:
                del self.cache[key]
            if key in self.cache_ttl:
                del self.cache_ttl[key]
        
        if backend == 'vault' or (backend == 'auto' and self.vault_client):
            if self.vault_client:
                try:
                    if isinstance(value, dict):
                        success = self.vault_client.put_secret(key, value)
                    else:
                        success = self.vault_client.put_secret(key, {'value': value})
                    
                    if success:
                        logger.info(f"Secret {key} stored in Vault")
                        return True
                except Exception as e:
                    logger.error(f"Failed to store secret in Vault: {e}")
        
        if backend == 'local' or (backend == 'auto' and not success):
            if self.local_manager:
                try:
                    success = self.local_manager.put_secret(key, value)
                    if success:
                        logger.info(f"Secret {key} stored locally")
                        return True
                except Exception as e:
                    logger.error(f"Failed to store secret locally: {e}")
        
        return success
    
    def delete_secret(self, key: str, backend: str = 'all') -> bool:
        """Delete secret from backends."""
        success = False
        
        # Clear cache
        with self.lock:
            if key in self.cache:
                del self.cache[key]
            if key in self.cache_ttl:
                del self.cache_ttl[key]
        
        if backend in ['vault', 'all'] and self.vault_client:
            try:
                if self.vault_client.delete_secret(key):
                    success = True
                    logger.info(f"Secret {key} deleted from Vault")
            except Exception as e:
                logger.error(f"Failed to delete secret from Vault: {e}")
        
        if backend in ['local', 'all'] and self.local_manager:
            try:
                if self.local_manager.delete_secret(key):
                    success = True
                    logger.info(f"Secret {key} deleted from local storage")
            except Exception as e:
                logger.error(f"Failed to delete secret from local storage: {e}")
        
        return success
    
    def list_secrets(self, backend: str = 'all') -> List[str]:
        """List secrets from backends."""
        all_secrets = set()
        
        if backend in ['vault', 'all'] and self.vault_client:
            try:
                vault_secrets = self.vault_client.list_secrets()
                all_secrets.update(vault_secrets)
            except Exception as e:
                logger.error(f"Failed to list secrets from Vault: {e}")
        
        if backend in ['local', 'all'] and self.local_manager:
            try:
                local_secrets = self.local_manager.list_secrets()
                all_secrets.update(local_secrets)
            except Exception as e:
                logger.error(f"Failed to list secrets from local storage: {e}")
        
        return sorted(list(all_secrets))
    
    def schedule_rotation(self, key: str, rotation_interval: timedelta):
        """Schedule automatic secret rotation."""
        self.rotation_schedule[key] = datetime.now() + rotation_interval
        
        if not self.rotation_enabled:
            self.start_rotation_service()
    
    def start_rotation_service(self):
        """Start automatic secret rotation service."""
        if self.rotation_thread and self.rotation_thread.is_alive():
            return
        
        self.rotation_enabled = True
        self.rotation_thread = threading.Thread(target=self._rotation_worker, daemon=True)
        self.rotation_thread.start()
        logger.info("Secret rotation service started")
    
    def stop_rotation_service(self):
        """Stop automatic secret rotation service."""
        self.rotation_enabled = False
        if self.rotation_thread:
            self.rotation_thread.join(timeout=5)
        logger.info("Secret rotation service stopped")
    
    def _rotation_worker(self):
        """Worker thread for automatic secret rotation."""
        while self.rotation_enabled:
            try:
                now = datetime.now()
                
                for key, next_rotation in list(self.rotation_schedule.items()):
                    if now >= next_rotation:
                        logger.info(f"Rotating secret: {key}")
                        
                        # Generate new secret value (this is a placeholder)
                        new_value = self._generate_secret_value(key)
                        
                        if self.put_secret(key, new_value):
                            # Schedule next rotation
                            self.rotation_schedule[key] = now + timedelta(days=30)  # Default 30 days
                            logger.info(f"Secret {key} rotated successfully")
                        else:
                            logger.error(f"Failed to rotate secret {key}")
                
                time.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Error in rotation worker: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def _generate_secret_value(self, key: str) -> str:
        """Generate new secret value for rotation."""
        # This is a placeholder - implement based on secret type
        if 'password' in key.lower():
            return secrets.token_urlsafe(32)
        elif 'api_key' in key.lower():
            return f"sk_{secrets.token_urlsafe(32)}"
        else:
            return secrets.token_urlsafe(24)
    
    def clear_cache(self):
        """Clear the secrets cache."""
        with self.lock:
            self.cache.clear()
            self.cache_ttl.clear()
        logger.info("Secrets cache cleared")
    
    def get_status(self) -> Dict[str, Any]:
        """Get secrets manager status."""
        return {
            'vault_available': self.vault_client is not None,
            'local_available': self.local_manager is not None,
            'cached_secrets': len(self.cache),
            'rotation_enabled': self.rotation_enabled,
            'scheduled_rotations': len(self.rotation_schedule),
            'next_rotation': min(self.rotation_schedule.values()).isoformat() if self.rotation_schedule else None
        }


# Global secrets manager instance
secrets_manager = SecretsManager()


def init_secrets_management(app):
    """Initialize secrets management system."""
    global secrets_manager
    
    # Get configuration
    vault_url = app.config.get('VAULT_URL') or os.environ.get('VAULT_URL')
    vault_token = app.config.get('VAULT_TOKEN') or os.environ.get('VAULT_TOKEN')
    vault_role_id = app.config.get('VAULT_ROLE_ID') or os.environ.get('VAULT_ROLE_ID')
    vault_secret_id = app.config.get('VAULT_SECRET_ID') or os.environ.get('VAULT_SECRET_ID')
    
    # Initialize Vault if configured
    if vault_url:
        try:
            secrets_manager.init_vault(vault_url, vault_token, vault_role_id, vault_secret_id)
        except Exception as e:
            logger.warning(f"Failed to initialize Vault: {e}")
    
    # Always initialize local manager as fallback
    secrets_file = app.config.get('SECRETS_FILE', 'instance/secrets.enc')
    master_key = app.config.get('SECRETS_MASTER_KEY') or os.environ.get('SECRETS_MASTER_KEY')
    
    try:
        secrets_manager.init_local(secrets_file, master_key)
    except Exception as e:
        logger.error(f"Failed to initialize local secrets manager: {e}")
    
    # Store secrets manager in app
    app.secrets_manager = secrets_manager
    
    logger.info("Secrets management system initialized")
    return secrets_manager