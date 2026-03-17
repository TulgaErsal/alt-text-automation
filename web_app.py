#!/usr/bin/env python3
"""
web_app.py  –  Flask web interface for generate_alt_text.py

Run:
    pip install flask
    python web_app.py

Then open http://localhost:5000 in your browser.
The person running the server must authenticate with Google once via the
browser that opens on the server machine; after that, any user can upload
and process .pptx files through the web UI.
"""

import io
import json
import os
import queue
import sys
import tempfile
import threading
import uuid
from pathlib import Path

try:
    from flask import Flask, Response, jsonify, render_template, request, send_file
    from werkzeug.utils import secure_filename
except ImportError:
    sys.exit("Missing dependency: pip install flask")

from generate_alt_text import (
    PURPOSE_OPTIONS,
    INCLUDE_OPTIONS,
    TONE_OPTIONS,
    build_driver,
    wait_for_auth,
    run_batch,
    _LOCAL_GECKODRIVER,
    _SESSION_LOST_EXCEPTIONS,
)

# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

DEFAULT_URL = "https://aihelper.engin.umich.edu/alt-text-generator"

# ── Global browser state ──────────────────────────────────────────────────────
# Only one browser session is active at a time.

_driver = None
_driver_lock = threading.Lock()

# One of: disconnected | launching | waiting | ready | timeout | error
_browser_status = "disconnected"
_browser_status_msg = ""
_status_lock = threading.Lock()
_connecting = False


def _set_status(status: str, msg: str = "") -> None:
    global _browser_status, _browser_status_msg
    with _status_lock:
        _browser_status = status
        _browser_status_msg = msg


def _get_status() -> dict:
    with _status_lock:
        return {"status": _browser_status, "msg": _browser_status_msg}


# ── Job registry ──────────────────────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ── Routes ────────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template(
        "index.html",
        purpose_options=list(PURPOSE_OPTIONS.keys()),
        tone_options=list(TONE_OPTIONS.keys()),
        default_url=DEFAULT_URL,
    )


@app.route("/api/status")
def api_status():
    return jsonify(_get_status())


@app.route("/api/connect", methods=["POST"])
def api_connect():
    global _driver, _connecting

    with _driver_lock:
        if _connecting:
            return jsonify({"error": "Already connecting"}), 409
        _connecting = True

    data = request.get_json(silent=True) or {}
    browser = data.get("browser", "auto")
    url = (data.get("url") or DEFAULT_URL).strip()
    gecko_str = (data.get("geckodriver") or "").strip()
    geckodriver: Path | None = None
    if gecko_str:
        geckodriver = Path(gecko_str)
    elif _LOCAL_GECKODRIVER.exists():
        geckodriver = _LOCAL_GECKODRIVER

    def connect_worker():
        global _driver, _connecting
        _set_status("launching")
        try:
            # Shut down any existing session
            with _driver_lock:
                if _driver is not None:
                    try:
                        _driver.quit()
                    except Exception:
                        pass
                    _driver = None  # type: ignore[assignment]

            driver = build_driver(browser, geckodriver)

            with _driver_lock:
                _driver = driver  # type: ignore[assignment]

            _set_status("waiting", "Please complete Google sign-in in the browser window.")
            wait_for_auth(driver, url, raise_on_timeout=True)
            _set_status("ready", "Signed in ✓  Ready to process files.")
        except TimeoutError:
            with _driver_lock:
                _driver = None  # type: ignore[assignment]
            _set_status("timeout", "Sign-in timed out. Click Reconnect to try again.")
        except Exception as exc:
            with _driver_lock:
                _driver = None  # type: ignore[assignment]
            _set_status("error", str(exc))
        finally:
            _connecting = False

    threading.Thread(target=connect_worker, daemon=True).start()
    return jsonify({"status": "connecting"})


@app.route("/api/disconnect", methods=["POST"])
def api_disconnect():
    global _driver
    with _driver_lock:
        if _driver is not None:
            try:
                _driver.quit()
            except Exception:
                pass
            _driver = None  # type: ignore[assignment]
    _set_status("disconnected")
    return jsonify({"status": "disconnected"})


@app.route("/api/process", methods=["POST"])
def api_process():
    if _get_status()["status"] != "ready":
        return jsonify({"error": "Browser not connected. Please connect and sign in first."}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    pptx_file = request.files["file"]
    if not (pptx_file.filename or "").lower().endswith(".pptx"):
        return jsonify({"error": "File must be a .pptx file."}), 400

    # Parse form options
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

    # Save upload to temp file
    tmp_in = tempfile.NamedTemporaryFile(suffix=".pptx", delete=False)
    pptx_file.save(tmp_in.name)
    tmp_in.close()
    input_path = Path(tmp_in.name)

    # Prepare output path in the user's Downloads folder
    original_stem = Path(secure_filename(pptx_file.filename or "file")).stem
    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    output_path = downloads_dir / f"{original_stem}_alt_text.pptx"
    # Avoid overwriting an existing file by appending a counter
    counter = 1
    while output_path.exists():
        output_path = downloads_dir / f"{original_stem}_alt_text_{counter}.pptx"
        counter += 1

    # Register job
    job_id = str(uuid.uuid4())
    log_q: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    with _jobs_lock:
        _jobs[job_id] = {
            "status": "running",
            "output_path": output_path,
            "output_name": output_path.name,
            "log_queue": log_q,
            "stop_event": stop_event,
            "input_path": input_path,
            "error": None,
        }

    def worker():
        global _driver

        class _QueueWriter(io.TextIOBase):
            def write(self, text):  # type: ignore[override]
                if text:
                    log_q.put({"type": "log", "text": text})
                return len(text)

            def flush(self):
                pass

        old_stdout = sys.stdout
        sys.stdout = _QueueWriter()
        try:
            with _driver_lock:
                drv = _driver
            if drv is None:
                raise RuntimeError("Browser not connected.")

            run_batch(
                driver=drv,
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

        except _SESSION_LOST_EXCEPTIONS as exc:
            with _driver_lock:
                _driver = None  # type: ignore[assignment]
            _set_status("disconnected", "Browser session was lost.")
            err = "Browser session was lost. Please reconnect and sign in again."
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = err
            log_q.put({"type": "error", "text": err})

        except Exception as exc:
            err = str(exc)
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = err
            log_q.put({"type": "error", "text": err})

        finally:
            sys.stdout = old_stdout
            log_q.put(None)  # sentinel — tells SSE stream to close
            try:
                input_path.unlink(missing_ok=True)
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/api/progress/<job_id>")
def api_progress(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
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


@app.route("/api/stop/<job_id>", methods=["POST"])
def api_stop(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    job["stop_event"].set()
    return jsonify({"status": "stopping"})


@app.route("/api/download/<job_id>")
def api_download(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] not in ("done", "aborted"):
        return jsonify({"error": "Job not complete"}), 400

    output_path: Path = job["output_path"]
    if not output_path.exists():
        return jsonify({"error": "Output file not found"}), 404

    return send_file(
        output_path,
        as_attachment=True,
        download_name=job["output_name"],
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Alt Text Automation – web interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    args = parser.parse_args()

    print(f"Starting Alt Text Automation web server on http://{args.host}:{args.port}")
    print("Open that URL in your browser, then click 'Connect Browser' to sign in.")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
