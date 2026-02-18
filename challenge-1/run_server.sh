#!/usr/bin/env bash
# Start the RAG API with the correct Gunicorn timeout (required for /verify).
# From project root: ./run_server.sh   or   bash run_server.sh
cd "$(dirname "$0")"
exec uv run gunicorn -c gunicorn_config.py "src.api.app:app"
