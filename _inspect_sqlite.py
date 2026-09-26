"""Inspect the local SQLite database before migrating it to Neon."""
import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.sqlite3")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

tables = [
    r[0]
    for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
]

print("SQLite file: %s (%d bytes)" % (DB, os.path.getsize(DB)))
print("Tables: %d" % len(tables))
print("=" * 78)

total_rows = 0
for t in tables:
    try:
        n = cur.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
    except Exception as exc:  # pragma: no cover
        print("%-45s ERROR %s" % (t, exc))
        continue
    total_rows += n
    marker = "" if n == 0 else "  <-- has data"
    print("%-45s %6d%s" % (t, n, marker))

print("=" * 78)
print("TOTAL ROWS ACROSS ALL TABLES: %d" % total_rows)

# Show a peek at the most important tables so we can verify later.
for t in ("auth_user", "website_profile", "website_candidatematch", "website_notification"):
    if t not in tables:
        continue
    print("\n--- %s sample ---" % t)
    cols = [d[1] for d in cur.execute('PRAGMA table_info("%s")' % t)]
    show = [c for c in ("username", "email", "legal_name", "company_name", "title", "is_superuser") if c in cols]
    if not show:
        show = cols[:3]
    for row in cur.execute('SELECT %s FROM "%s" LIMIT 3' % (", ".join(show), t)):
        print("   ", dict(row))

con.close()
sys.exit(0)
