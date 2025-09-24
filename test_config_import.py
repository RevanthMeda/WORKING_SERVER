#!/usr/bin/env python3
"""
Test script to verify config imports work correctly
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Test importing from config.py
    import config as config_module
    print("✅ Successfully imported config module")
    print(f"Config module file: {config_module.__file__}")
    
    # Test accessing Config class
    Config = config_module.Config
    print("✅ Successfully accessed Config class")
    print(f"Config class: {Config}")
    
    # Test accessing config dictionary
    config_dict = config_module.config
    print("✅ Successfully accessed config dictionary")
    print(f"Available configs: {list(config_dict.keys())}")
    
    # Test creating a config instance
    dev_config = config_dict['development']
    print("✅ Successfully accessed development config")
    print(f"Development config: {dev_config}")
    
    print("\n🎉 All config imports working correctly!")
    
except Exception as e:
    print(f"❌ Error importing config: {e}")
    import traceback
    traceback.print_exc()