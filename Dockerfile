FROM python:3.11-slim

# ── System packages ────────────────────────────────────────────────────────────
# Xvfb provides a virtual display so non-headless Chromium can run during the
# one-time interactive sign-in step.  x11vnc + noVNC make that display
# accessible as a web page (port 6080) so each user can complete their own
# Google sign-in without installing any software.
# Playwright's install-deps script handles Chromium's own OS dependencies, but
# we pre-install a few that are reliably needed on Debian slim images.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        x11vnc \
        novnc \
        websockify \
        # cairosvg native libraries (optional SVG support)
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-xlib-2.0-0 \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Playwright: download Chromium + its OS-level dependencies ─────────────────
# `playwright install-deps chromium` installs the shared libraries that the
# bundled Chromium binary needs (fonts, nss, etc.).
RUN playwright install chromium \
 && playwright install-deps chromium

# ── Application files ──────────────────────────────────────────────────────────
COPY generate_alt_text.py playwright_automation.py web_app.py ./
COPY templates/ templates/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# ── Runtime directories ────────────────────────────────────────────────────────
# OpenShift assigns an arbitrary non-root UID at runtime that is unknown at
# build time.  Making these directories world-writable ensures any UID can
# write to them without a chown step.
RUN mkdir -p /home/appuser/Downloads /data/sessions \
    && chmod -R 777 /home/appuser /data

# Path.home() in Python resolves $HOME; pinning it to /home/appuser ensures
# the "Downloads" output folder is always writable regardless of the runtime UID.
ENV HOME=/home/appuser \
    DISPLAY=:99 \
    SESSIONS_DIR=/data/sessions

# Flask web interface: 5000
# noVNC (browser window for per-user sign-in): 6080
EXPOSE 5000 6080

CMD ["/app/entrypoint.sh"]
