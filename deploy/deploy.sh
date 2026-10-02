#!/usr/bin/env bash
#
# deploy.sh — pull the latest code onto the VPS and restart Target JobSpace.
#
# Run as the `jobspace` user, from anywhere:
#   sudo -u jobspace bash /var/www/jobspace/deploy/deploy.sh
#
# What this does NOT do: it never touches nginx, never touches the systemd
# unit, and never touches the other two sites on this box. Nginx and the
# certificate are configuration that changes rarely, not per deploy.
#
set -o errexit    # stop on the first failure
set -o nounset    # error on an undefined variable
set -o pipefail   # catch failures inside pipes

APP_DIR=/var/www/jobspace
DOMAIN="jobspace.example.com"   # CHANGE THIS to your real domain
cd "$APP_DIR"

echo "==> Fetching latest code"
# The repository is owned by `jobspace` so this never needs sudo or a token.
git pull --ff-only origin main

echo "==> Installing dependencies"
# The virtualenv is outside the source tree's control; do not recreate it.
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# collectstatic and migrate both run automatically in the unit's ExecStartPre,
# before gunicorn binds the port. Running them here too would do the work
# twice, so they are deliberately NOT repeated.

# ── Permissions ────────────────────────────────────────────────────────────
# useradd created this directory mode 700, so nginx — a different user — cannot
# traverse into it to read staticfiles/ and media/. Without this, every
# stylesheet and uploaded file 403s while the app itself works fine, which is
# a confusing failure. The app is unaffected: it runs as `jobspace`, which
# still has full access. Only read access is granted to everyone else.
#
# This runs AFTER the pull on purpose. git can recreate those directories, and
# a deploy would otherwise silently undo the fix.
chmod 755 /var/www /var/www/jobspace
chmod -R a+rX /var/www/jobspace/staticfiles /var/www/jobspace/media 2>/dev/null || true

echo "==> Restarting the service"
# On failure, print the log tail and stop. The old workers keep serving until
# the unit comes back up, so a bad deploy is a failed request, not downtime.
if ! sudo systemctl restart jobspace; then
    echo "!!! Restart failed. Recent log output:" >&2
    sudo journalctl -u jobspace -n 50 --no-pager >&2
    exit 1
fi

echo "==> Waiting for gunicorn to answer on 127.0.0.1:8010"
# Check gunicorn DIRECTLY, not through nginx on port 80. Going through nginx
# would hit the 301 to HTTPS, which tells us nothing about whether the app is
# up. The Host header must match ALLOWED_HOSTS or Django returns 400.
for attempt in $(seq 1 30); do
    if curl -fsS -o /dev/null -H "Host: $DOMAIN" \
        http://127.0.0.1:8010/ 2>/dev/null; then
        echo "==> Site is responding."
        exit 0
    fi
    sleep 1
done

echo "!!! gunicorn not responding on 8010 after 30s." >&2
echo "!!! If the site is up in a browser, this is usually ALLOWED_HOSTS" >&2
echo "!!! not containing '$DOMAIN' — Django answers 400 for unknown hosts." >&2
sudo journalctl -u jobspace -n 50 --no-pager >&2
exit 1
