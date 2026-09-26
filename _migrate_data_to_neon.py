"""Migrate ALL rows from local db.sqlite3 into Neon (PostgreSQL).

Strategy
--------
* Users / Specializations / Profiles are matched to the target by natural key
  (username, then email / name / user) and UPDATED IN PLACE, so the target
  keeps its own primary keys. That sidesteps every PK collision.
* Every other row is keyed on its source primary key, so the script is
  idempotent: re-running updates instead of duplicating.
* All foreign keys are remapped through the pk maps built along the way.
* auto_now / auto_now_add values from the source are restored after insert,
  because Django overwrites them during save().

Run:  .\\.venv\\Scripts\\python.exe _migrate_data_to_neon.py [--dry-run]
"""
import os
import sys
import datetime
import sqlite3
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=RuntimeWarning, module="django.db")

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

DRY = "--dry-run" in sys.argv
SRC = sqlite3.connect(f"file:{BASE / 'db.sqlite3'}?mode=ro", uri=True)
SRC.row_factory = sqlite3.Row

USER_MODEL = apps.get_model(settings.AUTH_USER_MODEL)
UNAME = USER_MODEL.__name__

# Insert order: no-FK models first, so every remap is already available.
ORDER = [
    "Specialization",
    UNAME,
    "Profile",
    "Qualification",
    "CandidateDocument",
    "Subscription",
    "Payment",
    "RecruitmentRequest",
    "CandidateMatch",
    "Shortlist",
    "ReplacementRequest",
    "Notification",
    "AuditLog",
]

# Identity keys used to recognise a row that already exists in Neon, so
# re-running the migration updates in place instead of inserting duplicates.
# ("username","email") is an ANY-match list; a tuple of tuples is an ALL-match
# composite key, needed where a single column is not unique (e.g. a profile
# can legitimately have several documents).
NATURAL = {
    UNAME: ("username", "email"),
    "Specialization": ("name",),
    "Profile": ("user_id",),
    "CandidateDocument": (("profile_id", "file"),),
    "Notification": (("user_id", "kind", "title", "created_at"),),
    "AuditLog": (("actor_id", "action", "created_at"),),
    "RecruitmentRequest": (("employer_id", "position", "created_at"),),
    "Qualification": (("profile_id", "title"),),
}

LOG = []

# Rows created by throwaway test scripts, not real accounts. They are skipped so
# they don't pollute Neon. Pass --exclude-email to override the list.
EXCLUDE_EMAILS = set(
    (os.environ.get("MIGRATE_EXCLUDE_EMAILS")
     or "dbg@example.com,pce@example.com").split(",")
)
EXCLUDE_EMAILS = {e.strip().lower() for e in EXCLUDE_EMAILS if e.strip()}

# src pks that were deliberately skipped, so dependent rows get skipped too
SKIPPED = {name: set() for name in ORDER}


def w(s=""):
    LOG.append(str(s))
    print(s)


# model name -> {source_pk: target_pk}
PKMAP = {name: {} for name in ORDER}


def get_model(name):
    return USER_MODEL if name == UNAME else apps.get_model("website", name)


def src_rows(model):
    cols = [r[1] for r in SRC.execute(f"PRAGMA table_info({model._meta.db_table})")]
    if not cols:
        return []
    return list(SRC.execute(
        f"SELECT {','.join(cols)} FROM {model._meta.db_table} ORDER BY id"))


def find_existing(model, row):
    """Return the target pk if a row already matches this source row.

    NATURAL entries are either a flat tuple of columns (match on ANY) or a
    tuple of column-tuples (each inner tuple must match on ALL columns).
    FK values are remapped through PKMAP before querying.
    """
    spec = NATURAL.get(model.__name__, ())
    if spec and isinstance(spec[0], tuple):
        groups = spec
    else:
        groups = [(f,) for f in spec]

    for group in groups:
        kwargs = {}
        usable = True
        for field in group:
            if field not in row.keys():
                usable = False
                break
            val = row[field]
            if val is None:
                usable = False
                break
            try:
                fobj = model._meta.get_field(field)
            except Exception:
                usable = False
                break
            if fobj.many_to_one or fobj.one_to_one:
                tname = fobj.remote_field.model.__name__
                val = PKMAP.get(tname, {}).get(val, val)
            kwargs[field] = val
        if not usable:
            continue
        hit = model.objects.filter(**kwargs).first()
        if hit:
            return hit.pk
    return None


def build_kwargs(model, row):
    """Map a source sqlite row onto model fields, remapping every FK."""
    data = {}
    for f in model._meta.concrete_fields:
        col = f.column
        if f.primary_key or col not in row.keys():
            continue
        val = row[col]
        if f.many_to_one or f.one_to_one:
            if val is None:
                data[f.attname] = None
                continue
            tname = f.remote_field.model.__name__
            data[f.attname] = PKMAP.get(tname, {}).get(val, val)
        else:
            data[f.attname] = val
    return make_aware_all(data)


def make_aware_all(data):
    """SQLite stores naive datetimes; Django wants them tz-aware under USE_TZ."""
    for key, val in data.items():
        if isinstance(val, datetime.datetime) and timezone.is_naive(val):
            data[key] = timezone.make_aware(val, timezone.get_default_timezone())
    return data


