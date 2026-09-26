"""End-to-end check of the redesigned admin matching workspace.

Run:  python _check_matching_flow.py
Cleans up every record it creates.
"""
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402
from django.urls import reverse  # noqa: E402

setup_test_environment()

from django.contrib.auth import get_user_model  # noqa: E402
from website.models import CandidateMatch, Profile, RecruitmentRequest, Specialization  # noqa: E402

U = get_user_model()
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   [{extra}]" if extra else ""))


# -- clean slate ------------------------------------------------
U.objects.filter(username__startswith="qatest_").delete()

admin = U.objects.create_user(username="qatest_madmin", password="x", is_staff=True)
emp_u = U.objects.create_user(username="qatest_memp", password="x", email="memp@example.com")
emp = Profile.objects.create(
    user=emp_u, role="employer", company_name="Acme Test Co",
    industry_sector="Construction", hr_contact_name="Jane Recruiter",
    office_address="12 Test Street, Lagos", phone="08011112222",
)
good_u = U.objects.create_user(username="qatest_mgood", password="x", email="mgood@example.com")
good = Profile.objects.create(
    user=good_u, role="candidate", legal_name="Good Candidate",
    primary_degree="BSc Civil Engineering", software_competencies="AutoCAD site analysis",
    availability="immediate", expected_salary=120000,
    verification_status=Profile.VerificationStatus.VERIFIED,
)
bad_u = U.objects.create_user(username="qatest_mbad", password="x", email="mbad@example.com")
bad = Profile.objects.create(
    user=bad_u, role="candidate", legal_name="Unverified Candidate",
    verification_status=Profile.VerificationStatus.PENDING,
)
spec, _ = Specialization.objects.get_or_create(
    slug="civil-engineering", defaults={"name": "Civil Engineering"}
)
good.specializations.add(spec)

req = RecruitmentRequest.objects.create(
    employer=emp, position="Civil Engineer", professionals_required=2,
    minimum_qualification="BSc", required_skills="AutoCAD site analysis",
    salary_min=100000, salary_max=200000,
)

c = Client(SERVER_NAME="localhost")
c.force_login(admin)
MATCHING = "/dashboard/admin/matching/"

print("\n-- page & ranking " + "-" * 48)

r = c.get(MATCHING)
check("1. matching page renders", r.status_code == 200, r.status_code)
html = r.content.decode()
check("1b. employer modal present", 'id="employerDetailModal"' in html)
check("1c. employer buttons carry a data id", "data-employer-detail" in html)
check("1d. placeholder shown when no request selected", "mt-placeholder" in html)
check("1e. unverified candidate is NOT offered", "Unverified Candidate" not in html)
check("1f. request appears with open slots", "Civil Engineer" in html and "2 slots open" in html)

r = c.get(MATCHING + f"?request={req.pk}")
check("2. focused request renders", r.status_code == 200, r.status_code)
html = r.content.decode()
check("2b. verified candidate is offered", "Good Candidate" in html)
check("2c. score chip present", "mt-score" in html)
check("2d. match reasons explained", "mt-reasons" in html)
check("2e. match form posts candidate+request", 'name="candidate"' in html and 'name="request"' in html)
print("\n-- matching " + "-" * 56)

r = c.post(reverse("website:create_match"), {"request": req.pk, "candidate": good.pk})
check("3. create_match redirects", r.status_code == 302, r.status_code)
check("3b. redirect keeps focus on the request", f"request={req.pk}" in r.get("Location", ""),
      r.get("Location"))

m = CandidateMatch.objects.filter(request=req, profile=good, employer=emp).first()
check("3c. match row created and linked to the request", m is not None and m.request_id == req.pk)
req.refresh_from_db()
check("3d. status advanced to matching", req.status == RecruitmentRequest.Status.MATCHING, req.status)
check("3e. matched_count is 1", req.matched_count == 1, req.matched_count)
check("3f. remaining_slots is 1", req.remaining_slots == 1, req.remaining_slots)
check("3g. employer notified", emp.notifications.filter(kind="match").exists())
check("3h. candidate notified", good.notifications.filter(kind="match").exists())

r = c.post(reverse("website:create_match"), {"request": req.pk, "candidate": good.pk})
check("4. duplicate match is rejected", CandidateMatch.objects.filter(
    request=req, profile=good, is_active=True).count() == 1, r.status_code)

