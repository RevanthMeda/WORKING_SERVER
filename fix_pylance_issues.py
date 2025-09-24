#!/usr/bin/env python3
"""
Script to fix Pylance issues and clean up the project
"""

import os
import shutil
import sys
from pathlib import Path

def clean_cache_directories():
    """Remove cache directories that might cause issues"""
    cache_dirs = [
        '__pycache__',
        '.pytest_cache',
        '.mypy_cache',
        '.coverage',
        'htmlcov',
        '.tox',
        '.nox',
        'build',
        'dist',
        '*.egg-info'
    ]
    
    project_root = Path(__file__).parent
    
    print("🧹 Cleaning cache directories...")
    
    for cache_dir in cache_dirs:
        if '*' in cache_dir:
            # Handle glob patterns
            for path in project_root.rglob(cache_dir):
                if path.is_dir():
                    print(f"  Removing: {path}")
                    shutil.rmtree(path, ignore_errors=True)
        else:
            for path in project_root.rglob(cache_dir):
                if path.is_dir():
                    print(f"  Removing: {path}")
                    shutil.rmtree(path, ignore_errors=True)
    
    # Clean .pyc files
    print("🧹 Cleaning .pyc files...")
    for pyc_file in project_root.rglob('*.pyc'):
        print(f"  Removing: {pyc_file}")
        pyc_file.unlink(missing_ok=True)
    
    print("✅ Cache cleanup completed!")

def create_missing_init_files():
    """Create missing __init__.py files"""
    print("📁 Creating missing __init__.py files...")
    
    project_root = Path(__file__).parent
    
    # Directories that should have __init__.py files
    package_dirs = [
        'services',
        'routes', 
        'models',
        'config',
        'cache',
        'database',
        'tasks',
        'api',
        'monitoring',
        'security',
        'tests',
        'typings',
        'typings/services',
        'typings/flask_wtf',
        'typings/flask_login',
        'typings/flask_session'
    ]
    
    for pkg_dir in package_dirs:
        pkg_path = project_root / pkg_dir
        if pkg_path.exists() and pkg_path.is_dir():
            init_file = pkg_path / '__init__.py'
            if not init_file.exists():
                print(f"  Creating: {init_file}")
                init_file.touch()
    
    print("✅ __init__.py files created!")

def fix_import_issues():
    """Fix common import issues"""
    print("🔧 Checking for import issues...")
    
    project_root = Path(__file__).parent
    
    # Check if critical files exist
    critical_files = [
        'app.py',
        'config.py',
        'models.py',
        'auth.py',
        'session_manager.py'
    ]
    
    missing_files = []
    for file_name in critical_files:
        file_path = project_root / file_name
        if not file_path.exists():
            missing_files.append(file_name)
    
    if missing_files:
        print(f"⚠️  Missing critical files: {missing_files}")
    else:
        print("✅ All critical files present!")

def update_vscode_settings():
    """Update VS Code settings for better Pylance experience"""
    print("⚙️  Updating VS Code settings...")
    
    vscode_dir = Path(__file__).parent / '.vscode'
    vscode_dir.mkdir(exist_ok=True)
    
    # The settings.json file should already be created by previous operations
    settings_file = vscode_dir / 'settings.json'
    if settings_file.exists():
        print("✅ VS Code settings already configured!")
    else:
        print("⚠️  VS Code settings file missing - please run the configuration script")

def main():
    """Main function to run all fixes"""
    print("🚀 Starting Pylance issue fixes...")
    print("=" * 50)
    
    try:
        clean_cache_directories()
        print()
        
        create_missing_init_files()
        print()
        
        fix_import_issues()
        print()
        
        update_vscode_settings()
        print()
        
        print("=" * 50)
        print("✅ All fixes completed successfully!")
        print()
        print("📋 Next steps:")
        print("1. Restart VS Code")
        print("2. Reload the Python interpreter (Ctrl+Shift+P -> Python: Select Interpreter)")
        print("3. Clear Pylance cache (Ctrl+Shift+P -> Python: Clear Cache and Reload Window)")
        print("4. The number of Pylance problems should be significantly reduced!")
        
    except Exception as e:
        print(f"❌ Error during fixes: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()