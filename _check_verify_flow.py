"""Ad-hoc end-to-end check of admin candidate verify / reject / revoke flows.

Run:  python _check_verify_flow.py
Cleans up every record it creates.
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402

setup_test_environment()

from django.contrib.auth import get_user_model  # noqa: E402
from website.models import AuditLog, CandidateMatch, Profile  # noqa: E402

U = get_user_model()

# ── clean slate ──────────────────────────────────────────────
U.objects.filter(username__startswith="qatest_").delete()

admin = U.objects.create_user(username="qatest_admin", password="x", is_staff=True)
cand = U.objects.create_user(username="qatest_cand", password="x", email="qacand@example.com")
emp = U.objects.create_user(username="qatest_emp", password="x", email="qaemp@example.com")

cp = Profile.objects.create(
    user=cand, role="candidate", legal_name="QA Test Candidate",
    phone="0801234567", address="Lagos, Nigeria", primary_degree="BSc Testing",
    professional_pitch="I test things thoroughly.",
)
ep = Profile.objects.create(user=emp, role="employer", company_name="QA Employer")
CandidateMatch.objects.create(profile=cp, employer=ep)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name, ("| " + str(extra) if extra else ""))


admin_c = Client(SERVER_NAME="localhost")
admin_c.force_login(admin)

# ── 1. admin candidates page renders actions + modals + profile modal ──
r = admin_c.get("/dashboard/admin/candidates/")
html = r.content.decode()
check("admin candidates page renders", r.status_code == 200, r.status_code)
for needle in ["data-reject-url", "data-revoke-url", "rejectModal", "revokeModal",
               "candProfileModal", "candProfileBody", "cand-profile-source",
               "class=\"cand-row\"", "aria-haspopup=\"dialog\"", "adm-act--verify",
               "rejectReason", "revokeReason", "/verify/", "Rejected"]:
    check(f"page contains '{needle}'", needle in html)

# hover preview must be gone -- the modal is click/Enter triggered only
for gone in ["candHoverCard", "cand-hover-source", "mouseenter"]:
    check(f"page no longer contains '{gone}'", gone not in html)

# ── 2. verify ────────────────────────────────────────────────
admin_c.post(f"/dashboard/admin/candidates/{cp.pk}/verify/")
cp.refresh_from_db()
check("verify sets status=verified", cp.verification_status == "verified", cp.verification_status)
check("verify sets verified_at", cp.verified_at is not None)
check("candidate notified on verify", cp.notifications.filter(title="Profile verified").exists())

html = admin_c.get("/dashboard/admin/candidates/").content.decode()
check("Revoke button shown once verified", "adm-act--revoke" in html and "data-revoke-url" in html)

# ── 3. action endpoints are POST-only ────────────────────────
r = admin_c.get(f"/dashboard/admin/candidates/{cp.pk}/revoke/")
cp.refresh_from_db()
check("GET revoke redirects & changes nothing", r.status_code == 302 and cp.verification_status == "verified")

# ── 4. revoke requires a reason ──────────────────────────────
admin_c.post(f"/dashboard/admin/candidates/{cp.pk}/revoke/", {"reason": "   "})
cp.refresh_from_db()
check("revoke without reason is blocked", cp.verification_status == "verified", cp.verification_status)

# ── 5. revoke with reason ────────────────────────────────────
admin_c.post(f"/dashboard/admin/candidates/{cp.pk}/revoke/",
             {"reason": "Reference could not be confirmed"})
cp.refresh_from_db()
check("revoke sets status=changes", cp.verification_status == "changes", cp.verification_status)
check("revoke stores reason", "Reference could not be confirmed" in cp.verification_notes,
      cp.verification_notes)
check("revoke clears verified_at", cp.verified_at is None)
check("candidate notified on revoke", cp.notifications.filter(title="Verification revoked").exists())

html = admin_c.get("/dashboard/admin/candidates/").content.decode()
check("Verify button back after revoke",
      f"/dashboard/admin/candidates/{cp.pk}/verify/" in html
      and f"/dashboard/admin/candidates/{cp.pk}/revoke/" not in html)

# ── 6. reject requires a reason ──────────────────────────────
admin_c.post(f"/dashboard/admin/candidates/{cp.pk}/reject/", {"reason": "   "})
cp.refresh_from_db()
check("reject without reason is blocked", cp.verification_status == "changes", cp.verification_status)

# ── 7. reject with reason ────────────────────────────────────
admin_c.post(f"/dashboard/admin/candidates/{cp.pk}/verify/")
admin_c.post(f"/dashboard/admin/candidates/{cp.pk}/reject/",
             {"reason": "Certificate is unreadable"})
cp.refresh_from_db()
check("reject sets status=rejected", cp.verification_status == "rejected", cp.verification_status)
check("reject stores reason", cp.verification_notes == "Certificate is unreadable",
      cp.verification_notes)
check("candidate notified on reject", cp.notifications.filter(title="Profile rejected").exists())
check("employer notified on reject", ep.notifications.filter(title__contains="rejected").exists())
check("audit log written",
      AuditLog.objects.filter(action="Candidate rejected",
                               subject__contains="Certificate is unreadable").exists())

# ── 8. employer dashboard shows the reason ───────────────────
emp_c = Client(SERVER_NAME="localhost")
emp_c.force_login(emp)
r = emp_c.get("/dashboard/employer/candidates/")
html = r.content.decode()
check("employer candidates page renders", r.status_code == 200, r.status_code)
check("employer sees rejection reason",
      "Certificate is unreadable" in html and "emp-reject-note" in html)
check("employer sees Rejected badge", "emp-reject-badge" in html)

# ── 9. candidate verification page shows the reason ──────────
cand_c = Client(SERVER_NAME="localhost")
cand_c.force_login(cand)
r = cand_c.get("/dashboard/candidate/verification/")
html = r.content.decode()
check("candidate verification page renders", r.status_code == 200, r.status_code)
check("candidate sees rejection reason", "Certificate is unreadable" in html)
check("candidate sees fix/resubmit actions",
      "Fix my profile" in html and "Resubmit for review" in html)

# ── 10. resubmit resets status and clears the reason ─────────
cand_c.get("/dashboard/candidate/submit/")
cp.refresh_from_db()
check("resubmit -> pending + notes cleared",
      cp.verification_status == "pending" and cp.verification_notes == "",
      f"{cp.verification_status} / {cp.verification_notes!r}")

# ── cleanup ──────────────────────────────────────────────────
U.objects.filter(username__startswith="qatest_").delete()
AuditLog.objects.filter(subject__contains="QA Test Candidate").delete()

failed = [n for n, ok in results if not ok]
print("-" * 60)
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    raise SystemExit("FAILED: " + "; ".join(failed))
print("ALL CHECKS PASSED")
