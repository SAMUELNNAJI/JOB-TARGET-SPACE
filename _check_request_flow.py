"""End-to-end check of the employer recruitment-request flow.

Covers the free-text "Other" profession option and the submit confirmation modal.

Run:  python _check_request_flow.py
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
from website.forms import RecruitmentRequestForm  # noqa: E402
from website.models import Profile, RecruitmentRequest  # noqa: E402

U = get_user_model()
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   [{extra}]" if extra else ""))


# ── clean slate ──────────────────────────────────────────────
U.objects.filter(username__startswith="qatest_").delete()

emp = U.objects.create_user(username="qatest_emp2", password="x", email="qaemp2@example.com")
other_emp = U.objects.create_user(username="qatest_emp3", password="x", email="qaemp3@example.com")
ep = Profile.objects.create(user=emp, role="employer", company_name="QA Employer")
oep = Profile.objects.create(user=other_emp, role="employer", company_name="QA Other Employer")

c = Client(SERVER_NAME="localhost")
c.force_login(emp)
URL = "/dashboard/employer/requests/"

BASE = {
    "professionals_required": 2,
    "minimum_qualification": "BSc",
    "certifications": "None",
    "years_experience": 3,
    "required_skills": "Excel, reporting",
    "salary_min": 100000,
    "salary_max": 200000,
    "salary_period": "monthly",
}

print("\n-- form-level behaviour " + "-" * 46)

# 1. dropdown choice
f = RecruitmentRequestForm(data=dict(BASE, position="Accountant"))
check("1. dropdown choice validates", f.is_valid(), f.errors.as_json() if not f.is_valid() else "")
check("1b. dropdown value stored", f.cleaned_data.get("position") == "Accountant",
      f.cleaned_data.get("position"))

# 2. "Other" + typed profession not on the list
CUSTOM = "Quantity Surveyor"
f = RecruitmentRequestForm(data=dict(BASE, position=RecruitmentRequestForm.OTHER, custom_position=CUSTOM))
check("2. 'Other' + typed profession validates", f.is_valid(), f.errors.as_json() if not f.is_valid() else "")
check("2b. typed profession stored", f.cleaned_data.get("position") == CUSTOM,
      f.cleaned_data.get("position"))

# 3. "Other" selected but left blank
f = RecruitmentRequestForm(data=dict(BASE, position=RecruitmentRequestForm.OTHER, custom_position="   "))
check("3. 'Other' with blank text is rejected", not f.is_valid())
check("3b. error points at custom_position", "custom_position" in f.errors, list(f.errors))

# 4. nothing selected at all
f = RecruitmentRequestForm(data=dict(BASE, position="", custom_position=""))
check("4. nothing selected is rejected", not f.is_valid())
check("4b. error points at position", "position" in f.errors, list(f.errors))

# 5. whitespace-only custom text is ignored when a real choice is picked
f = RecruitmentRequestForm(data=dict(BASE, position="Doctor", custom_position="   "))
check("5. whitespace custom text ignored when a real choice is picked", f.is_valid()
      and f.cleaned_data.get("position") == "Doctor", f.cleaned_data.get("position"))

# 6. model field no longer restricts to the suggestion list
check("6. model accepts a free-text position",
      "Quantity Surveyor" not in {c for c, _ in RecruitmentRequest.POSITION_CHOICES})

print("\n-- view / template behaviour " + "-" * 41)

# 7. page loads
r = c.get(URL)
check("7. requests page renders", r.status_code == 200, r.status_code)
html = r.content.decode()
check("7b. page has the position select", 'name="position"' in html)
check("7c. page has the custom position input", 'name="custom_position"' in html)
check("7d. page has the 'Other' option", "Other" in html)
check("7e. no modal when nothing was submitted", 'id="requestSuccessModal"' not in html)

# 8. submit with a custom profession
before = RecruitmentRequest.objects.filter(employer=ep).count()
r = c.post(URL, dict(BASE, position=RecruitmentRequestForm.OTHER, custom_position=CUSTOM))
check("8. POST with custom profession redirects", r.status_code == 302, r.status_code)
check("8b. redirect carries ?submitted=", "?submitted=" in r.get("Location", ""), r.get("Location"))

created = RecruitmentRequest.objects.filter(employer=ep).order_by("-id").first()
check("8c. one request created", RecruitmentRequest.objects.filter(employer=ep).count() == before + 1)
check("8d. saved position is the custom one", created is not None and created.position == CUSTOM,
      created.position if created else "")
check("8e. employer linked correctly", created is not None and created.employer_id == ep.pk)

# 9. follow the redirect -> modal must render
loc = r.get("Location")
r = c.get(loc)
check("9. redirect target renders", r.status_code == 200, r.status_code)
html = r.content.decode()
check("9b. success modal is present", 'id="requestSuccessModal"' in html)
check("9c. modal names the custom position", CUSTOM in html)
check("9d. modal has a close control", "data-emp-modal-close" in html)
check("9e. modal has dialog semantics", 'role="dialog"' in html and 'aria-modal="true"' in html)
check("9f. page still lists the new request", CUSTOM in html)

# 10. modal must not leak another employer's request
foreign = RecruitmentRequest.objects.create(
    employer=oep, position="Secret Position XYZ",
    minimum_qualification="BSc", required_skills="x", salary_min=1, salary_max=2,
)
for label, q in (("foreign id", foreign.pk), ("unknown id", 999999999), ("non-numeric", "abc")):
    rr = c.get(f"{URL}?submitted={q}")
    check(f"10. {label} does not render a modal",
          rr.status_code == 200 and 'id="requestSuccessModal"' not in rr.content.decode(), rr.status_code)

# 11. invalid POST re-renders the form with errors, no modal
r = c.post(URL, dict(BASE, position=RecruitmentRequestForm.OTHER, custom_position=""))
check("11. invalid POST re-renders (200, not a redirect)", r.status_code == 200, r.status_code)
html = r.content.decode()
check("11b. no modal on a failed submit", 'id="requestSuccessModal"' not in html)
check("11c. error surfaced in the page", "Enter the position you need." in html)

# 12. salary guard still works
r = c.post(URL, dict(BASE, position="Accountant", salary_min=300000, salary_max=100000))
check("12. salary min>max still blocked", r.status_code == 200
      and "Maximum salary must be greater than minimum salary." in r.content.decode(), r.status_code)

# -- cleanup ----------------------------------------------------
RecruitmentRequest.objects.filter(employer__in=[ep, oep]).delete()
U.objects.filter(username__startswith="qatest_").delete()

failed = [n for n, ok, _ in results if not ok]
print("\n" + "=" * 66)
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED:")
    for n in failed:
        print("  - " + n)
else:
    print("ALL CHECKS PASSED")
print("=" * 66)
