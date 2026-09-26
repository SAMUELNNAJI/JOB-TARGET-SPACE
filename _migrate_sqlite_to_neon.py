"""Read-only audit: SQLite (source) vs Neon (target). Part 1: counts + collisions."""
import os
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.apps import apps  # noqa: E402

OUT = []
def w(s=""):
    OUT.append(str(s))

MODELS = list(apps.get_app_config("website").get_models())
w("=" * 70)
w("MODELS IN CODE")
w("=" * 70)
for m in MODELS:
    w(f"  {m._meta.db_table:38s} {m.__name__}")

from django.db.migrations.recorder import MigrationRecorder  # noqa: E402
rec = MigrationRecorder(connection)
w()
w("NEON applied website migrations: "
  + ", ".join(a[1] for a in rec.applied_migrations() if a[0] == "website"))

sq = sqlite3.connect(f"file:{BASE / 'db.sqlite3'}?mode=ro", uri=True)
sq.row_factory = sqlite3.Row
sq_tables = {r[0] for r in sq.execute(
    "SELECT name FROM sqlite_master WHERE type='table'")}
neon_tables = set(connection.introspection.table_names())

w()
w("=" * 70)
w("ROW COUNTS            sqlite -> neon")
w("=" * 70)
EXTRA = ["auth_user", "auth_group", "auth_permission", "auth_user_groups",
         "auth_user_user_permissions", "django_content_type",
         "django_admin_log", "django_session", "django_migrations"]
for m in MODELS:
    t = m._meta.db_table
    s = sq.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] if t in sq_tables else "-"
    n = connection.cursor().execute(
        f"SELECT COUNT(*) FROM {t}").fetchone()[0] if t in neon_tables else "-"
    w(f"  {t:38s} {str(s):>6s} -> {n}")
for t in EXTRA:
    s = sq.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] if t in sq_tables else "-"
    n = connection.cursor().execute(
        f"SELECT COUNT(*) FROM {t}").fetchone()[0] if t in neon_tables else "-"
    w(f"  {t:38s} {str(s):>6s} -> {n}")

w()
w("=" * 70)
w("USERS  (id | username | email | staff | su | active)")
w("=" * 70)
w("-- SQLITE --")
s_users = {}
for r in sq.execute("SELECT id,username,email,is_staff,is_superuser,is_active"
                    " FROM auth_user ORDER BY id"):
    s_users[r["id"]] = (r["username"], r["email"])
    w(f"  {r['id']} | {r['username']:20s} | {r['email']:30s} | "
      f"staff={r['is_staff']} su={r['is_superuser']} act={r['is_active']}")
w("-- NEON --")
n_users = {}
for r in connection.cursor().execute(
        "SELECT id,username,email,is_staff,is_superuser,is_active"
        " FROM auth_user ORDER BY id"):
    n_users[r[0]] = (r[1], r[2])
    w(f"  {r[0]} | {r[1]:20s} | {r[2]:30s} | staff={r[3]} su={r[4]} act={r[5]}")

w()
w("COLLISION CHECK (match by username, then email):")
for uid, (u, e) in s_users.items():
    by_name = [k for k, v in n_users.items() if v[0] == u]
    by_mail = [k for k, v in n_users.items() if v[1] == e]
    w(f"  sqlite u{uid} {u:20s} -> neon_by_name={by_name or 'new'}"
      f"  neon_by_email={by_mail or 'new'}")

w()
w("=" * 70)
w("PROFILES  (id | user_id | role | legal_name | status)")
w("=" * 70)
def cols(tbl):
    return {r[1] for r in sq.execute(f"PRAGMA table_info({tbl})")}
pcols = cols("website_profile")
w(f"  website_profile columns: {sorted(pcols)}")
sel = [c for c in ("id", "user_id", "role", "legal_name",
                   "verification_status") if c in pcols]
w("-- SQLITE --")
for r in sq.execute(f"SELECT {','.join(sel)} FROM website_profile ORDER BY id"):
    w("  p{:<3d} | u{:<3d} | {:10s} | {}".format(
        r["id"], r["user_id"], r["role"], r["legal_name"]))
w("-- NEON --")
try:
    nsel = [c for c in ("id", "user_id", "role", "legal_name",
                        "verification_status")]
    for r in connection.cursor().execute(
            f"SELECT {','.join(nsel)} FROM website_profile ORDER BY id"):
        w("  p{:<3d} | u{:<3d} | {:10s} | {}".format(
            r[0], r[1], r[2], r[3]))
except Exception as e:
    w(f"  ERROR: {e}")

w()
w("=" * 70)
w("SPECIALIZATIONS  (sqlite_id=name -> neon_id)")
w("=" * 70)
s_specs = {r["id"]: r["name"] for r in
           sq.execute("SELECT id,name FROM website_specialization ORDER BY id")}
n_specs = {r[0]: r[1] for r in connection.cursor().execute(
    "SELECT id,name FROM website_specialization ORDER BY id")}
for i, nme in s_specs.items():
    match = [k for k, v in n_specs.items() if v == nme]
    w(f"  s{i} '{nme}' -> {match or 'MISSING'}")
w(f"  neon-only specs: {[(k, v) for k, v in n_specs.items() if v not in s_specs.values()]}")

w()
w("M2M through tables in sqlite:")
for t in sorted(sq_tables):
    if "profile_specializations" in t:
        cnt = sq.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        w(f"  {t:44s} {cnt}")
        for r in sq.execute(f"SELECT * FROM {t}"):
            w(f"      {dict(r)}")

(BASE / "_audit1.txt").write_text("\n".join(OUT), encoding="utf-8")
print("\n".join(OUT))
