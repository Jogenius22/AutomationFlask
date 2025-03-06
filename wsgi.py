"""
WSGI entry point for Gunicorn
"""
from app import create_app

# Create the application instance
application = create_app()

# For compatibility with some WSGI servers that look for 'app'
app = application 