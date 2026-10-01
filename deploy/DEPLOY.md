# ─────────────────────────────────────────────────────────────────────────────
# JobSpace — deploying to THIS server (AlmaLinux 8, nginx in conf.d/)
# ─────────────────────────────────────────────────────────────────────────────

Everything in `deploy/` is additive. Nothing here edits `nginx.conf` or either
of the two files belonging to the sites already on this box:

- `/etc/nginx/conf.d/selectroyalmaids.com.ng.conf`
- `/etc/nginx/conf.d/getmecare.conf`

This server is **AlmaLinux 8**, so the package manager is `dnf` (not `apt`),
and nginx uses `/etc/nginx/conf.d/*.conf` with **no** `sites-available` /
`sites-enabled` split. There is no `default` site to worry about.

**Hardware note: this box has 1 CPU and ~1.9 GB RAM, shared with two other live
sites.** The gunicorn unit is sized down to 2 workers × 2 threads to match. Do
not raise the worker count — it will starve the other two sites.

## Before you start

1. **The domain's A record points at this VPS.** Verify with
   `dig +short yourdomain.com`. A wrong record is the #1 reason certbot fails.
2. **Which PostgreSQL holds the real data.** If this site is already live,
   point `DATABASE_URL` at that same database. A brand new one gives you a
   working site with no users and no payment history.
3. **Which domain name you are using.** You will replace
   `jobspace.example.com` in the nginx file (4 places), in `.env` (2 places)
   and in `deploy/deploy.sh` (1 place).
4. **SSH access and root.** Everything runs as root except the app itself,
   which runs as the unprivileged `jobspace` user.

> **Do not run `dnf update` or change anything global.** The other two sites
> depend on the current state of this machine.

---

## Step 1 — Confirm what you have

Most of this is already installed (nginx and certbot are). Check before
installing anything:

```bash
cat /etc/os-release
systemctl --version | head -1
nginx -v
command -v git certbot dnf
rpm -q postgresql-server
```

## Step 2 — Packages

Only install what is actually missing — this list is a safety net, not a
blanket install:

```bash
dnf install -y git
dnf install -y python3.12 python3.12-devel    # only if step 5 says it fails
dnf install -y postgresql-server              # only if there is no managed DB
```

`python3` on this box is **3.6.8**, which is too old for Django 5. A
`python3.12` binary already exists at `/usr/bin/python3.12` — use that
explicitly everywhere. Never rely on bare `python3`.

## Step 3 — The user and directory

```bash
useradd --system --create-home --home-dir /var/www/jobspace --shell /usr/sbin/nologin jobspace
mkdir -p /var/www/jobspace
chown jobspace:jobspace /var/www/jobspace
```

## Step 4 — The code

`/var/www/jobspace` already exists and contains only `.bashrc` and friends from
`useradd`, so a fresh `git clone` will refuse. Clear it and clone:

```bash
rm -rf /var/www/jobspace
useradd --system --create-home --home-dir /var/www/jobspace --shell /usr/sbin/nologin jobspace
git clone https://github.com/SAMUELNNAJI/JOB-TARGET-SPACE.git /var/www/jobspace
chown -R jobspace:jobspace /var/www/jobspace
```

> **The `rm -rf` is safe only right now**, while the directory holds nothing but
> the three skeleton dotfiles from `useradd`. Never run it again once the app
> is deployed — it would delete `media/`, which holds every uploaded CV and is
> **not** in git. Later updates use `deploy/deploy.sh`, never a reclone.

## Step 5 — The virtualenv

Kept at `/var/www/jobspace/venv`, outside the repo, so `git pull` can never
disturb it. Uses the explicit 3.12 path, never bare `python3`.

```bash
sudo -u jobspace /usr/bin/python3.12 -m venv /var/www/jobspace/venv
sudo -u jobspace /var/www/jobspace/venv/bin/pip install --upgrade pip
sudo -u jobspace /var/www/jobspace/venv/bin/pip install -r /var/www/jobspace/requirements.txt
```

If the venv step fails with "No module named venv", install the matching
module from Step 2 (`python3.12` and `python3.12-devel` must be the same
version) and retry.

## Step 6 — The database

**Skip this entire step if the site is already live elsewhere** — in that case
just point `DATABASE_URL` at that existing database (a managed one such as Neon
is fine and is what the Render setup uses).

AlmaLinux initialises Postgres differently from Debian — there is no
`pg_ctlcluster`, you use `postgresql-setup`:

```bash
dnf install -y postgresql-server
postgresql-setup --initdb
systemctl enable --now postgresql
```

Then create the role and database:

