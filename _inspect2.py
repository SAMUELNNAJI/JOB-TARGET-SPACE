"""Inspect the legacy SQLite DB: schema columns + data that must move to Neon."""
import sqlite3

con = sqlite3.connect("db.sqlite3")
con.row_factory = sqlite3.Row

print("=" * 70)
print("candidatedocument cols:", [d[1] for d in con.execute("PRAGMA table_info(website_candidatedocument)")])
for r in con.execute("select * from website_candidatedocument"):
    print("  doc:", dict(r))

print("=" * 70)
print("profile_specializations:", list(con.execute("select * from website_profile_specializations")))
print("=" * 70)
print("profile cols:", [d[1] for d in con.execute("PRAGMA table_info(website_profile)")])
for r in con.execute("select id,user_id,role,legal_name,company_name,verification_status,updated_at from website_profile"):
    print("  profile:", dict(r))
print("=" * 70)
print("notification cols:", [d[1] for d in con.execute("PRAGMA table_info(website_notification)")])
for r in con.execute("select * from website_notification"):
    print("  notif:", dict(r))
print("=" * 70)
for r in con.execute("select * from website_recruitmentrequest"):
    print("  req:", dict(r))
print("=" * 70)
for r in con.execute("select * from website_auditlog"):
    print("  log:", dict(r))
print("=" * 70)
for r in con.execute("select * from auth_user"):
    d = dict(r)
    d["password"] = str(d["password"])[:18] + "...hash"
    print("  user:", d)
print("=" * 70)
print("auth_permission:", con.execute("select count(*) from auth_permission").fetchone()[0])
print("content_type:", [tuple(r) for r in con.execute("select id,app_label,model from django_content_type")])
print("migrations rows:", con.execute("select count(*) from django_migrations").fetchone()[0])
print("sessions:", con.execute("select count(*) from django_session").fetchone()[0])
con.close()
