"""Prove the CV media route resolves with DEBUG=False (Render's setting)."""
import os
import sys
import warnings
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ["DJANGO_SETTINGS_MODULE"] = "jobspace.settings"
os.environ["DEBUG"] = "False"
os.environ["ALLOWED_HOSTS"] = "*"
warnings.filterwarnings("ignore", category=RuntimeWarning, module="django.db")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402

print(f"DEBUG              = {settings.DEBUG}")
print(f"MEDIA_ROOT         = {settings.MEDIA_ROOT}")
print(f"MEDIA_URL          = {settings.MEDIA_URL}")
print(f"database vendor    = {connection.vendor}")

doc = connection.cursor().execute(
    "SELECT file FROM website_candidatedocument ORDER BY id LIMIT 1"
).fetchone()
if not doc:
    print("no candidate document row found")
    sys.exit(1)

rel = doc[0]
url = f"{settings.MEDIA_URL}{rel}"
print(f"\nstored path        = {rel}")
print(f"on disk            = {(settings.MEDIA_ROOT / rel).exists()}")
print(f"requesting         = {url}")

c = Client()
resp = c.get(url)
print(f"\nHTTP status        = {resp.status_code}")
if resp.status_code == 200:
    body = b"".join(resp.streaming_content) if resp.streaming else resp.content
    print(f"bytes served       = {len(body)}")
    print(f"content-type       = {resp.get('Content-Type')}")
    ok = len(body) > 1000
else:
    print(f"body               = {resp.content[:200]!r}")
    ok = False

print("\n" + ("PASS: CV is reachable with DEBUG=False"
               if ok else "FAIL: CV not reachable"))