def restore_timestamps(model, obj, row):
    """Django overwrites auto_now/auto_now_add on save; put source values back."""
    patch = {}
    for f in model._meta.concrete_fields:
        col = f.column
        if not (getattr(f, "auto_now", False)
                or getattr(f, "auto_now_add", False)):
            continue
        if col in row.keys():
            patch[f.attname] = row[col]
    if patch:
        patch = make_aware_all(patch)
        model.objects.filter(pk=obj.pk).update(**patch)
        for k, v in patch.items():
            setattr(obj, k, v)
    return patch


def skip_via_fk(model, row):
    """True when this row points at a user/profile that was excluded as a test row."""
    for f in model._meta.concrete_fields:
        if not (f.many_to_one or f.one_to_one):
            continue
        remote = f.remote_field.model.__name__
        if remote not in SKIPPED:
            continue
        val = row[f.column] if f.column in row.keys() else None
        if val is not None and val in SKIPPED[remote]:
            return True
    return False


def sync_m2m(model, obj, row):
    """Re-link M2M rows (e.g. profile -> specializations)."""
    if model.__name__ != "Profile":
        return 0
    spec_map = PKMAP.get("Specialization", {})
    src_ids = {r["specialization_id"] for r in SRC.execute(
        "SELECT specialization_id FROM website_profile_specializations"
        " WHERE profile_id = ?", (row["id"],))}
    if not src_ids:
        return 0
    targets = [spec_map[i] for i in src_ids if i in spec_map]
    obj.specializations.set(targets)
    return len(targets)

w("=" * 72)
if DRY:
    w("DRY RUN - nothing will be written")
    w(f"source: db.sqlite3   target host: {connection.settings_dict['HOST']}")
    w(f"excluding test accounts: {', '.join(sorted(EXCLUDE_EMAILS)) or '(none)'}")
else:
    w("LIVE RUN - writing to Neon")
    w(f"source: db.sqlite3   target host: {connection.settings_dict['HOST']}")
    w(f"excluding test accounts: {', '.join(sorted(EXCLUDE_EMAILS)) or '(none)'}")
w("=" * 72)

# Safety net: snapshot Neon before mutating it, so the run can be undone.
if not DRY:
    from django.core.management import call_command  # noqa: E402
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = BASE / f"_neon_backup_{stamp}.json"
    call_command("dumpdata", "--natural-foreign", "--natural-primary",
                 output=str(backup), verbosity=0)
    w(f"[backup] wrote {backup.name} "
      f"({backup.stat().st_size / 1024:.1f} KB) - restore with loaddata")
    w()

created_total = updated_total = 0

for name in ORDER:
    model = get_model(name)
    rows = src_rows(model)
    pkmap = PKMAP[name]
    table = model._meta.db_table

    w()
    w(f"--- {name}  ({table})  source rows: {len(rows)}")
    if not rows:
        w("    (nothing to copy)")
        continue

    for row in rows:
        src_pk = row["id"]

        # Skip test-artifact accounts, and anything hanging off them.
        if name == UNAME:
            email = (row["email"] or "").lower()
            if email in EXCLUDE_EMAILS:
                SKIPPED[name].add(src_pk)
                w(f"    SKIP (excluded test account) {row['username']} <{email}>")
                continue
        elif skip_via_fk(model, row):
            SKIPPED[name].add(src_pk)
            w(f"    SKIP (owner excluded)  src pk {src_pk}")
            continue

        kwargs = build_kwargs(model, row)
        existing_pk = find_existing(model, row)

        with transaction.atomic():
            if DRY:
                # Nothing may be written in dry-run, not even a re-save.
                pkmap[src_pk] = existing_pk if existing_pk is not None else src_pk
                w(f"    WOULD {'UPDATE' if existing_pk else 'CREATE'}"
                  f"  src pk {src_pk} -> {table} pk {pkmap[src_pk]}")
                continue
            if existing_pk is not None:
                # Natural-key match -> update the Neon row in place, keep its pk.
                obj = model.objects.filter(pk=existing_pk).first()
                for k, v in kwargs.items():
                    setattr(obj, k, v)
                obj.save()
                action = "UPDATE"
                updated_total += 1
            elif model.objects.filter(pk=src_pk).exists():
                obj = model.objects.create(**kwargs)
                action = "CREATE(new pk)"
                created_total += 1
            else:
                obj = model.objects.create(pk=src_pk, **kwargs)
                action = "CREATE"
                created_total += 1

            restore_timestamps(model, obj, row)
            n_links = sync_m2m(model, obj, row)
            pkmap[src_pk] = obj.pk

        extra = f"  (+{n_links} specialization link)" if n_links else ""
        w(f"    {action}  src pk {src_pk} -> {table} pk {obj.pk}{extra}")

w()
w("=" * 72)
w(f"done: {created_total} created, {updated_total} updated")

w()
w("FINAL ROW COUNTS (sqlite -> neon)")
for name in ORDER:
    model = get_model(name)
    t = model._meta.db_table
    s = len(src_rows(model)) - len(SKIPPED.get(name, ()))
    n = model.objects.count()
    flag = "" if n >= s else "   <-- LOWER THAN SOURCE"
    w(f"  {t:36s} {s:>5d} -> {n:<5d}{flag}")

(BASE / "_migrate_neon_log.txt").write_text("\n".join(LOG), encoding="utf-8")
print("\nwrote _migrate_neon_log.txt")

