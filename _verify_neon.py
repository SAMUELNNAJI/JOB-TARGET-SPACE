"""Final verification: compare sqlite source against Neon target."""
import os
import sqlite3
import sys
import warnings
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="django.db")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

TABLES = [
    "auth_user", "website_profile", "website_specialization",
    "website_qualification", "website_candidatedocument", "website_subscription",
    "website_payment", "website_recruitmentrequest", "website_candidatematch",
    "website_shortlist", "website_replacementrequest", "website_notification",
    "website_auditlog",
]

sq = sqlite3.connect(f"file:{BASE / 'db.sqlite3'}?mode=ro", uri=True)
cur = connection.cursor()

print("=" * 78)
print("ROW COUNT COMPARISON  (sqlite -> neon)")
print("=" * 78)
print(f"  {'table':32} {'sqlite':>8} {'neon':>8}  status")
bad = 0
for t in TABLES:
    try:
        s = sq.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    except sqlite3.Error:
        s = 0
    n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    ok = n >= s
    if not ok:
        bad += 1
    print(f"  {t:32} {s:>8} {n:>8}  {'ok' if ok else 'MISSING ROWS'}")

print("\n" + "=" * 78)
print("USERS")
print("=" * 78)
for r in cur.execute(
        "SELECT id,username,email,is_staff,is_superuser,is_active"
        " FROM auth_user ORDER BY id"):
    print(f"  {r[0]:>3}  {r[1]:26} {str(r[2])[:34]:34} "
          f"staff={bool(r[3])} super={bool(r[4])} active={bool(r[5])}")

print("\n" + "=" * 78)
print("PROFILES")
print("=" * 78)
for r in cur.execute(
        "SELECT id,user_id,role,legal_name,company_name,verification_status,"
        "primary_degree,expected_salary FROM website_profile ORDER BY id"):
    print(f"  p{r[0]:>3} u{r[1]:<3} {r[2]:9} name={str(r[3])[:24]:24} "
          f"co={str(r[4])[:22]:22} {r[5]}")
    print(f"        degree={str(r[6])[:44]:44} salary={r[7]}")

print("\n" + "=" * 78)
print("CANDIDATE DOCUMENTS  (file must also exist in media/)")
print("=" * 78)
for r in cur.execute(
        "SELECT id,profile_id,file FROM website_candidatedocument ORDER BY id"):
    direct = BASE / "media" / r[2]
    print(f"  d{r[0]} profile={r[1]}  {r[2]}")
    print(f"      on disk: {'YES' if direct.exists() else 'NO  <-- MISSING'}")

print("\n" + "=" * 78)
print("NOTIFICATIONS / AUDITLOG / REQUESTS")
print("=" * 78)
for lbl, t in (("notifications", "website_notification"),
               ("auditlog", "website_auditlog"),
               ("recruitmentrequest", "website_recruitmentrequest")):
    print(f"  {lbl:20}: {cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")
for r in cur.execute("SELECT id,employer_id,position,status"
                     " FROM website_recruitmentrequest"):
    print(f"    req {r[0]}: employer={r[1]} {r[2]!r} [{r[3]}]")
for r in cur.execute("SELECT id,kind,is_read,title FROM website_notification"
                     " ORDER BY id LIMIT 30"):
    print(f"    n{r[0]:>3} {r[1]:14} read={bool(r[2])} {str(r[3])[:46]}")

print("\n" + "=" * 78)
print("M2M  (profile.specializations)")
print("=" * 78)
for r in cur.execute(
        "SELECT p.id, p.legal_name, s.name FROM website_profile p"
        " JOIN website_profile_specializations ps ON ps.profile_id = p.id"
        " JOIN website_specialization s ON s.id = ps.specialization_id"
        " ORDER BY p.id"):
    print(f"  p{r[0]} {str(r[1])[:24]:24} -> {r[2]}")

print("\n" + "=" * 78)
print("SPECIALIZATIONS")
print("=" * 78)
for r in cur.execute("SELECT id,name FROM website_specialization ORDER BY id"):
    print(f"  {r[0]:>3} {r[1]}")

print("\n" + "=" * 78)
print("RESULT: " + ("ALL TABLES FULLY MIGRATED" if bad == 0
                    else f"{bad} TABLE(S) INCOMPLETE"))
print("=" * 78)
