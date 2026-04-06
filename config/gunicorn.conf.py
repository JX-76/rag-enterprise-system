"""
Gunicorn Configuration
"""
import multiprocessing

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "rag_api"

# Server mechanics
daemon = False
pidfile = "/tmp/gunicorn.pid"

# SSL
keyfile = None
certfile = None
