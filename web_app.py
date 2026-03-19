#!/usr/bin/env python3
"""
web_app.py  –  Flask web interface for the Alt Text Automation tool.

Run:
    cp .env.example .env   # fill in SECRET_KEY, GOOGLE_CLIENT_ID/SECRET
    pip install flask authlib playwright
    playwright install chromium
    python web_app.py

Each user signs in with their own UMich Google account.  After a one-time
interactive sign-in to the AI Helper tool (via the noVNC browser window), their
Playwright storageState is saved to SESSIONS_DIR.  All subsequent processing
runs headlessly using that stored session; the session survives container
restarts as long as SESSIONS_DIR is backed by a PersistentVolumeClaim.
"""

import io
import json
import os
import queue
import sys
import tempfile
import threading
import uuid
from functools import wraps
from pathlib import Path

# Load .env file if present (no-op when running in a container with real env vars).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from flask import (
        Flask, Response, jsonify, redirect,
        render_template, request, send_file, session, url_for,
    )
    from werkzeug.middleware.proxy_fix import ProxyFix
    from werkzeug.utils import secure_filename
except ImportError:
    sys.exit("Missing dependency: pip install flask")

try:
    from authlib.integrations.flask_client import OAuth
except ImportError:
    sys.exit("Missing dependency: pip install authlib")

import playwright_automation as pa
from playwright_automation import AuthExpiredError
from generate_alt_text import PURPOSE_OPTIONS, TONE_OPTIONS

# ── App setup ──────────────────────────────────────────────────────────────────

app = Flask(__name__)
# Respect X-Forwarded-Proto / X-Forwarded-Host from OpenShift's ingress so that
# url_for(..., _external=True) produces the correct HTTPS redirect URI for OAuth.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024   # 200 MB
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(32)

DEFAULT_URL = "https://aihelper.engin.umich.edu/alt-text-generator"

# URL of the noVNC web client used for the interactive sign-in step.
# In OpenShift set this to the route for port 6080, e.g.
#   https://alt-text-vnc.apps.cluster.example.com/vnc.html
# Leave empty to let the JS fall back to window.location.hostname:6080/vnc.html
NOVNC_URL = os.environ.get("NOVNC_URL", "")

# ── Google OAuth ───────────────────────────────────────────────────────────────

