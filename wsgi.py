"""
WSGI entry point for production deployment.

Usage with gunicorn:
    gunicorn -w 2 -b 0.0.0.0:5000 wsgi:app

Or with nginx + gunicorn:
    gunicorn -w 4 -b 127.0.0.1:8000 wsgi:app
"""

from web_app import app

if __name__ == "__main__":
    # For development only
    app.run(host='0.0.0.0', port=5000, debug=False)
