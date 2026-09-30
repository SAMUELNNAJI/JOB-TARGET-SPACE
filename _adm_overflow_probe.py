"""Measure horizontal overflow on the admin dashboard at mobile widths.

Runs Django against a throwaway sqlite DB (never touches db.sqlite3), seeds a
realistic admin dataset, then walks the rendered page with Playwright and
reports every element whose box extends past the viewport.

    .venv\\Scripts\\python.exe _adm_overflow_probe.py
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
SCRATCH_DB = BASE / "_adm_probe.sqlite3"
PORT = 8791
WIDTHS = [320, 360, 375, 390, 414, 768, 1024, 1280, 1440]

os.environ["DJANGO_SETTINGS_MODULE"] = "jobspace.settings"
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = f"sqlite:///{SCRATCH_DB}"
os.environ["SECRET_KEY"] = "probe-key"
os.environ["SECURE_SSL_REDIRECT"] = "False"

sys.path.insert(0, str(BASE))


def seed():
    import django

    django.setup()
    from django.contrib.auth import (
        BACKEND_SESSION_KEY,
        HASH_SESSION_KEY,
        SESSION_KEY,
        get_user_model,
    )
    from django.contrib.sessions.backends.db import SessionStore
    from django.core.management import call_command
    from django.utils import timezone

    from website.models import (
        AuditLog,
        CandidateMatch,
        Payment,
        Profile,
        RecruitmentRequest,
    )

    call_command("migrate", verbosity=0, run_syncdb=True)

    User = get_user_model()
    admin = User.objects.filter(username="probe_admin").first()
    if admin is None:
        admin = User.objects.create_superuser("probe_admin", "a@b.com", "pw12345")
    admin.is_staff = True
    admin.save()

    emp = Profile.objects.filter(user__username="probe_emp").first()
    if emp is None:
        eu = User.objects.create_user("probe_emp", "e@b.com", "pw12345")
        emp = Profile.objects.create(
            user=eu,
            role=Profile.Role.EMPLOYER,
            company_name="Guinness Nigerian Brewery Plc Lagos Ikeja",
            industry_sector="Beverages & FMCG Manufacturing",
        )
    cand = Profile.objects.filter(user__username="probe_cand").first()
    if cand is None:
        cu = User.objects.create_user("probe_cand", "c@b.com", "pw12345")
        cand = Profile.objects.create(
            user=cu,
            role=Profile.Role.CANDIDATE,
            legal_name="Chidinma Nweke-Ezeocha Okafor",
            verification_status=Profile.VerificationStatus.PENDING,
        )
    if not Profile.objects.filter(user__username="probe_cand2").exists():
        c2u = User.objects.create_user("probe_cand2", "c2@b.com", "pw12345")
        Profile.objects.create(
            user=c2u,
            role=Profile.Role.CANDIDATE,
            legal_name="Adebayo Chukwuemekaokonkwo Bassey",
            verification_status=Profile.VerificationStatus.VERIFIED,
        )

    if not RecruitmentRequest.objects.exists():
        RecruitmentRequest.objects.create(
            employer=emp,
            position="Senior Process Automation Engineer",
            professionals_required=3,
            minimum_qualification="B.Eng Mechatronics",
            required_skills="PLC, SCADA",
            years_experience=5,
            salary_min=400000,
            salary_max=900000,
        )
    if not CandidateMatch.objects.exists():
        CandidateMatch.objects.create(
            profile=cand,
            employer=emp,
            is_accepted=True,
            accepted_at=timezone.now(),
        )
    if not Payment.objects.exists():
        Payment.objects.create(
            employer=emp, reference="PRB-1", amount=100000,
            status=Payment.Status.SUCCESS, paid_at=timezone.now(),
        )
    if not AuditLog.objects.exists():
        AuditLog.objects.create(
            actor=admin,
            action="Verified candidate profile and pushed to matching pool",
            subject="Chidinma Nweke-Ezeocha Okafor",
        )

    store = SessionStore()
    store[SESSION_KEY] = str(admin.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = admin.get_session_auth_hash()
    store.save()
    return store.session_key



PROBE_JS = """
() => {
  const vw = document.documentElement.clientWidth;
  const bad = [];
  document.querySelectorAll('body *').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return;
    // Anything inside a scroll container is by design: it sticks out so it
    // can be scrolled to, and it never extends the document.
    let a = el.parentElement, clipped = false;
    while (a && a !== document.documentElement) {
      if (getComputedStyle(a).overflowX !== 'visible') { clipped = true; break; }
      a = a.parentElement;
    }
    const over = Math.round(r.right - vw);
    if (over > 1 && !clipped) {
      const cls = (typeof el.className === 'string' && el.className.trim())
        ? '.' + el.className.trim().split(/\\s+/).slice(0, 4).join('.') : '';
      bad.push({
        sel: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + cls,
        w: Math.round(r.width), right: Math.round(r.right), over,
      });
    }
  });
  const seen = new Map();
  bad.forEach((b) => { if (!seen.has(b.sel) || seen.get(b.sel).over < b.over) seen.set(b.sel, b); });
  const scrollers = [...document.querySelectorAll('.dashboard-table-scroll')]
    .map((s) => ({
      box: Math.round(s.clientWidth), content: Math.round(s.scrollWidth),
      canScroll: s.scrollWidth > s.clientWidth + 1,
      tableW: Math.round(s.querySelector('table')?.scrollWidth || 0),
    }));
  return {
    vw,
    scrollW: document.documentElement.scrollWidth,
    docOver: document.documentElement.scrollWidth - vw,
    scrollers,
    bad: [...seen.values()].sort((a, b) => b.over - a.over).slice(0, 14),
  };
}
"""


def kill_stale_servers():
    """Leftover runserver processes hold a sqlite lock on the scratch DB and
    make requests hang, which looks like a browser timeout."""
    subprocess.run(
        ["pwsh", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
         "Where-Object { $_.CommandLine -like '*runserver*' -and "
         "$_.CommandLine -like '*" + str(PORT) + "*' } | "
         "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
        check=False, capture_output=True,
    )


def main():
    kill_stale_servers()
    time.sleep(1)
    if SCRATCH_DB.exists():
        SCRATCH_DB.unlink()
    session_key = seed()

    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{PORT}", "--noreload"],
        cwd=str(BASE), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/signin/", timeout=1)
                break
            except Exception:
                time.sleep(0.5)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            for w in WIDTHS:
                ctx = browser.new_context(viewport={"width": w, "height": 850})
                ctx.add_cookies([{
                    "name": "sessionid", "value": session_key,
                    "domain": "127.0.0.1", "path": "/",
                }])
                page = ctx.new_page()
                page.set_default_navigation_timeout(60000)
                page.goto(f"http://127.0.0.1:{PORT}/dashboard/admin/",
                          wait_until="domcontentloaded")
                page.wait_for_timeout(600)
                res = page.evaluate(PROBE_JS)
                print(f"\n=== width {w}px | scrollWidth={res['scrollW']} "
                      f"| PAGE OVERFLOW={res['docOver']}px ===")
                for b in res["bad"]:
                    print(f"  +{b['over']:>4}px w={b['w']:>4}  {b['sel']}")
                if not res["bad"]:
                    print("  (no page-level offenders)")
                for s in res["scrollers"]:
                    print(f"  table-scroll: box={s['box']} content={s['content']} "
                          f"scrollable={s['canScroll']}")
                if w in (375, 1280):
                    page.screenshot(
                        path=str(BASE / f"_adm_{w}_after.png"), full_page=True)
                ctx.close()
            browser.close()
    finally:
        server.terminate()
        server.kill()
        kill_stale_servers()


if __name__ == "__main__":
    main()
