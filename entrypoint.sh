#!/bin/bash
set -e

# ── Virtual display ────────────────────────────────────────────────────────────
# Xvfb provides an in-memory X11 screen used only during the interactive
# sign-in step (non-headless Chromium).  Headless processing does not use it.
Xvfb :99 -screen 0 1280x900x24 -ac &
sleep 1   # give Xvfb time to be ready

# ── VNC server ─────────────────────────────────────────────────────────────────
# x11vnc mirrors the Xvfb display on VNC port 5900.
x11vnc -display :99 -forever -nopw -shared -quiet &

# ── noVNC (web-based VNC client on port 6080) ──────────────────────────────────
# Users open http://<host>:6080/vnc.html to see and interact with the Chromium
# window during their one-time sign-in to the AI Helper tool.
websockify --web=/usr/share/novnc/ 6080 127.0.0.1:5900 &

# ── Ensure runtime directories exist ──────────────────────────────────────────
mkdir -p "${HOME}/Downloads"
mkdir -p "${SESSIONS_DIR:-/data/sessions}"

echo "┌──────────────────────────────────────────────────────────┐"
echo "│  Alt Text Automation                                     │"
echo "│                                                          │"
echo "│  Web interface : http://<host>:5000                      │"
echo "│  Sign-in window: http://<host>:6080/vnc.html             │"
echo "│    (open this URL when prompted during first sign-in)    │"
echo "└──────────────────────────────────────────────────────────┘"

# ── Flask app ──────────────────────────────────────────────────────────────────
exec python web_app.py --host 0.0.0.0 --port 5000
