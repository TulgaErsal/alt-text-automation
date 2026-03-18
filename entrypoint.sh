#!/bin/bash
set -e

# ── Virtual display ────────────────────────────────────────────────────────────
# Xvfb provides an in-memory X11 screen so Firefox can run without a physical
# display.  DISPLAY=:99 is set in the Dockerfile ENV.
Xvfb :99 -screen 0 1280x900x24 -ac &
sleep 1   # give Xvfb time to be ready

# ── VNC server ─────────────────────────────────────────────────────────────────
# x11vnc mirrors the Xvfb display on VNC port 5900.
# Remove -nopw and add -passwd <secret> if you want VNC password protection.
x11vnc -display :99 -forever -nopw -shared -quiet &

# ── noVNC (web-based VNC client) ───────────────────────────────────────────────
# The operator opens http://<host>:6080/vnc.html to see and interact with the
# Firefox window for Google sign-in.  No client software is required.
websockify --web=/usr/share/novnc/ 6080 127.0.0.1:5900 &

# ── Ensure the Downloads folder exists ────────────────────────────────────────
# HOME may differ when OpenShift assigns an arbitrary UID, but the ENV value
# set in the Dockerfile keeps Path.home() pointing to /home/appuser.
mkdir -p "${HOME}/Downloads"

echo "┌─────────────────────────────────────────────────────────┐"
echo "│  Alt Text Automation — containerised                    │"
echo "│                                                         │"
echo "│  Upload interface : http://<host>:5000                  │"
echo "│  Browser (sign-in): http://<host>:6080/vnc.html         │"
echo "└─────────────────────────────────────────────────────────┘"

# ── Flask app ──────────────────────────────────────────────────────────────────
exec python web_app.py --host 0.0.0.0 --port 5000
