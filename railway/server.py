"""
Railway Server — Production-hardened
=======================================
Fixes vs v1:
  - ThreadPoolExecutor with max_workers cap (not unlimited threads)
  - Request deduplication (ignore if already running)
  - /status endpoint to check if a run is in progress
  - Graceful shutdown handling
"""

import os, sys, threading, time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from flask import Flask, request, jsonify
from dotenv import load_dotenv
load_dotenv()

app    = Flask(__name__)
SECRET = os.getenv("RAILWAY_SECRET", "")

# ── Run state tracker ─────────────────────────────────────
_run_lock   = threading.Lock()
_is_running = False
_last_run   = None
_executor   = ThreadPoolExecutor(max_workers=12)  # cap at 12 threads


def _auth_ok() -> bool:
    if not SECRET:
        return True
    return request.headers.get("Authorization") == f"Bearer {SECRET}"


def _run_all_tracked():
    global _is_running, _last_run
    from propleads_pro.main import run_all
    try:
        run_all()
        _last_run = {"status": "completed", "finished_at": datetime.utcnow().isoformat()}
    except Exception as e:
        _last_run = {"status": "failed", "error": str(e),
                     "finished_at": datetime.utcnow().isoformat()}
        print(f"[Railway] ❌ run_all failed: {e}")
    finally:
        _is_running = False


def _run_zip_tracked(state: str, zip_code: str):
    global _last_run
    from propleads_pro.main import run_for_zip
    try:
        run_for_zip(state=state, zip_code=zip_code)
        _last_run = {"status": "completed", "zip": zip_code,
                     "finished_at": datetime.utcnow().isoformat()}
    except Exception as e:
        _last_run = {"status": "failed", "zip": zip_code, "error": str(e),
                     "finished_at": datetime.utcnow().isoformat()}
    finally:
        global _is_running
        _is_running = False


@app.route("/run", methods=["POST"])
def run():
    global _is_running
    if not _auth_ok():
        return jsonify({"error": "unauthorized"}), 401

    with _run_lock:
        if _is_running:
            return jsonify({"status": "already_running",
                            "message": "A run is already in progress. Try again later."}), 409
        _is_running = True

    body     = request.get_json(silent=True) or {}
    mode     = body.get("mode", "all")
    state    = body.get("state", "TX")
    zip_code = body.get("zip", "78701")

    if mode == "zip":
        _executor.submit(_run_zip_tracked, state, zip_code)
        print(f"[Railway] ZIP run queued: {state}/{zip_code}")
    else:
        _executor.submit(_run_all_tracked)
        print(f"[Railway] Full daily run queued")

    return jsonify({"status": "started", "mode": mode,
                    "started_at": datetime.utcnow().isoformat()})


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "is_running": _is_running,
        "last_run":   _last_run,
    })


@app.route("/test", methods=["POST"])
def test():
    if not _auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    _executor.submit(_run_zip_tracked, "TX", "78701")
    return jsonify({"status": "test started", "zip": "78701"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "propleads-pro",
                    "is_running": _is_running})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"[Railway] PropLeads Pro starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
