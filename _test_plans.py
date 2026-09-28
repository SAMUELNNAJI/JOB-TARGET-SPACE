"""End-to-end tests for subscription plans, expiry and the Basic match cap."""
import os

# The project's DATABASE_URL points at a remote Postgres, which would make
# the test runner prompt for credentials and hang. Force a local scratch DB.
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_scratch_plans.sqlite3"
)

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.test.utils import setup_test_environment, teardown_test_environment
from django.test.runner import DiscoverRunner

setup_test_environment()
runner = DiscoverRunner(verbosity=0, interactive=False)
old_config = runner.setup_databases()

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from website.models import CandidateMatch, Profile, RecruitmentRequest, Subscription

User = get_user_model()
ok = True


def check(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {label}{(' -> ' + str(extra)) if extra else ''}")


def no_5xx(label, resp):
    codes = [c for _, c in getattr(resp, "redirect_chain", [])]
    bad = resp.status_code >= 500 or any(c >= 500 for c in codes)
    check(f"{label} -> no 5xx", not bad, f"final={resp.status_code} chain={codes}")
    return resp


def mk_employer(slug):
    u = User.objects.create_user(slug, f"{slug}@example.com", "pw")
    return Profile.objects.create(user=u, role=Profile.Role.EMPLOYER,
                                  company_name=f"{slug.title()} Ltd", phone="08012345678")


def subscribe(emp, plan, days):
    now = timezone.now()
    return Subscription.objects.create(
        employer=emp, plan=plan, amount=50000 if plan == "basic" else 100000,
        starts_at=now, expires_at=now + timedelta(days=days), is_active=True,
    )


def mk_candidate(i):
    u = User.objects.create_user(f"cand{i}", f"cand{i}@example.com", "pw")
    return Profile.objects.create(
        user=u, role=Profile.Role.CANDIDATE,
        verification_status=Profile.VerificationStatus.VERIFIED,
    )


admin = User.objects.create_user("sub_admin", "subadmin@example.com", "pw", is_staff=True)
ac = Client()
ac.force_login(admin)

REQ = {
    "position": "Accountant",
    "professionals_required": 10,
    "minimum_qualification": "BSc",
    "certifications": "",
    "years_experience": 3,
    "required_skills": "Excel, VAT",
    "salary_min": 100000,
    "salary_max": 200000,
    "salary_period": "monthly",
}

print("\n=== 1. Employer with NO plan is blocked from the request page ===")
e0 = mk_employer("nosub")
c0 = Client()
c0.force_login(e0.user)
r = c0.get(reverse("website:employer_section", args=["requests"]))
check("requests page 200", r.status_code == 200, r.status_code)
body = r.content.decode()
check("gate modal present", 'id="empSubGate"' in body)
check("form blurred (is-locked)", "is-locked" in body)
check("submit disabled", 'class="emp-submit-btn" disabled' in body,
      [l for l in body.splitlines() if "emp-submit-btn" in l][:1])
check("offers both plans", "Choose Basic" in body and "Choose Premium" in body)

r = c0.post(reverse("website:employer_section", args=["requests"]), REQ, follow=True)
check("server refuses the POST", RecruitmentRequest.objects.filter(employer=e0).count() == 0,
      f"count={RecruitmentRequest.objects.filter(employer=e0).count()}")
check("no 5xx on blocked POST", r.status_code < 500, r.status_code)

print("\n=== 2. Basic plan: activated, may request, 30-day term ===")
e1 = mk_employer("basicemp")
s1 = subscribe(e1, Subscription.Plan.BASIC, 30)
check("match_limit is 5", s1.match_limit == 5, s1.match_limit)
check("duration_days is 30", s1.duration_days == 30, s1.duration_days)
check("is_current true", s1.is_current)
c1 = Client()
c1.force_login(e1.user)
r = c1.post(reverse("website:employer_section", args=["requests"]), REQ, follow=True)
check("Basic employer CAN submit a request",
      RecruitmentRequest.objects.filter(employer=e1).count() == 1)
r = c1.get(reverse("website:employer_section", args=["requests"]))
check("no gate for active Basic", 'id="empSubGate"' not in r.content.decode())

print("\n=== 3. Premium plan: 90-day term, unlimited matching ===")
e2 = mk_employer("prememp")
s2 = subscribe(e2, Subscription.Plan.PREMIUM, 90)
check("match_limit is None (unlimited)", s2.match_limit is None, s2.match_limit)
check("duration_days is 90", s2.duration_days == 90, s2.duration_days)

print("\n=== 4. Payment approval sets the correct term per plan ===")
e3 = mk_employer("paybasic")
c3 = Client()
c3.force_login(e3.user)
proof = SimpleUploadedFile("r.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, content_type="image/png")
r = c3.post(reverse("website:submit_payment_proof"),
            {"plan": "basic", "bank_name": "GT", "sender_name": "X", "proof": proof}, follow=True)
from website.models import Payment
p = Payment.objects.filter(employer=e3).latest("id")
no_5xx("basic payment approval", ac.post(
    reverse("website:admin_payment_action", args=[p.pk]),
    {"action": "approve", "admin_notes": "ok"}, follow=True))
p.refresh_from_db()
sub = p.subscription
check("Basic approved -> 30 day term", (sub.expires_at - sub.starts_at).days == 30,
      (sub.expires_at - sub.starts_at).days)
check("Basic activated", sub.is_active and sub.is_current)
check("Basic match_limit 5", sub.match_limit == 5, sub.match_limit)

e4 = mk_employer("payprem")
c4 = Client()
c4.force_login(e4.user)
proof2 = SimpleUploadedFile("r2.png", b"\x89PNG\r\n\x1a\n" + b"1" * 32, content_type="image/png")
r = c4.post(reverse("website:submit_payment_proof"),
            {"plan": "premium", "bank_name": "GT", "sender_name": "X", "proof": proof2}, follow=True)
p2 = Payment.objects.filter(employer=e4).latest("id")
no_5xx("premium payment approval", ac.post(
    reverse("website:admin_payment_action", args=[p2.pk]),
    {"action": "approve", "admin_notes": "ok"}, follow=True))
p2.refresh_from_db()
sub2 = p2.subscription
check("Premium approved -> 90 day term", (sub2.expires_at - sub2.starts_at).days == 90,
      (sub2.expires_at - sub2.starts_at).days)
check("Premium plan recorded", sub2.plan == Subscription.Plan.PREMIUM, sub2.plan)
check("Premium match_limit None", sub2.match_limit is None)

print("\n=== 5. Admin matching page shows the plan ===")
req1 = RecruitmentRequest.objects.filter(employer=e1).first()
r = ac.get(reverse("website:admin_section", args=["matching"]) + f"?request={req1.pk}")
check("matching page 200", r.status_code == 200, r.status_code)
mb = r.content.decode()
check("plan pill rendered on request card", "mt-plan-pill" in mb)
check("employer's Basic plan shown", "mt-plan-pill--basic" in mb)
check("cap text shown", "5 per request" in mb)
check("allowance banner shown", "mt-plan-banner" in mb and "allows" in mb)
check("cap modal markup present", 'id="planCapModal"' in mb)
check("banner carries the cap data", 'data-limit="5"' in mb)

# A premium employer should read as unlimited, not capped.
# e4 only ever paid, so give them a request to focus on.
c4b = Client()
c4b.force_login(e4.user)
c4b.post(reverse("website:employer_section", args=["requests"]), REQ, follow=True)
req2pre = RecruitmentRequest.objects.filter(employer=e4).first()
check("premium employer could post a request", req2pre is not None)
r = ac.get(reverse("website:admin_section", args=["matching"]) + f"?request={req2pre.pk}")
mb2 = r.content.decode()
check("premium pill rendered", "mt-plan-pill--premium" in mb2)
check("premium reads unlimited", "Unlimited" in mb2 or "unlimited" in mb2)
check("no cap on premium banner", "is-capped" not in mb2)

print("\n=== 6. Basic employer: capped at 5 matches per request ===")
cands = [mk_candidate(i) for i in range(7)]
url = reverse("website:create_match")
for i in range(5):
    r = ac.post(url, {"request": req1.pk, "candidate": cands[i].pk}, follow=True)
    no_5xx(f"basic match {i+1}", r)
check("5 matches created", CandidateMatch.objects.filter(request=req1, is_active=True).count() == 5,
      CandidateMatch.objects.filter(request=req1, is_active=True).count())

# 6th must be refused
before = CandidateMatch.objects.filter(request=req1, is_active=True).count()
r = ac.post(url, {"request": req1.pk, "candidate": cands[5].pk}, follow=True)
after = CandidateMatch.objects.filter(request=req1, is_active=True).count()
check("6th match REFUSED on Basic", after == before == 5, f"{before} -> {after}")
check("cap message shown", "Basic plan" in r.content.decode() and "5 candidate" in r.content.decode())

print("\n=== 7. Withdrawing a match frees a slot on Basic ===")
victim = CandidateMatch.objects.filter(request=req1, is_active=True).first()
rm = reverse("website:remove_match", args=[victim.pk])
no_5xx("withdraw match", ac.post(rm, {}, follow=True))
check("now 4 active matches", CandidateMatch.objects.filter(request=req1, is_active=True).count() == 4)
r = ac.post(url, {"request": req1.pk, "candidate": cands[5].pk}, follow=True)
check("new match allowed after withdrawal",
      CandidateMatch.objects.filter(request=req1, is_active=True).count() == 5)

print("\n=== 8. Premium employer: unlimited matches ===")
c5 = Client()
c5.force_login(e2.user)
c5.post(reverse("website:employer_section", args=["requests"]), REQ, follow=True)
req2 = RecruitmentRequest.objects.filter(employer=e2).first()
pc = [mk_candidate(100 + i) for i in range(7)]
for i in range(7):
    r = ac.post(url, {"request": req2.pk, "candidate": pc[i].pk}, follow=True)
no_5xx("premium match 7", r)
check("Premium allowed 7 matches",
      CandidateMatch.objects.filter(request=req2, is_active=True).count() == 7,
      CandidateMatch.objects.filter(request=req2, is_active=True).count())

print("\n=== 9. Expired plan blocks requests again ===")
e1.subscriptions.filter(pk=s1.pk).update(expires_at=timezone.now() - timedelta(days=1))
e1.refresh_from_db()
check("expired plan is not current", e1.current_subscription() is None)
check("has_active_plan False", not e1.has_active_plan())
c1b = Client()
c1b.force_login(e1.user)
before = RecruitmentRequest.objects.filter(employer=e1).count()
r = c1b.post(reverse("website:employer_section", args=["requests"]), REQ, follow=True)
check("expired employer CANNOT submit",
      RecruitmentRequest.objects.filter(employer=e1).count() == before)
r = c1b.get(reverse("website:employer_section", args=["requests"]))
gb = r.content.decode()
check("gate returns for expired plan", 'id="empSubGate"' in gb)
check("modal explains expiry", "expired" in gb.lower())

print("\n=== 10. Renewal window logic ===")
check("premium @13 days -> renew", subscribe(mk_employer("w1"), Subscription.Plan.PREMIUM, 13).renewal_window_open())
check("premium @30 days -> no renew", not subscribe(mk_employer("w2"), Subscription.Plan.PREMIUM, 30).renewal_window_open())
check("basic @5 days -> renew", subscribe(mk_employer("w3"), Subscription.Plan.BASIC, 5).renewal_window_open())
check("basic @20 days -> no renew", not subscribe(mk_employer("w4"), Subscription.Plan.BASIC, 20).renewal_window_open())

print("\n=== 11. Subscription page shows term + renewal prompt ===")
e5 = mk_employer("renewsoon")
subscribe(e5, Subscription.Plan.PREMIUM, 10)
c6 = Client()
c6.force_login(e5.user)
r = c6.get(reverse("website:employer_section", args=["subscription"]))
sb = r.content.decode()
check("subscription page 200", r.status_code == 200, r.status_code)
check("premium renewal modal shown", 'id="renewalModal"' in sb)
check("offers continue premium", "Continue Premium" in sb)
check("offers downgrade to basic", "Downgrade to Basic" in sb)
check("shows /3mo term", "/3mo" in sb)

runner.teardown_databases(old_config)
teardown_test_environment()

# Mirror the console summary to a file: the shared terminal has been
# intermittently dropping piped output on this machine.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_plans_result.txt"),
          "w", encoding="utf-8") as fh:
    fh.write("ALL CHECKS PASSED\n" if ok else "SOME CHECKS FAILED\n")

print("\n" + "=" * 50)
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
print("=" * 50)
raise SystemExit(0 if ok else 1)

mb = r.content.decode()
check("plan pill rendered", "mt-plan-pill" in mb)
check("shows Basic", "Basic" in mb)
check("shows the 5 cap", "5 per request" in mb or "allows 5 candidate" in mb)
check("cap modal markup present", 'id="planCapModal"' in mb)

ac = Client()
ac.force_login(admin)
