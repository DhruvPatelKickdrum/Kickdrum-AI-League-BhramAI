"""
Minimal Flask API for the RAG claim verification pipeline.
Designed for MVP: browser extension selects text → POST /verify → returns result.
"""

import logging

from flask import Flask, jsonify, request

# Import after app so config/logging are loaded
from main import verify_claim as _verify_claim

app = Flask(__name__)
logger = logging.getLogger(__name__)

# CORS for browser extension / web clients (MVP: allow all origins; tighten in production)
@app.after_request
def cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response


@app.route("/health", methods=["GET"])
def health():
    """Liveness/readiness for ALB and monitoring."""
    return jsonify({"status": "ok"})


@app.route("/verify", methods=["POST", "OPTIONS"])
def verify():
    """
    Verify a claim via the RAG pipeline.
    Body: { "claim": "text to verify" }
    Returns: { "claim": str, "verdict": str, "reasoning": str, "citations": list }
    """
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(silent=True) or {}
    claim = data.get("claim") or (request.form.get("claim") if request.form else None)

    if not claim or not str(claim).strip():
        return jsonify({"error": "Missing or empty 'claim'"}), 400

    claim = str(claim).strip()
    try:
        result = _verify_claim(claim)
        return jsonify({
            "claim": result.get("claim", ""),
            "verdict": result.get("verdict", ""),
            "reasoning": result.get("reasoning", ""),
            "citations": result.get("citations", []),
        })
    except Exception as e:
        logger.exception("Verify failed for claim=%s", claim[:100])
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    from config.logging_config import setup_logging
    from config.settings import settings
    setup_logging(settings.log_level)
    app.run(host="0.0.0.0", port=8080, debug=False)
