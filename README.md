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

Uploaded files are stored under `media/`. Render's filesystem is ephemeral, so configure persistent disk storage or an object store before relying on user-uploaded documents in production.
