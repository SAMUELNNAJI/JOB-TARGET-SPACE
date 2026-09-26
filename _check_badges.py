import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from website.context_processors import dashboard_badges
from website.models import Profile

PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL:", label)


class FakeReq:
    def __init__(self, path, user):
        self.path = path
        self.user = user


class FakeUser:
    is_authenticated = True
    is_staff = False
    is_superuser = False

    def __init__(self, profile=None):
        self.profile = profile


class FakeProfile:
    def __init__(self, role):
        self.role = role
        self.notifications = self
        self.matches = self
        self.candidate_matches = self
        self.shortlists = self
        self.recruitment_requests = self

    def filter(self, **kw):
        return self

    def count(self):
        return 7


admin = FakeUser()
admin.is_staff = True

pages = {
    "/dashboard/admin/candidates/": "admin_candidates",
    "/dashboard/admin/requests/": "admin_requests",
    "/dashboard/admin/talent-pool/": "admin_talent_pool",
    "/dashboard/admin/matching/": "admin_matching",
    "/dashboard/admin/replacements/": "admin_replacements",
    "/dashboard/admin/payments/": "admin_payments",
    "/dashboard/admin/notifications/": "admin_notifications",
}
for path, key in pages.items():
    b = dashboard_badges(FakeReq(path, admin))["sidebar_badges"]
    check(f"{key} == 0 on {path}", b.get(key) == 0)

b = dashboard_badges(FakeReq("/dashboard/admin/candidates/", admin))["sidebar_badges"]
check("admin_requests untouched on candidates page", b["admin_requests"] != 0)
neutral = dashboard_badges(FakeReq("/dashboard/admin/", admin))["sidebar_badges"]
real_pending = Profile.objects.filter(
    role=Profile.Role.CANDIDATE,
    verification_status__in=[Profile.VerificationStatus.PENDING, Profile.VerificationStatus.VERIFYING],
).count()
check("admin_candidates equals real count on neutral page", neutral["admin_candidates"] == real_pending)
check("unread_count 0 on notifications page",
      dashboard_badges(FakeReq("/dashboard/admin/notifications/", admin))["unread_count"] == 0)
check("header_unread mirrors unread_count",
      dashboard_badges(FakeReq("/dashboard/admin/notifications/", admin))["header_unread"] == 0)

cand = FakeProfile("candidate")
b = dashboard_badges(FakeReq("/dashboard/candidate/matches/", FakeUser(cand)))["sidebar_badges"]
check("candidate_matches == 0 on matches page", b["candidate_matches"] == 0)
check("candidate_notifications kept on matches page", b["candidate_notifications"] == 7)

b = dashboard_badges(FakeReq("/dashboard/candidate/notifications/", FakeUser(cand)))["sidebar_badges"]
check("candidate_notifications == 0 on notifications page", b["candidate_notifications"] == 0)
check("candidate_matches kept on notifications page", b["candidate_matches"] == 7)

emp = FakeProfile("employer")
b = dashboard_badges(FakeReq("/dashboard/employer/candidates/", FakeUser(emp)))["sidebar_badges"]
check("employer_candidates == 0 on candidates page", b["employer_candidates"] == 0)
check("employer_shortlist kept there", b["employer_shortlist"] == 7)
check("employer_shortlist == 0 on shortlist page",
      dashboard_badges(FakeReq("/dashboard/employer/shortlist/", FakeUser(emp)))["sidebar_badges"]["employer_shortlist"] == 0)
check("employer_requests == 0 on requests page",
      dashboard_badges(FakeReq("/dashboard/employer/requests/", FakeUser(emp)))["sidebar_badges"]["employer_requests"] == 0)
check("employer_notifications == 0 on notifications page",
      dashboard_badges(FakeReq("/dashboard/employer/notifications/", FakeUser(emp)))["sidebar_badges"]["employer_notifications"] == 0)

anon = FakeUser()
anon.is_authenticated = False
check("anonymous gets empty badges", dashboard_badges(FakeReq("/x", anon))["sidebar_badges"] == {})

print(f"RESULT: {PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
