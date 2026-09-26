"""Debug: why does the sequence-discovery query return nothing?"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

QUERIES = {
    "A: information_schema nextval columns": """
        SELECT table_name, column_name, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND column_default LIKE 'nextval(%'
        ORDER BY table_name
    """,
    "B: pg_depend rows for auth_user_id_seq": """
        SELECT d.classid::regclass::text, d.objsubid, d.refclassid::regclass::text,
               d.refobjsubid, d.deptype
        FROM pg_class s
        JOIN pg_depend d ON d.objid = s.oid
        WHERE s.relname = 'auth_user_id_seq' AND s.relkind = 'S'
    """,
}

with connection.cursor() as cur:
    for label, sql in QUERIES.items():
        print(f"\n--- {label}")
        try:
            rows = cur.execute(sql).fetchall()
            print(f"    {len(rows)} row(s)")
            for r in rows[:6]:
                print(f"      {r}")
        except Exception as exc:  # noqa: BLE001
            print(f"    ERROR {type(exc).__name__}: {exc}")

# The approach the repair will actually use: Django's own model registry for
# the table/PK list, then pg_get_serial_sequence() per column.
print("\n--- django models + pg_get_serial_sequence")
from django.apps import apps  # noqa: E402

seen = set()
with connection.cursor() as cur:
    models = sorted(apps.get_models(), key=lambda m: m._meta.db_table)
    for model in models:
        table = model._meta.db_table
        if table in seen or not model._meta.managed:
            continue
        seen.add(table)
        for fld in model._meta.concrete_fields:
            if not getattr(fld, "primary_key", False):
                continue
            col = fld.column
            try:
                seq = cur.execute(
                    "SELECT pg_get_serial_sequence(%s, %s)", [f'public."{table}"', col]
                ).fetchone()[0]
            except Exception as exc:  # noqa: BLE001
                print(f"  {table}.{col}: ERROR {type(exc).__name__}: {exc}")
                continue
            if not seq:
                print(f"  {table}.{col}: no sequence (pk is not a serial)")
                continue
            max_pk = cur.execute(
                f'SELECT COALESCE(MAX("{col}"),0) FROM "{table}"').fetchone()[0]
            # pg_get_serial_sequence already returns a schema-qualified name,
            # so it must be used unquoted.
            r = cur.execute(
                "SELECT last_value, is_called FROM " + seq).fetchone()
            before = r[0] + 1 if r[1] else r[0]
            flag = "ok" if before > max_pk else "OUT OF SYNC"
            print(f"  {table:34} {col:12} max={max_pk:>4} next={before:>4}  {flag}")
    print(f"\n  {len(seen)} managed tables inspected")
