"""
Production WSGI server configuration for SAT Report Generator
Optimized for performance
"""
import os
import sys
from waitress import serve
from app import create_app

# Create the Flask application
app = create_app('production')

def run_production_server():
    """Run the application with optimized Waitress production server"""
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    
    print(f"Starting SAT Report Generator on {host}:{port}")
    print("Using optimized Waitress production server")
    
    # Optimized Waitress configuration for better performance
    serve(
        app,
        host=host,
        port=port,
        threads=6,  # Optimal thread count for most systems
        connection_limit=50,  # Prevent connection overload
        cleanup_interval=10,  # Frequent cleanup of idle connections
        channel_timeout=60,  # Reasonable timeout for idle connections
        ident='SAT-Report-Generator',
        asyncore_use_poll=True,  # Better performance than select()
        backlog=128,  # Handle more pending connections
        recv_bytes=8192,  # Larger receive buffer
        send_bytes=16384,  # Larger send buffer
        outbuf_overflow=104857600,  # 100MB overflow buffer
        max_request_body_size=10485760,  # 10MB max request
    )

if __name__ == '__main__':
    # Run production server
    run_production_server()
