#!/usr/bin/env bash
#
# deploy.sh — pull the latest code onto the VPS and restart Target JobSpace.
#
# Run as root (or a user with full sudo), from the project directory:
#   sudo bash /var/www/jobspace/deploy/deploy.sh
#
# Or as the jobspace user if /etc/sudoers.d/jobspace grants NOPASSWD on
# systemctl restart/status jobspace:
#   sudo -u jobspace bash /var/www/jobspace/deploy/deploy.sh
#
set -o errexit
set -o nounset
set -o pipefail

APP_DIR=/var/www/jobspace
VENV="$APP_DIR/venv"
SERVICE=jobspace

cd "$APP_DIR"

# ── 1. Pull latest code ────────────────────────────────────────────────────
echo "==> Fetching latest code"
git pull --ff-only origin main

# ── 2. Install / upgrade Python dependencies ──────────────────────────────
echo "==> Installing dependencies"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt

# ── 3. Fix permissions so nginx can read static + media ───────────────────
echo "==> Setting permissions"
# jobspace owns /var/www/jobspace — chmod that directly without sudo.
# /var/www itself needs 755 but only root can change it; if it is already
# 755 (set once by root during initial setup) this is a no-op, and if it
# is not, the || true means the script continues to the restart step rather
# than blocking on a password prompt.
chmod 755 /var/www/jobspace 2>/dev/null || true
chmod -R a+rX "$APP_DIR/staticfiles" "$APP_DIR/media" 2>/dev/null || true

# ── 4. Restart the service ────────────────────────────────────────────────
echo "==> Restarting $SERVICE"
# Try sudo first; fall back to systemctl directly (works when already root).
if command -v sudo &>/dev/null && sudo -n systemctl restart "$SERVICE" 2>/dev/null; then
    echo "    Restarted via sudo systemctl."
elif systemctl restart "$SERVICE" 2>/dev/null; then
    echo "    Restarted via systemctl (running as root)."
else
    echo ""
    echo "!!! Could not restart the service automatically." >&2
    echo "!!! Run this manually as root:" >&2
    echo "!!!   sudo systemctl restart $SERVICE" >&2
    echo "!!! Then check the logs with:" >&2
    echo "!!!   sudo journalctl -u $SERVICE -n 60 --no-pager" >&2
    echo ""
    echo "==> Code and dependencies are updated. Only the restart is pending."
    exit 1
fi

# ── 5. Wait for gunicorn to come up ───────────────────────────────────────
echo "==> Waiting for gunicorn on 127.0.0.1:8010 ..."
for attempt in $(seq 1 30); do
    # Use localhost header — matches ALLOWED_HOSTS default (127.0.0.1).
    # Accepts both 200 and 301/302 as "up" (301 = HTTPS redirect is fine).
    http_code=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Host: 127.0.0.1" http://127.0.0.1:8010/ 2>/dev/null || echo "000")
    if [[ "$http_code" =~ ^(200|301|302|400)$ ]]; then
        echo "==> Gunicorn is responding (HTTP $http_code). Deploy complete."
        exit 0
    fi
    sleep 1
done

echo ""
echo "!!! Gunicorn did not respond on port 8010 after 30 seconds." >&2
echo "!!! Check the logs:" >&2
echo "!!!   sudo journalctl -u $SERVICE -n 60 --no-pager" >&2
echo "!!! Common causes:" >&2
echo "!!!   - DATABASE_URL missing or wrong in /var/www/jobspace/.env" >&2
echo "!!!   - A failing migration in ExecStartPre" >&2
echo "!!!   - collectstatic failing (missing STATIC_ROOT or bad S3 config)" >&2
echo "!!!   - Wrong python/gunicorn path (check venv is at $VENV)" >&2
sudo journalctl -u "$SERVICE" -n 60 --no-pager 2>/dev/null || \
    journalctl -u "$SERVICE" -n 60 --no-pager 2>/dev/null || true
exit 1
