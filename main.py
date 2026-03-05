import os
import sys
import json
import threading
import traceback
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# הוסף את src/ ל-Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

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

def _run_zip_job(state, zip_code):
    global _running, _last
    try:
        from propleads_pro.main import run_for_zip
        run_for_zip(state=state, zip_code=zip_code)
        _last = {"status": "completed", "zip": zip_code}
    except Exception as e:
        traceback.print_exc()
        _last = {"status": "failed", "error": str(e)}
    finally:
        _running = False

def _run_all_job():
    global _running, _last
    try:
        from propleads_pro.main import run_all
        run_all()
        _last = {"status": "completed"}
    except Exception as e:
        traceback.print_exc()
        _last = {"status": "failed", "error": str(e)}
    finally:
        _running = False

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
    if mode == "zip":
        _pool.submit(_run_zip_job, body.get("state","TX"), body.get("zip","78701"))
    else:
        _pool.submit(_run_all_job)
    return jsonify({"status": "started", "mode": mode})

@app.route("/test", methods=["POST"])
def test():
    global _running
    if not auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    with _lock:
        if _running:
            return jsonify({"status": "already_running"}), 409
        _running = True
    _pool.submit(_run_zip_job, "TX", "78701")
    return jsonify({"status": "test started"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