r = c.post(reverse("website:create_match"), {"request": req.pk, "candidate": bad.pk})
check("5. unverified candidate cannot be matched",
      not CandidateMatch.objects.filter(request=req, profile=bad).exists(), r.status_code)

print("\n-- slot limits " + "-" * 53)

cand2_u = U.objects.create_user(username="qatest_mc2", password="x", email="mc2@example.com")
cand2 = Profile.objects.create(
    user=cand2_u, role="candidate", legal_name="Second Candidate",
    verification_status=Profile.VerificationStatus.VERIFIED,
)
c.post(reverse("website:create_match"), {"request": req.pk, "candidate": cand2.pk})
req.refresh_from_db()
check("6. second match fills the request", req.matched_count == 2, req.matched_count)
check("6b. status becomes available", req.status == RecruitmentRequest.Status.AVAILABLE, req.status)
check("6c. is_fully_matched true", req.is_fully_matched is True)
check("6d. remaining_slots is 0", req.remaining_slots == 0, req.remaining_slots)

cand3_u = U.objects.create_user(username="qatest_mc3", password="x", email="mc3@example.com")
cand3 = Profile.objects.create(
    user=cand3_u, role="candidate", legal_name="Third Candidate",
    verification_status=Profile.VerificationStatus.VERIFIED,
)
r = c.post(reverse("website:create_match"), {"request": req.pk, "candidate": cand3.pk})
check("7. cannot exceed professionals_required", not CandidateMatch.objects.filter(
    request=req, profile=cand3).exists(), r.status_code)
print("\n-- withdrawal " + "-" * 55)

r = c.post(reverse("website:remove_match", args=[m.pk]))
check("8. remove_match redirects", r.status_code == 302, r.status_code)
m.refresh_from_db()
req.refresh_from_db()
check("8b. match deactivated (not deleted)", m.is_active is False)
check("8c. matched_count drops to 1", req.matched_count == 1, req.matched_count)
check("8d. status rolls back to matching", req.status == RecruitmentRequest.Status.MATCHING, req.status)

r = c.post(reverse("website:remove_match", args=[m.pk]))
check("9. withdrawing an inactive match 404s", r.status_code == 404, r.status_code)
r = c.get(reverse("website:remove_match", args=[m.pk]))
check("9b. GET on remove does not act", m.is_active is False and r.status_code in (302, 405), r.status_code)

print("\n-- employer detail endpoint " + "-" * 36)

r = c.get(reverse("website:admin_employer_detail", args=[emp.pk]))
check("10. employer detail returns JSON", r.status_code == 200, r.status_code)
data = r.json()
for key in ("name", "legal_name", "user_name", "email", "phone", "whatsapp", "industry",
            "hr_contact", "address", "joined", "last_login", "status", "plan", "plan_expires",
            "requests_total", "matches_total", "shortlists", "payments"):
    check(f"10. detail exposes '{key}'", key in data, data.get(key))
check("10z. detail shows the company", data.get("name") == "Acme Test Co", data.get("name"))
check("10y. detail shows the HR contact", data.get("hr_contact") == "Jane Recruiter",
      data.get("hr_contact"))

r = c.get(reverse("website:admin_employer_detail", args=[good.pk]))
check("11. employer detail 404s for a candidate id", r.status_code == 404, r.status_code)

print("\n-- permissions " + "-" * 51)

c2 = Client(SERVER_NAME="localhost")
c2.force_login(emp_u)
r2 = c2.get(MATCHING)
check("12. non-staff is refused", r2.status_code in (302, 403), r2.status_code)
anon = Client(SERVER_NAME="localhost")
ra = anon.get(MATCHING)
check("12b. anonymous is redirected to login", ra.status_code == 302, ra.status_code)
check("12c. anonymous cannot create matches", anon.post(
    reverse("website:create_match"), {"request": req.pk, "candidate": good.pk}).status_code == 302)

# -- cleanup ----------------------------------------------------
CandidateMatch.objects.filter(employer=emp).delete()
RecruitmentRequest.objects.filter(employer=emp).delete()
Specialization.objects.filter(slug="civil-engineering").delete()
U.objects.filter(username__startswith="qatest_").delete()

failed = [n for n, ok, _ in results if not ok]
print("\n" + "=" * 68)
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED:")
    for n in failed:
        print("  - " + n)
else:
    print("ALL CHECKS PASSED")
print("=" * 68)