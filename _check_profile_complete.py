"""End-to-end check of the employer profile-completion modal + auto-redirect.

Run:  python _check_profile_complete.py
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
from website.models import Profile  # noqa: E402

U = get_user_model()
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   [{extra}]" if extra else ""))


# -- clean slate ------------------------------------------------
# NB: EmployerProfileForm.save() renames username -> email, so accounts created by
# this script can end up with a non-"qatest_" username. Sweep both.
U.objects.filter(username__startswith="qatest_").delete()
U.objects.filter(email__in=["pce@example.com", "pce2@example.com",
                             "pce3@example.com", "pccc@example.com"]).delete()

emp_u = U.objects.create_user(username="qatest_pc_emp", password="x", email="pce@example.com")
emp = Profile.objects.create(user=emp_u, role="employer")

FULL = {
    "company_name": "Zenith Test Ltd",
    "industry_sector": "Technology",
    "hr_contact_name": "Ada Recruiter",
    "office_address": "5 Test Close, Lagos",
    "email": "pce@example.com",
    "phone": "08033334444",
}
PROFILE_URL = "/dashboard/employer/profile/"
REQUESTS_URL = "/dashboard/employer/requests/"

c = Client(SERVER_NAME="localhost")
c.force_login(emp_u)

print("\n-- completeness rule " + "-" * 45)

emp.refresh_from_db()
check("1. a fresh employer profile is incomplete", emp.employer_profile_complete is False)

cand_u = U.objects.create_user(username="qatest_pc_cand", password="x", email="pccc@example.com")
cand = Profile.objects.create(
    user=cand_u, role="candidate", legal_name="X", phone="080", address="a",
    primary_degree="d", certifications="c", software_competencies="s",
    professional_pitch="p", expected_salary=1, availability="immediate",
    verification_status=Profile.VerificationStatus.VERIFIED,
)
check("2. a fully-filled CANDIDATE is not employer-complete",
      cand.employer_profile_complete is False)

print("\n-- partial save " + "-" * 51)

r = c.get(PROFILE_URL)
check("3. profile page renders", r.status_code == 200, r.status_code)
check("3b. no modal on a plain GET", 'id="profileCompleteModal"' not in r.content.decode())

r = c.post(PROFILE_URL, {"company_name": "Zenith Test Ltd", "industry_sector": "Technology"})
emp.refresh_from_db()
check("4. partial save is not treated as complete", emp.employer_profile_complete is False)
check("4b. partial save redirects without ?completed", "completed" not in r.get("Location", ""),
      r.get("Location"))

print("\n-- completing the profile " + "-" * 40)

r = c.post(PROFILE_URL, FULL)
check("5. completing POST redirects (PRG)", r.status_code == 302, r.status_code)
check("5b. redirect carries ?completed=1", "completed=1" in r.get("Location", ""), r.get("Location"))

emp.refresh_from_db()
check("6. profile is now complete", emp.employer_profile_complete is True)
check("6b. details persisted",
      emp.company_name == "Zenith Test Ltd" and emp.industry_sector == "Technology"
      and emp.hr_contact_name == "Ada Recruiter" and emp.phone == "08033334444")

r = c.get(r.get("Location"))
check("7. completed page renders", r.status_code == 200, r.status_code)
html = r.content.decode()
check("7b. completion modal is present", 'id="profileCompleteModal"' in html)
check("7c. modal summarises the company", "Zenith Test Ltd" in html and "Ada Recruiter" in html)
check("7d. modal links to the request page", "profileCompleteModal" in html
      and f'href="{REQUESTS_URL}"' in html)
check("7e. modal auto-forwards via JS", "profileCompleteModal" in html
      and "location.href" in html and "data-countdown" in html)
check("7f. modal offers a stay option", "data-profile-stay" in html)
check("7g. dialog semantics present", 'role="dialog"' in html and 'aria-modal="true"' in html)
check("7h. request page itself is reachable", c.get(REQUESTS_URL).status_code == 200)
print("\n-- idempotency " + "-" * 52)

# Editing an already-complete profile must NOT hijack the page again.
r = c.post(PROFILE_URL, dict(FULL, industry_sector="Technology (updated)"))
check("8. editing a complete profile does not re-trigger", "completed" not in r.get("Location", ""),
      r.get("Location"))
emp.refresh_from_db()
check("8b. edit still saved", emp.industry_sector == "Technology (updated)", emp.industry_sector)

# A hand-crafted URL must not show the modal for an incomplete profile.
u2 = U.objects.create_user(username="qatest_pc_emp2", password="x", email="pce2@example.com")
emp2 = Profile.objects.create(user=u2, role="employer", company_name="Partial Co")
c2 = Client(SERVER_NAME="localhost")
c2.force_login(u2)
html = c2.get(PROFILE_URL + "?completed=1").content.decode()
check("9. ?completed=1 alone does not open the modal for an incomplete profile",
      'id="profileCompleteModal"' not in html)
check("9b. incomplete employer still false", emp2.employer_profile_complete is False)

# Missing contact details keep it incomplete.
u3 = U.objects.create_user(username="qatest_pc_emp3", password="x", email="pce3@example.com")
emp3 = Profile.objects.create(
    user=u3, role="employer", company_name="No Phone Co", industry_sector="Retail",
    hr_contact_name="Sam", office_address="1 Road",
)
check("10. missing phone keeps the profile incomplete", emp3.employer_profile_complete is False)
emp3.phone = "08099998888"
emp3.save()
check("10b. adding the last field completes it", emp3.employer_profile_complete is True)

# -- cleanup ----------------------------------------------------
Profile.objects.filter(user__username__startswith="qatest_").delete()
U.objects.filter(username__startswith="qatest_").delete()
# Also catch accounts renamed to their email by the form's save().
U.objects.filter(email__in=["pce@example.com", "pce2@example.com",
                             "pce3@example.com", "pccc@example.com"]).delete()

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