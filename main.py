"""
Main entry point for SAT Report Generator on Replit
"""
import os
from app import create_app

# Determine environment based on FLASK_ENV
flask_env = os.environ.get('FLASK_ENV', 'development')
config_name = 'production' if flask_env == 'production' else 'development'

# Create the Flask application
app = create_app(config_name)

if __name__ == '__main__':
    # For Replit, we'll use gunicorn instead of Flask's development server
    # This allows proper handling of proxied requests
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=(config_name == 'development'))
