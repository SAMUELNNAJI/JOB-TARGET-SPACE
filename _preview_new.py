"""Final step: purge test artifacts, fix sequences, verify parity."""
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

# Subjects produced by my throwaway verification scripts, not real activity.
TEST_SUBJECT = ("%Acme Test Co%", "%Good Candidate%", "%Second Candidate%")
TEST_EMAILS = ["pce@example.com", "dbg@example.com"]

print("=" * 70)
print("STEP 1 - purge test artifacts from the SQLITE source")
print("=" * 70)
sq = sqlite3.connect(str(BASE / "db.sqlite3"))
sq.row_factory = sqlite3.Row
n = sq.execute(
    "SELECT COUNT(*) FROM website_auditlog WHERE subject LIKE ? "
    "OR subject LIKE ? OR subject LIKE ?", TEST_SUBJECT).fetchone()[0]
sq.execute("DELETE FROM website_auditlog WHERE subject LIKE ? "
           "OR subject LIKE ? OR subject LIKE ?", TEST_SUBJECT)
for e in TEST_EMAILS:
    sq.execute("DELETE FROM auth_user WHERE email = ?", (e,))
sq.execute("DELETE FROM website_profile WHERE user_id NOT IN "
           "(SELECT id FROM auth_user)")
sq.commit()
print(f"  removed {n} test audit rows from sqlite; dropped test users")
print("  sqlite audit rows remaining: "
      f"{sq.execute('SELECT COUNT(*) FROM website_auditlog').fetchone()[0]}")
sq.close()

print("\n" + "=" * 70)
print("STEP 2 - remove 13-byte stub CV files (test uploads)")
print("=" * 70)
media = BASE / "media"
stubs = 0
for f in sorted(media.rglob("*")) if media.exists() else []:
    if f.is_file() and f.stat().st_size == 13:
        f.unlink()
        stubs += 1
        print(f"  deleted stub {f.name}")
print(f"  {stubs} stub files removed; real uploads left in place")
for f in sorted(media.rglob("*")) if media.exists() else []:
    if f.is_file():
        print(f"  KEPT {f.relative_to(BASE)} ({f.stat().st_size} bytes)")

print("\n" + "=" * 70)
print("STEP 3 - purge test rows that may already exist in Neon")
print("=" * 70)
with connection.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM website_auditlog WHERE subject LIKE %s "
                "OR subject LIKE %s OR subject LIKE %s", TEST_SUBJECT)
    n2 = cur.fetchone()[0]
    cur.execute("DELETE FROM website_auditlog WHERE subject LIKE %s "
                "OR subject LIKE %s OR subject LIKE %s", TEST_SUBJECT)
    for e in TEST_EMAILS:
        cur.execute("SELECT id FROM auth_user WHERE email = %s", [e])
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM auth_user WHERE id = %s", [row[0]])
            print(f"  deleted neon test user {e}")
    cur.execute("DELETE FROM website_candidatedocument d WHERE EXISTS ("
                "SELECT 1 FROM website_candidatedocument e WHERE "
                "e.profile_id = d.profile_id AND e.file = d.file "
                "AND e.id < d.id)")
print(f"  removed {n2} test audit rows from neon")

print()
print("=" * 70)
print("STEP 4 - reset PK sequences (prevents broken inserts on Render)")
print("=" * 70)
with connection.cursor() as cur:
    tables = [r[0] for r in cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE' "
        "AND table_name <> 'django_migrations' ORDER BY table_name")]
    fixed = 0
    for t in tables:
        seq = cur.execute("SELECT pg_get_serial_sequence(%s,'id')", [t]).fetchone()[0]
        if not seq:
            continue
        maxid = cur.execute(f"SELECT COALESCE(MAX(id),0) FROM {t}").fetchone()[0]
        cur.execute("SELECT setval(%s, %s, true)", [seq, max(maxid, 1)])
        fixed += 1
        print(f"   {t:34s} max_id={maxid:<5} sequence -> {max(maxid,1)}")
    print(f"   {fixed} sequences reset")

print()
print("=" * 70)
print("STEP 5 - final parity check (sqlite vs neon)")
print("=" * 70)
sq = sqlite3.connect(f"file:{BASE / 'db.sqlite3'}?mode=ro", uri=True)
ok = True
with connection.cursor() as cur:
    for t in ["website_specialization", "auth_user", "website_profile",
              "website_candidatedocument", "website_recruitmentrequest",
              "website_candidatematch", "website_notification",
              "website_auditlog"]:
        s = sq.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        d = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        flag = "OK" if s == d else "*** MISMATCH ***"
        if s != d:
            ok = False
        print(f"   {t:32s} sqlite={s:<4} neon={d:<4} {flag}")
    print()
    print("   -- sequence health --")
    for t in tables:
        seq = cur.execute("SELECT pg_get_serial_sequence(%s,'id')", [t]).fetchone()[0]
        if not seq:
            continue
        last, called = cur.execute("SELECT last_value, is_called FROM " + seq).fetchone()
        maxid = cur.execute(f"SELECT COALESCE(MAX(id),0) FROM {t}").fetchone()[0]
        if called and last < maxid:
            ok = False
            print(f"   *** BROKEN {t}: seq={last} < max={maxid}")
    print("   all sequences healthy" if ok else "   *** problems above ***")