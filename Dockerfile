FROM python:3.11-slim

# ── System packages ────────────────────────────────────────────────────────────
# Firefox for browser automation, Xvfb for a virtual display (no screen in a
# container), x11vnc + noVNC so the server operator can sign in to Google by
# opening http://<host>:6080/vnc.html in their own browser.
RUN apt-get update && apt-get install -y --no-install-recommends \
        firefox-esr \
        wget \
        ca-certificates \
        xvfb \
        x11vnc \
        novnc \
        websockify \
        # cairosvg native libraries (optional SVG support)
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ── geckodriver (Linux x86-64) ─────────────────────────────────────────────────
ARG GECKODRIVER_VERSION=0.34.0
RUN wget -q \
        "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" \
        -O /tmp/gd.tar.gz \
    && tar -xzf /tmp/gd.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/geckodriver \
    && rm /tmp/gd.tar.gz

# ── Python dependencies ────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application files ──────────────────────────────────────────────────────────
COPY generate_alt_text.py web_app.py ./
COPY templates/ templates/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# ── Runtime directories ────────────────────────────────────────────────────────
# OpenShift runs containers as an arbitrary non-root UID chosen at deploy time.
# Making these directories world-writable ensures any UID can write to them.
RUN mkdir -p /home/appuser/Downloads \
    && chmod -R 777 /home/appuser

# Path.home() in Python resolves $HOME; setting it here points "Downloads" to a
# known, writable path regardless of which UID OpenShift assigns at runtime.
ENV HOME=/home/appuser \
    DISPLAY=:99

# Flask web interface: 5000
# noVNC (remote browser for Google sign-in): 6080
EXPOSE 5000 6080

CMD ["/app/entrypoint.sh"]
