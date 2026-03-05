import os
import sys
import json
import threading
import traceback
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify

app = Flask(__name__)
SECRET = os.getenv("RAILWAY_SECRET", "")
_running = False
_lock = threading.Lock()
_last = None
_pool = ThreadPoolExecutor(max_workers=5)

def auth_ok():
    if not SECRET:
        return True
    return request.headers.get("Authorization") == f"Bearer {SECRET}"

@app.route("/health")
def health():
    missing = [k for k in ["OPENAI_API_KEY","SUPABASE_URL","SERPER_API_KEY"]
               if not os.getenv(k)]
    return jsonify({"status": "ok" if not missing else "warning",
                    "missing_vars": missing, "running": _running})

@app.route("/status")
def status():
    return jsonify({"running": _running, "last": _last})

@app.route("/run", methods=["POST"])
def run():
    global _running
    if not auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    with _lock:
        if _running:
            return jsonify({"status": "already_running"}), 409
        _running = True
    body = request.get_json(silent=True) or {}
    mode = body.get("mode", "all")
    return jsonify({"status": "started", "mode": mode})

@app.route("/test", methods=["POST"])
def test():
    global _running
    if not auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"status": "test ok"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
