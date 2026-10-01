# JobSpace Django site

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/.

The existing design is rendered through the `website` app. Clean Django routes are available for each page, and the original `.html` URLs remain supported while links are migrated.

## Deploy To Render

This repository includes `render.yaml`. In Render, create a new Blueprint service from the repository and Render will provision the web service and PostgreSQL database.

The deployment uses:

- `gunicorn jobspace.wsgi:application` as the production web server.
- `python manage.py collectstatic --noinput` and `python manage.py migrate --noinput` during builds.
- WhiteNoise to serve collected static assets.
- Render's `DATABASE_URL` for PostgreSQL; SQLite remains the local-development fallback.

Render generates `SECRET_KEY` and sets `DEBUG=False` from the blueprint. Add your custom Render URL to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` if you use a custom domain.


## Deploy To A VPS (self-hosted)

For a VPS that already hosts other sites, see **[`deploy/DEPLOY.md`](deploy/DEPLOY.md)**.

Everything needed is in `deploy/`:

| File | Purpose |
|---|---|
| `deploy/DEPLOY.md` | The full step-by-step guide, plus a troubleshooting table |
| `deploy/nginx/jobspace.conf` | A new, self-contained nginx site (a Unix socket to gunicorn, TLS, static/media aliases) |
| `deploy/systemd/jobspace.service` | The gunicorn service, with migrations and `collectstatic` run automatically on every start |
| `deploy/deploy.sh` | Pull, install, restart, and wait for the site to answer |
| `.env.example` | Every environment variable the VPS needs, with notes on each |

This setup is **additive and isolated**: it adds one new nginx server block and
one new systemd unit, and never edits `nginx.conf`, the `default` site, or
anything belonging to a site already on the box. gunicorn listens on a Unix
socket rather than a TCP port, so it adds no open port to the firewall, and the
app runs as its own unprivileged `jobspace` user with its own virtualenv.

To deploy a new version:

```bash
sudo -u jobspace bash /var/www/jobspace/deploy/deploy.sh
```

Two things to be aware of, both detailed in `deploy/DEPLOY.md`: **uploaded
files are currently public to anyone with the URL** (the templates link to
`doc.file.url` directly, with no ownership check), and **`media/` lives on the
server disk**, so it needs its own backup strategy.

Uploaded files are stored under `media/`. Render's filesystem is ephemeral, so configure persistent disk storage or an object store before relying on user-uploaded documents in production.
