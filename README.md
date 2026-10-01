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
one new systemd unit, and never edits `nginx.conf` or either of the files
belonging to a site already on the box. gunicorn listens on `127.0.0.1:8010`
— loopback only, so no new port is opened in the firewall — and the app runs
as its own unprivileged `jobspace` user with its own virtualenv.

To deploy a new version:

```bash
sudo -u jobspace bash /var/www/jobspace/deploy/deploy.sh
```

## Payments

There is **no payment gateway**. Employers are shown the company's account
details, they transfer the money themselves, then upload a screenshot as proof;
an admin then approves or declines it in the admin payments screen. Nothing is
activated automatically, and there is no webhook.

A Flutterwave integration previously existed and was removed. It was never
wired into any template, and its webhook accepted unsigned POSTs whenever the
shared secret was unset — which let anyone mark their own subscription paid.

## SEO

The eight public marketing pages are the only indexable pages. Each has a
unique title and meta description, a canonical URL, Open Graph and Twitter card
tags, and schema.org JSON-LD. `/sitemap.xml` and `/robots.txt` are generated
from the same source of truth (`website/seo.py`).

Everything private — every `/dashboard/` page, `/admin/`, the auth pages and
the file-download URLs — is served with `noindex, nofollow` and is excluded from
the sitemap. This matters for privacy, not just tidiness: a crawled dashboard
would expose a candidate's CVs and the private download URLs.

The metadata is emitted by a context processor, so it is correct on every page
without any view opting in. If you add a base template, include
`templates/includes/seo_head.html` in its `<head>`.

## Security notes

- **Uploaded files are private.** CVs, payment proofs and voice notes are
  served only to their owner (or staff) through permission-checked views, and
  `/media/` returns 404 in production. Previously any of them could be
  downloaded by anyone who had the URL — see `deploy/DEPLOY.md`.
- **Uploaded files live on the server disk**, so they need a backup strategy,
  and they must never be committed to git. 28 real CVs were committed by
  accident at some point; they are untracked now but still in history.

Uploaded files are stored under `media/`. Render's filesystem is ephemeral, so configure persistent disk storage or an object store before relying on user-uploaded documents in production.
