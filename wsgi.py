"""
WSGI entry point for production deployment
Use with gunicorn: gunicorn -w 4 -b 0.0.0.0:8080 wsgi:app
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

from app import app

if __name__ == "__main__":
    app.run()
