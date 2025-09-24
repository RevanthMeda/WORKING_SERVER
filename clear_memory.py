#!/usr/bin/env python3
"""
Memory clearing script for SAT Report Generator
Clears all cached configurations and reloads fresh credentials on startup
"""

import os
import sys
import gc
import logging

def clear_application_memory():
    """Clear all cached configurations and force garbage collection"""
    print("🧹 Clearing application memory...")
    
    # Clear Python module cache for configuration modules
    modules_to_clear = ['config', 'utils', 'auth', 'models']
    
    for module_name in modules_to_clear:
        if module_name in sys.modules:
            print(f"   🗑️  Clearing {module_name} from module cache")
            del sys.modules[module_name]
    
    # Force garbage collection
    collected = gc.collect()
    print(f"   ♻️  Garbage collected: {collected} objects")
    
    # Clear environment cache (if using dotenv)
    env_vars_to_refresh = ['SMTP_PASSWORD', 'SMTP_USERNAME', 'DEFAULT_SENDER']
    for var in env_vars_to_refresh:
        if var in os.environ:
            value = os.environ[var]
            # Re-set to force refresh
            os.environ[var] = value
            print(f"   🔄 Refreshed environment variable: {var}")
    
    print("✅ Memory clearing completed!")

def test_fresh_credentials():
    """Test that credentials are loading fresh"""
    print("🧪 Testing fresh credential loading...")
    
    try:
        from config import Config
        creds = Config.get_smtp_credentials()
        
        print(f"   📧 SMTP Server: {creds['server']}")
        print(f"   👤 Username: {creds['username']}")
        print(f"   🔐 Password: {creds['password'][:4]}...{creds['password'][-4:]}")
        print(f"   📬 Sender: {creds['sender']}")
        print("✅ Fresh credentials loaded successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading fresh credentials: {e}")
        return False

if __name__ == "__main__":
    clear_application_memory()
    test_fresh_credentials()