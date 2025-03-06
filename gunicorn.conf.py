"""Gunicorn configuration file"""
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"
backlog = 2048

# Worker processes
workers = 1
worker_class = 'gthread'
threads = 2
timeout = 300
keepalive = 2

# Logging
errorlog = '-'
loglevel = 'info'
accesslog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL
certfile = None
keyfile = None

# Process naming
proc_name = None

# Server hooks
def on_starting(server):
    print("Starting Gunicorn server...")

def on_exit(server):
    print("Shutting down Gunicorn server...")

# WSGI application path (this is the important part)
wsgi_app = "wsgi:app" 