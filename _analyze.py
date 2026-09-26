import os, django, json, sqlite3

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.contrib.auth.models import User
from website.models import (Profile, Specialization, CandidateDocument,
                            Notification, AuditLog, RecruitmentRequest)

TABLES = ["auth_user", "website_profile", "website_specialization",
          "website_candidatedocument", "website_notification",
          "website_auditlog", "website_recruitmentrequest"]

sc = sqlite3.connect("db.sqlite3")
sc.row_factory = sqlite3.Row

print("=== SQLITE FULL ROWS ===")
for t in TABLES:
    rows = [dict(r) for r in sc.execute("SELECT * FROM %s" % t)]
    print("\n-- %s (%d) --" % (t, len(rows)))
    for r in rows:
        clean = {k: v for k, v in r.items() if v is not None}
        print(json.dumps(clean, default=str))

print("\n=== NEON FULL ROWS ===")
for m in [User, Profile, Specialization, CandidateDocument, Notification,
          AuditLog, RecruitmentRequest]:
    for o in m.objects.all().order_by("pk"):
        d = {f.attname: getattr(o, f.attname) for f in m._meta.concrete_fields}
        d["_m2m"] = {f.name: list(getattr(o, f.name).values_list("pk", flat=True))
                     for f in m._meta.many_to_many}
        print(m.__name__, json.dumps(d, default=str))
