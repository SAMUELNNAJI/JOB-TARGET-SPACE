"""Compare the local SQLite database against Neon so the migration can be planned."""
import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.conf import settings  # noqa: E402
from django.apps import apps  # noqa: E402
from django.db import connections  # noqa: E402
from django.contrib.auth.models import User, Group, Permission  # noqa: E402
from django.contrib.contenttypes.models import ContentType  # noqa: E402
from website import models as M  # noqa: E402

settings.DATABASES["legacy"] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": str(Path(settings.BASE_DIR) / "db.sqlite3"),
    "ATOMIC_REQUESTS": False,
    "AUTOCOMMIT": True,
    "CONN_MAX_AGE": 0,
    "CONN_HEALTH_CHECKS": False,
    "OPTIONS": {},
    "TIME_ZONE": None,
    "TEST": {},
    "USER": "",
    "PASSWORD": "",
    "HOST": "",
    "PORT": "",
}

print("legacy backend:", connections["legacy"].vendor)
print("default backend:", connections["default"].vendor)
print()

print("--- row counts ---")
for model in [Permission, ContentType, Group, User] + list(
    apps.get_app_config("website").get_models()
):
    tbl = model._meta.db_table
    a = model.objects.using("legacy").count()
    b = model.objects.using("default").count()
    print(f"{tbl:42s} sqlite={a:<6} neon={b}")

print()
print("--- specializations: sqlite ---")
for s in M.Specialization.objects.using("legacy").all().order_by("pk"):
    print(f"  pk={s.pk:<4} name={s.name!r} slug={s.slug!r}")
print("--- specializations: neon ---")
for s in M.Specialization.objects.using("default").all().order_by("pk"):
    print(f"  pk={s.pk:<4} name={s.name!r} slug={s.slug!r}")

print()
print("--- users: sqlite ---")
for u in User.objects.using("legacy").all().order_by("pk"):
    print(f"  pk={u.pk:<4} {u.username!r} su={u.is_superuser} staff={u.is_staff}")
print("--- users: neon ---")
for u in User.objects.using("default").all().order_by("pk"):
    print(f"  pk={u.pk:<4} {u.username!r} su={u.is_superuser} staff={u.is_staff}")

print()
print("--- profiles: sqlite ---")
for p in M.Profile.objects.using("legacy").all().order_by("pk"):
    spec = [s.name for s in p.specializations.all()]
    print(f"  pk={p.pk:<4} user={p.user_id} role={p.role} legal={p.legal_name!r} "
          f"comp={p.company_name!r} status={p.verification_status} spec={spec}")

print()
print("--- candidate documents: sqlite ---")
for d in M.CandidateDocument.objects.using("legacy").all():
    on_disk = (Path(settings.MEDIA_ROOT) / d.file.name).exists()
    print(f"  pk={d.pk} profile={d.profile_id} file={d.file.name!r} on_disk={on_disk}")

print()
print("--- notifications: sqlite ---")
for n in M.Notification.objects.using("legacy").all().order_by("pk"):
    print(f"  pk={n.pk:<4} profile={n.profile_id} kind={n.kind} read={n.is_read} {n.title!r}")

print()
print("--- audit logs: sqlite ---")
for a in M.AuditLog.objects.using("legacy").all().order_by("pk"):
    print(f"  pk={a.pk:<4} actor={a.actor_id} {a.action!r} {a.subject!r} {a.result!r}")

print()
print("--- recruitment requests: sqlite ---")
for r in M.RecruitmentRequest.objects.using("legacy").all().order_by("pk"):
    print(f"  pk={r.pk:<4} employer={r.employer_id} pos={r.position!r} status={r.status}")

print()
print("--- other website tables: sqlite ---")
for model in (M.Qualification, M.CandidateMatch, M.Subscription, M.Payment,
              M.Shortlist, M.ReplacementRequest):
    rows = list(model.objects.using("legacy").all().order_by("pk"))
    print(f"  {model._meta.db_table}: {len(rows)} rows")
    for r in rows:
        print("   ", r)
