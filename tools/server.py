#!/usr/bin/env python3
"""
server.py — Eric's Footy Site
Lightweight Flask server that serves the frontend and exposes article data via REST API.

SOP: architecture/server_sop.md
"""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, send_from_directory, send_file
from flask_cors import CORS

# ─── Paths ───────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
FRONTEND_DIR = ROOT / "frontend"
DATA_FILE = ROOT / "data" / "articles.json"
SCRAPER = ROOT / "tools" / "scraper.py"

# ─── App Setup ────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=str(FRONTEND_DIR))
CORS(app)

PORT = int(os.environ.get("PORT", 5000))

# ─── Scrape State ─────────────────────────────────────────────────────────────
# Shared state for background scrape job.
# Using a dict + threading.Lock instead of class to keep it simple.
_scrape_lock = threading.Lock()
scrape_state = {
    "running": False,
    "last_error": None,
    "last_success": None,  # ISO timestamp of last successful scrape
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def read_articles() -> dict:
    """Read and return the articles JSON payload. Returns empty state if missing."""
    if not DATA_FILE.exists():
        return {"last_updated": None, "total_count": 0, "articles": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Error reading {DATA_FILE}: {e}", file=sys.stderr)
        return {"last_updated": None, "total_count": 0, "articles": []}


def run_scraper() -> tuple[bool, str]:
    """Invoke scraper.py as a subprocess. Returns (success, message)."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRAPER)],
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute max (embed resolution adds ~60s)
        )
        if result.returncode != 0:
            err = result.stderr or "Unknown error"
            print(f"❌ Scraper failed:\n{err}", file=sys.stderr)
            return False, err
        return True, result.stdout
    except subprocess.TimeoutExpired:
        return False, "Scraper timed out after 300 seconds"
    except Exception as e:
        return False, str(e)


def _run_scraper_background():
    """
    Run the scraper in a background thread, updating scrape_state when done.
    Called only from trigger_scrape() — never directly.
    """
    print("🔄 Background scrape started")
    success, message = run_scraper()
    with _scrape_lock:
        scrape_state["running"] = False
        if success:
            payload = read_articles()
            scrape_state["last_success"] = payload.get("last_updated")
            scrape_state["last_error"] = None
            print("✅ Background scrape complete")
        else:
            scrape_state["last_error"] = message
            print(f"❌ Background scrape failed: {message}", file=sys.stderr)


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard."""
    return send_file(FRONTEND_DIR / "index.html")


@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(FRONTEND_DIR / "css", filename)


@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(FRONTEND_DIR / "js", filename)


@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(FRONTEND_DIR / "assets", filename)


@app.route("/api/articles", methods=["GET"])
def get_articles():
    """Return the current articles payload from data/articles.json."""
    payload = read_articles()
    return jsonify(payload)


@app.route("/api/scrape", methods=["POST"])
def trigger_scrape():
    """
    Start a background scrape job and return immediately (202 Accepted).
    The frontend should poll /api/scrape/status and then /api/articles.
    Returns 409 if a scrape is already in progress.
    """
    with _scrape_lock:
        if scrape_state["running"]:
            return jsonify({"status": "already_running"}), 409
        scrape_state["running"] = True
        scrape_state["last_error"] = None

    print("🔄 Manual scrape triggered via /api/scrape")
    t = threading.Thread(target=_run_scraper_background, daemon=True)
    t.start()
    return jsonify({"status": "started"}), 202


@app.route("/api/scrape/status", methods=["GET"])
def scrape_status():
    """
    Poll this endpoint to check whether a background scrape is still running.
    Response shape:
      { running: bool, last_error: str|null, last_success: str|null }
    """
    with _scrape_lock:
        return jsonify(dict(scrape_state))


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    data_exists = DATA_FILE.exists()
    return jsonify({
        "status": "ok",
        "data_file_exists": data_exists,
        "data_file": str(DATA_FILE),
    })


# ─── Startup Bootstrap ───────────────────────────────────────────────────────
# Runs whether started via `python server.py` OR gunicorn (module-level).
if not DATA_FILE.exists():
    print("\n📭 No data file found — running initial scrape...")
    success, msg = run_scraper()
    if success:
        print("✅ Initial scrape complete")
    else:
        print(f"⚠️  Initial scrape failed: {msg}\n   Starting server anyway.")

# ─── Dev entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n⚽  Eric's Footy Site — Server starting")
    print(f"   Root:     {ROOT}")
    print(f"   Frontend: {FRONTEND_DIR}")
    print(f"   Data:     {DATA_FILE}")
    print(f"\n🚀 Server ready at http://localhost:{PORT}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)
