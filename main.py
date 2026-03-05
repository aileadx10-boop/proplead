import os
import sys
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
SECRET = os.getenv("RAILWAY_SECRET", "")

def auth_ok():
    if not SECRET:
        return True
    return request.headers.get("Authorization") == f"Bearer {SECRET}"

@app.route("/health")
def health():
    missing = [k for k in ["OPENAI_API_KEY","SUPABASE_URL","SERPER_API_KEY"]
               if not os.getenv(k)]
    return jsonify({
        "status": "ok" if not missing else "warning",
        "missing_vars": missing
    })

@app.route("/run", methods=["POST"])
def run():
    if not auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"status": "started"})

@app.route("/test", methods=["POST"])
def test():
    if not auth_ok():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"status": "test ok"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
```

Commit ✅ — חכה לירוק ואז פתח:
```
https://proplead-production.up.railway.app/health
