"""Gunicorn configuration for production deployment."""

import multiprocessing
import os

bind =f"0.0.0.0:{os .getenv ('PORT','8000')}"
backlog =2048

workers =int (os .getenv ("WORKERS",multiprocessing .cpu_count ()*2 +1 ))
worker_class ="uvicorn.workers.UvicornWorker"
worker_connections =1500
max_requests =1000
max_requests_jitter =50

timeout =60
keepalive =5
graceful_timeout =30

accesslog ="-"
errorlog ="-"
loglevel =os .getenv ("LOG_LEVEL","info").lower ()
access_log_format ='%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

proc_name ="vinted-parser-bot"

preload_app =True
daemon =False
pidfile ="/tmp/gunicorn.pid"
user =None
group =None
tmp_upload_dir =None

keyfile =os .getenv ("SSL_KEYFILE")
certfile =os .getenv ("SSL_CERTFILE")

def when_ready (server ):
    """Called just after the server is started."""
    server .log .info ("Server is ready. Spawning workers")

def worker_int (worker ):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker .log .info ("worker received INT or QUIT signal")

def pre_fork (server ,worker ):
    """Called just before a worker is forked."""
    server .log .info ("Worker spawned (pid: %s)",worker .pid )

def post_fork (server ,worker ):
    """Called just after a worker has been forked."""
    server .log .info ("Worker spawned (pid: %s)",worker .pid )

def post_worker_init (worker ):
    """Called just after a worker has initialized the application."""
    worker .log .info ("Worker initialized (pid: %s)",worker .pid )

def worker_abort (worker ):
    """Called when a worker received the SIGABRT signal."""
    worker .log .info ("Worker aborted (pid: %s)",worker .pid )