```bash
sudo -u postgres psql
```

```sql
CREATE USER jobspace WITH PASSWORD 'use-a-real-password-here';
CREATE DATABASE jobspace OWNER jobspace;
\q
```

> On a 1.9 GB box, a local Postgres competes for the same RAM as the two
> existing sites and gunicorn. A managed database is the better choice here if
> you have one available.

## Step 7 — The environment file

```bash
sudo -u jobspace cp /var/www/jobspace/.env.example /var/www/jobspace/.env
sudo -u jobspace nano /var/www/jobspace/.env
```

Set `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
at minimum. See `.env.example` for what each one does. Then lock it down:

```bash
sudo chown jobspace:jobspace /var/www/jobspace/.env
sudo chmod 600 /var/www/jobspace/.env
```

> `.env` holds the secret key and the database password. It is git-ignored.
> Do not commit it, and do not paste its contents into a chat or an issue.

## Step 8 — The systemd service

```bash
cp /var/www/jobspace/deploy/systemd/jobspace.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now jobspace
systemctl status jobspace
```

Migrations and `collectstatic` run automatically as `ExecStartPre`, before
gunicorn binds the port. **Always read the log** — this is where most failures
show up:

```bash
journalctl -u jobspace -n 50 --no-pager
```

## Step 9 — File permissions (do not skip)

`useradd` created `/var/www/jobspace` with mode `700`. nginx runs as a
**different user**, so it cannot even traverse into that directory — every
stylesheet and uploaded file would return **403** while the app itself worked
fine. That is a confusing failure, so fix it now:

```bash
chmod 755 /var/www /var/www/jobspace
systemctl restart jobspace          # re-runs collectstatic
chmod -R a+rX /var/www/jobspace/staticfiles /var/www/jobspace/media
```

`deploy.sh` repeats these on every deploy, after the `git pull`, because git can
recreate those directories and silently undo the fix.

## Step 10 — nginx

Edit your domain into the config first — it appears in **four** places
(two `server_name`, two `ssl_certificate`):

```bash
nano /var/www/jobspace/deploy/nginx/jobspace.conf
```

Then install it as a **new** file in `conf.d/`. Nothing existing is modified —
this box has no `sites-available`/`sites-enabled` split, so no symlink is
involved:

```bash
cp /var/www/jobspace/deploy/nginx/jobspace.conf /etc/nginx/conf.d/jobspace.conf
```

**Test before reloading. Always.** If this fails, nothing on disk has changed
and the running config is untouched — your other two sites are unaffected:

```bash
nginx -t && systemctl reload nginx
```

Use `reload`, never `restart` — it does not drop the other sites' connections.

Verify the other two sites are still in place afterwards:

```bash
ls -l /etc/nginx/conf.d/
```

Both `selectroyalmaids.com.ng.conf` and `getmecare.conf` must still be listed.

## Step 11 — The certificate

DNS must be pointing here first. Verify with `dig +short yourdomain.com` — if
it does not show this server's IP, stop and wait for DNS to propagate.

```bash
certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

certbot rewrites **this file only** — it fills in the certificate paths and
replaces the port-80 block with a redirect. The other two site configs are not
touched. That rewrite is expected.

Confirm renewal is scheduled:

```bash
certbot renew --dry-run
```

## Step 12 — Enable the stricter HTTPS settings

Only **after** `https://yourdomain.com` loads correctly in a browser:

```bash
nano /var/www/jobspace/.env
```

```diff
-SECURE_SSL_REDIRECT=False
-SECURE_HSTS_SECONDS=0
+SECURE_SSL_REDIRECT=True
+SECURE_HSTS_SECONDS=31536000
```

```bash
systemctl restart jobspace
```

> Read the Django HSTS notes before this step. A browser that has cached HSTS
> will refuse plain HTTP for that domain for the full year, and a broken
> certificate afterwards is unfixable for those browsers until it expires.

## Step 13 — Verify

```bash
# System checks — this should list no issues
sudo -u jobspace /var/www/jobspace/venv/bin/python /var/www/jobspace/manage.py check --deploy

# Create the first admin user
sudo -u jobspace /var/www/jobspace/venv/bin/python /var/www/jobspace/manage.py createsuperuser
```

Then confirm, in a browser:

- `https://yourdomain.com` loads, and `http://` redirects to `https://`
- the stylesheet loads (proves `collectstatic` + the Step 9 permissions)
- you can sign in at `/signin/` and reach `/admin/`
- you can upload a CV (proves the 20M limit and the media path)
- **the other two sites still load** — check them explicitly, every time

