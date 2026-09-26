"""Repair Neon after the sqlite->Neon data migration.

Fixes three problems the live run left behind:
  1. Sequences left behind by explicit-PK inserts (breaks every new signup).
  2. Duplicate candidate-document rows.
  3. Test-artifact users that slipped in before EXCLUDE_EMAILS existed.

Safe to re-run. Always takes a dumpdata backup first.
Use --dry-run to preview.
"""
import os
import sys
import datetime
import warnings
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")

warnings.filterwarnings("ignore", category=RuntimeWarning, module="django.db")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connection, transaction  # noqa: E402

DRY = "--dry-run" in sys.argv
TestUser = get_user_model()
Profile = apps.get_model("website", "Profile")
Doc = apps.get_model("website", "CandidateDocument")

TEST_EMAILS = ["dbg@example.com", "pce@example.com"]


def hdr(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


hdr("REPAIR NEON" + ("  (DRY RUN - nothing written)" if DRY else "  (LIVE)"))
print(f"host: {connection.settings_dict['HOST']}")

if not DRY:
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = BASE / f"_neon_backup_repair_{stamp}.json"
    call_command("dumpdata", "--natural-foreign", "--natural-primary",
                 output=str(backup), verbosity=0)
    print(f"[backup] {backup.name} ({backup.stat().st_size / 1024:.1f} KB)")

# ── 1. Remove test-artifact accounts and everything hanging off them ────────
hdr("1. TEST-ARTIFACT USERS")
for email in TEST_EMAILS:
    for u in TestUser.objects.filter(email__iexact=email):
        profs = list(Profile.objects.filter(user=u))
        print(f"  delete user {u.pk} <{u.email}> "
              f"+ {len(profs)} profile(s) {profs and [p.pk for p in profs]}")
        if DRY:
            continue
        with transaction.atomic():
            u.delete()  # cascades to profile, docs, notifications, audit rows

# ── 2. Remove duplicate candidate documents ────────────────────────────────
hdr("2. DUPLICATE CANDIDATE DOCUMENTS")
seen = {}
for d in Doc.objects.order_by("profile_id", "file", "id"):
    key = (d.profile_id, d.file)
    if key in seen:
        keep = seen[key]
        print(f"  doc {d.pk} duplicates doc {keep.pk} "
              f"(profile {d.profile_id}, {d.file}) -> delete {d.pk}")
        if not DRY:
            d.delete()
    else:
        seen[key] = d
if not seen:
    print("  (no duplicates)")
print(f"  {Doc.objects.count()} document(s) remain")

# ── 3. Resync every sequence to MAX(pk) ────────────────────────────────────
hdr("3. SEQUENCE RESYNC")
print("Explicit-PK inserts (dumpdata/loaddata) do NOT advance sequences, so")
print("every table below is resynced to MAX(pk). Next insert gets MAX(pk)+1.\n")
print(f"  {'table':32} {'pk':10} {'max_pk':>7} {'next':>7} {'after':>7}  status")

# Derive table/PK pairs from Django's model registry, then ask Postgres which
# sequence backs each PK. Do NOT assume a "<table>_id_seq" naming scheme:
# django_session's PK is session_key and has no sequence at all, and
# pg_get_serial_sequence() already returns a schema-qualified name.
fixed = 0
skipped = 0
with connection.cursor() as cur:
    seen_tables = set()
    for model in sorted(apps.get_models(), key=lambda m: m._meta.db_table):
        table = model._meta.db_table
        if table in seen_tables or not model._meta.managed:
            continue
        seen_tables.add(table)

        for fld in model._meta.concrete_fields:
            if not getattr(fld, "primary_key", False):
                continue
            col = fld.column
            try:
                seq = cur.execute(
                    "SELECT pg_get_serial_sequence(%s, %s)",
                    [f'public."{table}"', col],
                ).fetchone()[0]
            except Exception as exc:  # noqa: BLE001
                print(f"  {table:32} {col:10} SKIP ({type(exc).__name__}: {exc})")
                skipped += 1
                continue

            if not seq:
                # e.g. django_session.session_key - no sequence to sync.
                print(f"  {table:32} {col:10} {'':>7} {'':>7} {'':>7}  "
                      f"no sequence (non-serial pk)")
                skipped += 1
                continue

            try:
                max_pk = cur.execute(
                    f'SELECT COALESCE(MAX("{col}"), 0) FROM "{table}"'
                ).fetchone()[0]
                last, called = cur.execute(
                    "SELECT last_value, is_called FROM " + seq).fetchone()
            except Exception as exc:  # noqa: BLE001
                print(f"  {table:32} {col:10} SKIP ({type(exc).__name__}: {exc})")
                skipped += 1
                continue

            before = last + 1 if called else last
            # setval(seq, n, true) -> the next nextval() returns n+1 = MAX(pk)+1.
            # For empty tables start at 1 so the first insert yields 1.
            if DRY:
                # setval() is a WRITE -- never run it in a dry run.
                after = 1 if max_pk == 0 else max_pk + 1
            else:
                if max_pk == 0:
                    cur.execute("SELECT setval(%s, 1, false)", [seq])
                else:
                    cur.execute("SELECT setval(%s, %s, true)", [seq, max_pk])
                last2, called2 = cur.execute(
                    "SELECT last_value, is_called FROM " + seq).fetchone()
                after = last2 + 1 if called2 else last2

            was_ok = before > max_pk
            if not was_ok:
                fixed += 1
            print(f"  {table:32} {col:10} {max_pk:>7} {before:>7} {after:>7}  "
                  f"{'ok' if was_ok else 'FIXED'}")

print(f"\n  {fixed} sequence(s) repaired, {skipped} table(s) skipped "
      f"(non-serial pk), {len(seen_tables)} table(s) inspected")

hdr("DONE" if not DRY else "DRY RUN COMPLETE - no changes written")
if DRY:
    print("Re-run without --dry-run to apply.")

