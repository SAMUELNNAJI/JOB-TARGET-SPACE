"""Verify every sqlite row landed in Neon, and check FK integrity."""
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

sq = sqlite3.connect(f"file:{BASE / 'db.sqlite3'}?mode=ro", uri=True)
sq.row_factory = sqlite3.Row
cur = connection.cursor()

TABLES = [
    "website_specialization", "auth_user", "website_profile",
    "website_candidatedocument", "website_recruitmentrequest",
    "website_notification", "website_auditlog",
]
problems = []

print("=" * 74)
print("ROW-BY-ROW VERIFICATION (sqlite source vs neon target)")
print("=" * 74)
for t in TABLES:
    src = list(sq.execute(f"SELECT * FROM {t} ORDER BY id"))
    tgt = list(cur.execute(f"SELECT * FROM {t} ORDER BY id"))
    src_ids = {r["id"] for r in src}
    tgt_ids = {r[0] for r in tgt}
    print(f"\n{t}: sqlite={len(src)} neon={len(tgt)}")
    if src_ids - tgt_ids:
        print(f"  !! pks absent by exact id: {sorted(src_ids - tgt_ids)}")
        problems.append(f"{t}: pk mismatch {sorted(src_ids - tgt_ids)}")
    else:
        print("  ok  every source pk exists in neon with the same id")

print("\n" + "=" * 74)
print("FIELD-LEVEL SPOT CHECK")
print("=" * 74)
for r in sq.execute("SELECT id,username,email,is_superuser,is_staff,is_active"
                    " FROM auth_user ORDER BY id"):
    hit = cur.execute("SELECT username,email,is_superuser,is_staff,is_active"
                      " FROM auth_user WHERE id=%s", [r["id"]]).fetchone()
    if not hit:
        print(f"  !! user {r['id']} ({r['email']}) MISSING in neon")
        problems.append(f"user {r['id']} missing")
        continue
    same = (hit[0] == r["username"] and hit[1] == r["email"]
            and hit[2] == r["is_superuser"] and hit[3] == r["is_staff"]
            and hit[4] == r["is_active"])
    print(f"  {'ok ' if same else 'DIFF'} user {r['id']:>3} {r['email']:28} "
          f"su={r['is_superuser']} staff={r['is_staff']}")
    if not same:
        problems.append(f"user {r['id']} field mismatch")

print("\n--- profiles ---")
for r in sq.execute("SELECT id,user_id,role,legal_name,company_name,"
                    "verification_status,expected_salary FROM website_profile"
                    " ORDER BY id"):
    hit = cur.execute("SELECT user_id,role,legal_name,company_name,"
                      "verification_status,expected_salary"
                      " FROM website_profile WHERE id=%s", [r["id"]]).fetchone()
    if not hit:
        print(f"  !! profile {r['id']} MISSING in neon")
        problems.append(f"profile {r['id']} missing")
        continue
    ok = (hit[0] == r["user_id"] and hit[1] == r["role"]
          and (hit[2] or "") == (r["legal_name"] or "")
          and (hit[3] or "") == (r["company_name"] or "")
          and hit[4] == r["verification_status"]
          and (hit[5] or 0) == (r["expected_salary"] or 0))
    print(f"  {'ok ' if ok else 'DIFF'} p{r['id']:>3} u{r['user_id']:<3} "
          f"{r['role']:9} name={r['legal_name']!r} co={r['company_name']!r} "
          f"status={r['verification_status']}")
    if not ok:
        problems.append(f"profile {r['id']} field mismatch")

print("\n--- notifications (FK -> profile) ---")
for r in sq.execute("SELECT id,profile_id,title,kind FROM website_notification"
                    " ORDER BY id"):
    hit = cur.execute("SELECT profile_id,title,kind FROM website_notification"
                      " WHERE id=%s", [r["id"]]).fetchone()
    ok = hit is not None and hit[0] == r["profile_id"] and hit[1] == r["title"]
    print(f"  {'ok ' if ok else 'DIFF'} n{r['id']:>3} profile={r['profile_id']} "
          f"{r['kind']:12} {r['title'][:44]!r}")
    if not ok:
        problems.append(f"notification {r['id']} mismatch")

print("\n--- audit logs (FK -> actor user) ---")
for r in sq.execute("SELECT id,actor_id,action FROM website_auditlog"
                    " ORDER BY id"):
    hit = cur.execute("SELECT actor_id,action FROM website_auditlog"
                      " WHERE id=%s", [r["id"]]).fetchone()
    ok = hit is not None and (hit[0] or 0) == (r["actor_id"] or 0)
    print(f"  {'ok ' if ok else 'DIFF'} a{r['id']:>3} actor={r['actor_id']} "
          f"{r['action'][:40]!r}")
    if not ok:
        problems.append(f"auditlog {r['id']} mismatch")

print("\n--- M2M profile -> specializations ---")
src_m2m = list(sq.execute("SELECT profile_id,specialization_id"
                          " FROM website_profile_specializations"
                          " ORDER BY profile_id"))
print(f"  sqlite rows ({len(src_m2m)}): {src_m2m}")
neon_m2m = list(cur.execute(
    "SELECT profile_id,specialization_id FROM website_profile_specializations"
    " ORDER BY profile_id"))
print(f"  neon   rows ({len(neon_m2m)}): {neon_m2m}")
if {tuple(r) for r in src_m2m} != {tuple(r) for r in neon_m2m}:
    problems.append("M2M specializations differ")

print("\n" + "=" * 74)
print("FK ORPHAN CHECK (neon)")
print("=" * 74)
for label, q in [
    ("profile -> user", "SELECT count(*) FROM website_profile p LEFT JOIN"
     " auth_user u ON p.user_id=u.id WHERE u.id IS NULL"),
    ("notification -> profile", "SELECT count(*) FROM website_notification n"
     " LEFT JOIN website_profile p ON n.profile_id=p.id WHERE p.id IS NULL"),
    ("auditlog -> user", "SELECT count(*) FROM website_auditlog a LEFT JOIN"
     " auth_user u ON a.actor_id=u.id WHERE u.id IS NULL"),
    ("candidatedoc -> profile", "SELECT count(*) FROM website_candidatedocument d"
     " LEFT JOIN website_profile p ON d.profile_id=p.id WHERE p.id IS NULL"),
    ("recruitreq -> employer", "SELECT count(*) FROM website_recruitmentrequest r"
     " LEFT JOIN website_profile p ON r.employer_id=p.id WHERE p.id IS NULL"),
]:
    n = cur.execute(q).fetchone()[0]
    print(f"  {'ok ' if n == 0 else '!! '}{label}: {n} orphans")
    if n:
        problems.append(f"{label}: {n} orphans")

print("\n" + "=" * 74)
if problems:
    print(f"PROBLEMS FOUND ({len(problems)}):")
    for p in problems:
        print("  -", p)
else:
    print("ALL CHECKS PASSED - neon matches sqlite")
print("=" * 74)

            and hit[2] == r["is_superuser"] and hit[3] == r["is_staff"]
            and hit[4] == r["is_active"])
    print(f"  {'ok ' if same else 'DIFF'} user {r['id']:>3} {r['email']:28} "
          f"su={r['is_superuser']} staff={r['is_staff']}")
    if not same:
        problems.append(f"user {r['id']} field mismatch")