**Reboot test** — worth doing once, because it proves the service comes back on
its own and is not relying on anything you did by hand:

```bash
reboot
```

Wait ~60s, reconnect, then re-check the site and the other two.

---

## Everyday deploys

```bash
sudo -u jobspace bash /var/www/jobspace/deploy/deploy.sh
```

Pulls code, installs dependencies, fixes the permissions, restarts, and waits
for gunicorn to answer on 127.0.0.1:8010.

**Before the first run**, set your domain on line 17 of that script so its
health check sends the right `Host` header:

```bash
nano /var/www/jobspace/deploy/deploy.sh
```

## When something breaks

```bash
systemctl status jobspace      # is it running?
journalctl -u jobspace -f      # live logs — most useful command here
journalctl -u jobspace -n 200 --no-pager
tail -f /var/log/nginx/jobspace.error.log
```

Most common causes, in the order they actually happen:

| Symptom | Cause | Fix |
|---|---|---|
| Every page is HTTP 400 | `ALLOWED_HOSTS` does not contain the domain | Fix `.env`, restart |
| Site works on http, blank page on https | `collectstatic` not run, or nginx `alias` path wrong | Check `journalctl`, then re-run `collectstatic --noinput` |
| "Internal Server Error" on every page | Service failed at start | `journalctl -u jobspace -n 50` — usually a bad `.env` or an unreachable database |
| **Styling missing, everything else fine** | **nginx cannot read `/var/www/jobspace` (mode 700)** | **Step 9: `chmod 755 /var/www /var/www/jobspace` then restart** |
| **502 Bad Gateway** | gunicorn not listening on 8010 | `systemctl status jobspace`; `ss -lntp \| grep 8010` |
| Uploads fail with 413 | `client_max_body_size` too low | It is 20M; raise it in the nginx config if genuinely needed |
| Redirect loop | `SECURE_SSL_REDIRECT=True` with no working certificate | Set it to `False`, fix the cert, then re-enable |
| Certificate expired / wrong domain | certbot did not run for this server | `certbot renew`, confirm the renewal cron exists |
| 403 on files, app is fine | SELinux denying nginx read access | See below |
| Site unreachable from the internet | firewalld blocking 80/443 | See below |

### The two AlmaLinux-specific gotchas

**SELinux.** AlmaLinux ships with SELinux in enforcing mode. If nginx is
denied access to your files you will see "Permission denied" in
`/var/log/audit/audit.log` even though the unix permissions look correct:

```bash
getenforce                                    # Enforcing = problem is possible
tail -20 /var/log/audit/audit.log | grep nginx
```

Confirm before changing anything — `ausearch -m avc -ts recent` gives the exact
denial. Then allow nginx to read the app directory:

```bash
semanage fcontext -a -t httpd_sys_content_t "/var/www/jobspace/staticfiles(/.*)?"
semanage fcontext -a -t httpd_sys_content_t "/var/www/jobspace/media(/.*)?"
restorecon -Rv /var/www/jobspace
systemctl reload nginx
```

Only do this if you have actually seen an SELinux denial. It is not needed
otherwise, and `semanage` comes from `policycoreutils-python-utils`.

**firewalld.** Both 80 and 443 must be open:

```bash
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
firewall-cmd --list-services
```

**Nothing needs opening for gunicorn.** It binds `127.0.0.1:8010`, which is
loopback only and is not reachable from the internet. Never bind it to
`0.0.0.0`.

---

## Two things to know before you rely on this

**1. Uploaded files are public to anyone with the URL.** CVs, payment proofs
and voice notes are served from `/media/` at predictable paths, and the links
in the templates are plain `<a href="{{ doc.file.url }}">`. Anyone who learns
or guesses a URL can open that file without logging in. The nginx config
forces `Content-Disposition: attachment` so an uploaded HTML or SVG file
cannot run script under your domain, but that stops cross-site scripting, not
the download itself. If CVs must be private, the fix is to move them behind an
authenticated download view that checks the requester owns the document, and
add `X-Accel-Redirect` instead of the public `alias`. That is an application
change, not a deployment change, so it is not done here.

**2. `media/` lives on the VPS disk, not in the database.** Unlike Render,
this disk is persistent, so uploads survive a redeploy — but not a `rm -rf`.
If you ever rebuild the server, the database will still hold rows pointing at
files that are gone. Keep a backup:

```bash
sudo -u jobspace tar czf /var/backups/jobspace-media-$(date +%F).tar.gz -C /var/www/jobspace media
```

`tools/voice_notes.py audit` reports uploaded files that the database
references but that are missing from `media/` — useful after any restore.
