# Gunicorn config for RAG API. REQUIRED for /verify (agent runs can take 10+ minutes).
# Run: uv run gunicorn -c gunicorn_config.py "src.api.app:app"
# Without -c gunicorn_config.py, default timeout is 30s and the worker is killed mid-request.
timeout = 900  # 15 minutes — RAG /verify can take 10+ min
workers = 2
bind = "0.0.0.0:8080"


def when_ready(server):
    """Log so you can confirm the config is loaded (timeout must be > 30 for /verify)."""
    server.log.info("RAG API: worker timeout = %ss (config loaded)", timeout)