oauth  = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url=(
        "https://accounts.google.com/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            # API callers get a JSON 401; browser requests get a redirect.
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not authenticated"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def _user_id() -> str:
    return session["user_id"]


# ── Job registry ───────────────────────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ── Auth routes ────────────────────────────────────────────────────────────────

@app.route("/login")
def login():
    redirect_uri = url_for("login_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/login/callback")
def login_callback():
    token     = google.authorize_access_token()
    user_info = token.get("userinfo") or google.userinfo()
    session["user_id"]   = user_info["email"]
    session["user_name"] = user_info.get("name", user_info["email"])
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ── Main route ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    user = None
    if "user_id" in session:
        user = {
            "id":   session["user_id"],
            "name": session.get("user_name", session["user_id"]),
        }
    return render_template(
        "index.html",
        user=user,
        purpose_options=list(PURPOSE_OPTIONS.keys()),
        tone_options=list(TONE_OPTIONS.keys()),
        default_url=DEFAULT_URL,
        novnc_url=NOVNC_URL,
    )


# ── API: status ────────────────────────────────────────────────────────────────

@app.route("/api/status")
@login_required
def api_status():
    user_id   = _user_id()
    ai_status = pa.get_signin_status(user_id)

    # If no in-memory status but a session file exists (e.g. after a container
    # restart), treat the user as already connected.
    if ai_status["status"] == "none" and pa.has_session(user_id):
        ai_status = {"status": "ready", "msg": "Session restored."}

    return jsonify({
        "user":          {"id": user_id, "name": session.get("user_name", user_id)},
        "ai_helper":     ai_status,
        "signin_locked": not pa.signin_lock_available(),
    })


# ── API: AI Helper sign-in ─────────────────────────────────────────────────────

@app.route("/api/ai-connect", methods=["POST"])
@login_required
def api_ai_connect():
    user_id = _user_id()
    data    = request.get_json(silent=True) or {}
    url     = (data.get("url") or DEFAULT_URL).strip()

    started = pa.start_signin(user_id, url)
    if not started:
        return jsonify({
            "error": (
                "Another user is currently signing in. "
                "Please try again in a few minutes."
            )
        }), 409
    return jsonify({"status": "connecting"})


@app.route("/api/ai-disconnect", methods=["POST"])
@login_required
def api_ai_disconnect():
    user_id = _user_id()
    pa.delete_session(user_id)
    pa.set_signin_status(user_id, "none")
    return jsonify({"status": "disconnected"})


# ── API: process ───────────────────────────────────────────────────────────────

@app.route("/api/process", methods=["POST"])
@login_required
def api_process():
    user_id   = _user_id()
    ai_status = pa.get_signin_status(user_id)

    # Accept "ready" from in-memory state or from a persisted session file.
    connected = (
        ai_status["status"] == "ready"
        or (ai_status["status"] == "none" and pa.has_session(user_id))
    )
    if not connected:
        return jsonify({
            "error": "Not connected. Please sign in to the AI Helper tool first."
        }), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    pptx_file = request.files["file"]
    if not (pptx_file.filename or "").lower().endswith(".pptx"):
        return jsonify({"error": "File must be a .pptx file."}), 400

    version = request.form.get("version", "long")
    if version not in ("short", "medium", "long"):
        version = "long"

    purpose = request.form.get("purpose") or None
    if purpose and purpose not in PURPOSE_OPTIONS:
        purpose = None

    tone = request.form.get("tone") or None
    if tone and tone not in TONE_OPTIONS:
        tone = None

    includes: list[str] = []
    if request.form.get("include_data_values"):
        includes.append("data-values")
    if request.form.get("include_captions"):
        includes.append("captions")

    url = (request.form.get("url") or DEFAULT_URL).strip()

    # Save upload to a temp file.
    tmp_in = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
    pptx_file.save(tmp_in.name)
    tmp_in.close()
    input_path = Path(tmp_in.name)

    # Output file in the server's Downloads folder.
    original_stem = Path(secure_filename(pptx_file.filename or "file")).stem
    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    output_path   = downloads_dir / f"{original_stem}_alt_text.pptx"
    counter = 1
    while output_path.exists():
        output_path = downloads_dir / f"{original_stem}_alt_text_{counter}.pptx"
        counter += 1

    # Register job.
    job_id     = str(uuid.uuid4())
    log_q      = queue.Queue()
    stop_event = threading.Event()

    with _jobs_lock:
        _jobs[job_id] = {
            "user_id":     user_id,
            "status":      "running",
            "output_path": output_path,
            "output_name": output_path.name,
            "log_queue":   log_q,
            "stop_event":  stop_event,
            "input_path":  input_path,
            "error":       None,
        }

    def worker():
        class _QueueWriter(io.TextIOBase):
            def write(self, text):
                if text:
                    log_q.put({"type": "log", "text": text})
                return len(text)

            def flush(self):
                pass

        old_stdout = sys.stdout
        sys.stdout = _QueueWriter()
        try:
            pa.run_batch_headless(
                user_id=user_id,
                pptx_path=input_path,
                output_path=output_path,
                tool_url=url,
                version=version,
                purpose=purpose,
                includes=includes,
                tone=tone,
                stop_event=stop_event,
            )
            with _jobs_lock:
                if stop_event.is_set():
                    _jobs[job_id]["status"] = "aborted"
                    log_q.put({"type": "aborted"})
                else:
                    _jobs[job_id]["status"] = "done"
                    log_q.put({"type": "done", "job_id": job_id})

        except AuthExpiredError as exc:
            # Session expired mid-processing — clear it so the UI prompts re-auth.
            pa.delete_session(user_id)
            pa.set_signin_status(user_id, "none", str(exc))
            err = str(exc) + "  Please sign in to the AI Helper tool again."
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"]  = err
            log_q.put({"type": "auth_expired", "text": err})

        except Exception as exc:
            err = str(exc)
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"]  = err
            log_q.put({"type": "error", "text": err})

        finally:
            sys.stdout = old_stdout
            log_q.put(None)          # sentinel — signals the SSE stream to close
            try:
                input_path.unlink(missing_ok=True)
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


# ── API: progress stream ───────────────────────────────────────────────────────

@app.route("/api/progress/<job_id>")
@login_required
def api_progress(job_id: str):
    user_id = _user_id()
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or job["user_id"] != user_id:
        return jsonify({"error": "Job not found"}), 404

    log_q: queue.Queue = job["log_queue"]

    def generate():
        while True:
            item = log_q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── API: stop / download ───────────────────────────────────────────────────────

@app.route("/api/stop/<job_id>", methods=["POST"])
@login_required
def api_stop(job_id: str):
    user_id = _user_id()
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or job["user_id"] != user_id:
        return jsonify({"error": "Job not found"}), 404
    job["stop_event"].set()
    return jsonify({"status": "stopping"})


@app.route("/api/download/<job_id>")
@login_required
def api_download(job_id: str):
    user_id = _user_id()
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or job["user_id"] != user_id:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] not in ("done", "aborted"):
        return jsonify({"error": "Job not complete"}), 400

    output_path: Path = job["output_path"]
    if not output_path.exists():
        return jsonify({"error": "Output file not found"}), 404

    response = send_file(
        output_path,
        as_attachment=True,
        download_name=job["output_name"],
        mimetype=(
            "application/vnd.openxmlformats-officedocument"
            ".presentationml.presentation"
        ),
    )

    try:
        output_path.unlink(missing_ok=True)
    except Exception:
        pass
    with _jobs_lock:
        _jobs.pop(job_id, None)

    return response


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Alt Text Automation – web interface"
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    print(f"Starting Alt Text Automation web server on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
