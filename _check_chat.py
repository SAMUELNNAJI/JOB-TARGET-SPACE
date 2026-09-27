"""End-to-end test of the support chat: user -> staff -> user, permissions,
incremental polling, and the nav badge. Run with:  python _check_chat.py
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
# The Django test Client sends Host: testserver, which production ALLOWED_HOSTS
# rightly rejects. Widen it for the duration of this script only.
from django.conf import settings as _dj_settings

_dj_settings.ALLOWED_HOSTS = list(_dj_settings.ALLOWED_HOSTS) + ["testserver"]

django.setup()


def step(msg):
    """Progress marker — Neon round-trips are slow, so show where we are."""
    print(f"... {msg}", flush=True)

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from website.context_processors import dashboard_badges
from website.models import Profile, SupportMessage, SupportThread

User = get_user_model()
PASS = FAIL = 0


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL:", label, flush=True)


suffix = django.utils.timezone.now().strftime("%H%M%S%f")
emp_u = User.objects.create_user(f"t_emp_{suffix}", password="x")
cand_u = User.objects.create_user(f"t_cand_{suffix}", password="x")
admin_u = User.objects.create_user(f"t_adm_{suffix}", password="x", is_staff=True)
emp = Profile.objects.create(user=emp_u, role=Profile.Role.EMPLOYER, company_name="Acme")
cand = Profile.objects.create(user=cand_u, role=Profile.Role.CANDIDATE)

step('user opens Support')
# ── User opens Support ──────────────────────────────────────────────────
c = Client()
check("employer can sign in", c.login(username=emp_u.username, password="x"))

r = c.get("/dashboard/employer/support/")
check("employer /support/ redirects to chat",
      r.status_code == 302 and r["Location"].endswith(reverse("website:support_chat")))

r = c.get(reverse("website:support_chat"))
check("chat page renders", r.status_code == 200 and b"chat-composer" in r.content)
check("chat page loads htmx", b"htmx.min.js" in r.content)
check("thread auto-created on first open", SupportThread.objects.filter(profile=emp).exists())

thread = SupportThread.objects.get(profile=emp)

# ── User sends a message ────────────────────────────────────────────────
r = c.post(reverse("website:support_chat_send"), {"body": "How long does verification take?"})
check("send returns 200", r.status_code == 200)
check("message persisted", thread.messages.filter(body="How long does verification take?").exists())
check("sent message marked as user's", thread.messages.last().sender_role == SupportMessage.Role.USER)
check("user message unread for staff", thread.messages.last().is_read is False)
thread.refresh_from_db()
check("thread last_message_at stamped", thread.last_message_at is not None)
check("reply renders as own bubble", b"chat-msg--out" in r.content)

# ── Empty body rejected ─────────────────────────────────────────────────
before = thread.messages.count()
c.post(reverse("website:support_chat_send"), {"body": "   "})
check("blank body creates nothing", thread.messages.count() == before)

# ── Incremental polling ─────────────────────────────────────────────────
first = thread.messages.last().id
SupportMessage.objects.create(thread=thread, sender=admin_u,
                              sender_role=SupportMessage.Role.STAFF, body="Hello")
r = c.get(reverse("website:support_chat_messages"), {"after": first})
check("poll ?after= returns only newer", b"How long does verification" not in r.content)
check("poll includes the new message", b"Hello" in r.content)

step('staff side')
# ── Staff side ──────────────────────────────────────────────────────────
a = Client()
check("admin can sign in", a.login(username=admin_u.username, password="x"))
check("admin inbox renders", a.get(reverse("website:admin_support_inbox")).status_code == 200)

# "Chat now" resolves a profile into a thread, then redirects.
r = a.get(reverse("website:admin_support_inbox"), {"profile": cand.pk})
check("?profile= creates thread + redirects", r.status_code == 302)
cand_thread = SupportThread.objects.get(profile=cand)
check("redirect carries thread id", f"thread={cand_thread.pk}" in r["Location"])

# Staff poll returns only NEW bubbles. A request without ?after= is
# deliberately empty (that history dump is what duplicated messages), so ask
# from a point before the first message to see the transcript.
head_before = SupportMessage.objects.filter(thread=thread).order_by("id").first().id - 1
r = a.get(reverse("website:admin_support_messages"),
          {"thread": thread.pk, "after": head_before})
check("staff poll returns transcript",
      r.status_code == 200 and b"How long does verification" in r.content)

r = a.post(reverse("website:admin_support_send"),
           {"thread": thread.pk, "body": "Usually 2-3 business days."})

step('permissions')
# ── Composer: CSRF token must be present ───────────────────────────────
# The original bug: htmx does NOT add the X-CSRFToken header on its own, so a
# form without {% csrf_token %} makes Django reject every POST with 403.
# Assert the token is really in the markup.
page = c.get(reverse("website:support_chat")).content
composer_markup = page.split(b'class="chat-composer"', 1)[-1].split(b"</form>", 1)[0]
check("composer form has a CSRF token", b"csrfmiddlewaretoken" in composer_markup)
check("composer form has enctype for uploads", b"multipart/form-data" in composer_markup)
check("composer has a mic button", b"data-mic" in composer_markup)
check("composer has an audio file input", b'name="audio"' in composer_markup)

# ── No template syntax leaks into the rendered page ─────────────────────
# Django's {# ... #} comment is SINGLE-LINE only. A multi-line one is not
# recognised as a tag at all and gets printed verbatim into the page, which is
# exactly what happened (the comments were visible on screen).
check("no raw {# leaked into the page", b"{#" not in page)
check("no raw {% leaked into the page", b"{%" not in page)
check("no template comment text leaked", b"csrf_token is REQUIRED" not in page)
check("no vendored htmx note leaked", b"htmx is vendored" not in page)
check("no chat.css note leaked", b"Loaded after dashboard.css" not in page)

# Admin side must be clean too.
admin_page = a.get(reverse("website:admin_support_inbox")).content
check("admin page has no raw {# leak", b"{#" not in admin_page)
check("admin page has no raw {% leak", b"{%" not in admin_page)

# The empty state must live OUTSIDE #chat-thread or polling duplicates it.
thread_part = page.split(b'id="chat-thread"', 1)[-1].split(b"</form>", 1)[0]
check("empty state is outside the polled thread", b"chat-empty" not in thread_part)

# The poll response must contain bubbles only — returning the wrapper would
# nest #chat-thread inside itself on every tick.
r = c.get(reverse("website:support_chat_messages"))
check("poll returns no nested wrapper", r.content.count(b'id="chat-thread"') == 0)
check("poll returns no duplicated empty state", b"No messages yet" not in r.content)

# ── No duplicate messages ──────────────────────────────────────────────
# The bug: the poll used to answer a request WITHOUT ?after= with a recent
# history dump, and chat.js only re-added ?after= on afterSettle — not after
# the send-swap. So the next tick re-appended the message just sent, and every
# message appeared twice. Both halves are asserted here.
last_id = thread.messages.last().id
r = c.get(reverse("website:support_chat_messages"))  # no ?after=
check("poll without ?after= returns nothing", b"chat-msg" not in r.content)

# With ?after= at the current head, nothing new yet.
r = c.get(reverse("website:support_chat_messages"), {"after": last_id})
check("poll at head returns nothing", b"chat-msg" not in r.content)

# A genuine new message IS returned exactly once.
SupportMessage.objects.create(
    thread=thread, sender=emp_u, sender_role=SupportMessage.Role.USER,
    body="only once please",
)
r = c.get(reverse("website:support_chat_messages"), {"after": last_id})
check("poll returns the new message once", r.content.count(b"only once please") == 1)
check("poll does not replay older messages", b"How long does verification" not in r.content)

# Same guarantee on the admin side.
r = a.get(reverse("website:admin_support_messages"), {"thread": thread.pk})
check("admin poll without ?after= returns nothing", b"chat-msg" not in r.content)

# ── Voice notes ────────────────────────────────────────────────────────
from django.core.files.uploadedfile import SimpleUploadedFile
import wave, struct, io


def make_wav(seconds=1, rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", 0) for _ in range(rate * seconds)))
    buf.seek(0)
    return SimpleUploadedFile("voice.webm", buf.read(), content_type="audio/webm")


r = c.post(reverse("website:support_chat_send"),
           {"body": "", "audio": make_wav()})
check("audio-only message accepted", r.status_code == 200)
check("audio message persisted", thread.messages.filter(audio__isnull=False).exists())
check("audio bubble rendered", b"chat-audio" in r.content and b"data-audio-el" in r.content)
check("audio play button uses data-audio-toggle", b"data-audio-toggle" in r.content)
check("audio duration label rendered", b"data-audio-time" in r.content)
check("audio has no stale duration attribute", b"data-duration" not in r.content)
check("audio message has a public url", thread.messages.filter(audio__isnull=False)
      .last().audio.url.startswith("/media/chat_audio/"))

# A message with neither text nor audio is rejected.
before = thread.messages.count()
c.post(reverse("website:support_chat_send"), {"body": "", "audio": ""})
check("totally empty message rejected", thread.messages.count() == before)

# ── Permissions ─────────────────────────────────────────────────────────
# NOTE: admin endpoints are guarded by user_passes_test, which REDIRECTS a
# logged-in non-staff user to LOGIN_URL (302). The user-side endpoints instead
# reject with 403. Both are correct denials; just different codes.
check("user cannot open staff inbox",
      c.get(reverse("website:admin_support_inbox")).status_code == 302)
check("user cannot post staff reply",
      c.post(reverse("website:admin_support_send"),
             {"thread": thread.pk, "body": "nope"}).status_code == 302)
check("staff cannot post as a user",
      a.post(reverse("website:support_chat_send"), {"body": "nope"}).status_code == 403)
check("anonymous cannot send",
      Client().post(reverse("website:support_chat_send"),
                    {"body": "nope"}).status_code == 302)

step('chat badge')
# ── Chat badge ──────────────────────────────────────────────────────────
def badge_markup():
    return c.get("/dashboard/employer/").content


# Opening Support clears anything already waiting, so start from a clean slate.
c.get(reverse("website:support_chat"))
check("no chat badge once Support has been read", b"Support Chat<span" not in badge_markup())

SupportMessage.objects.create(thread=thread, sender=admin_u,
                              sender_role=SupportMessage.Role.STAFF, body="Another one")
check("chat badge appears for a new staff reply", b"Support Chat<span" in badge_markup())

c.get(reverse("website:support_chat"))
check("opening Support clears the badge", b"Support Chat<span" not in badge_markup())

# ── CSRF is actually enforced ───────────────────────────────────────────
# The Django test Client skips CSRF by default, which is exactly why the
# missing {% csrf_token %} bug shipped unnoticed. This client enforces it, so
# a composer without the token fails here with 403 — the same failure a real
# browser hit.
step("csrf enforcement")
strict = Client(enforce_csrf_checks=True)
strict.login(username=emp_u.username, password="x")
page = strict.get(reverse("website:support_chat")).content
form = page.split(b'class="chat-composer"', 1)[-1].split(b"</form>", 1)[0]
check("strict client also sees the token", b"csrfmiddlewaretoken" in form)

# Post WITH the token taken from the page -> succeeds.
tok = form.split(b'name="csrfmiddlewaretoken" value="', 1)[1].split(b'"', 1)[0].decode()
before = thread.messages.count()
r = strict.post(reverse("website:support_chat_send"),
                {"body": "csrf protected", "csrfmiddlewaretoken": tok})
check("send with CSRF token succeeds", r.status_code == 200
      and thread.messages.count() == before + 1)

# Post WITHOUT it -> 403, proving the guard is what protects the endpoint.
r = strict.post(reverse("website:support_chat_send"), {"body": "no token"})
check("send without CSRF token is rejected", r.status_code == 403)

step('cleanup')
# ── Cleanup ─────────────────────────────────────────────────────────────
for t in SupportThread.objects.filter(profile__in=[emp, cand]):
    t.delete()
emp.delete(); cand.delete()
emp_u.delete(); cand_u.delete(); admin_u.delete()

print(f"RESULT: {PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)

check("staff reply saved", thread.messages.filter(body="Usually 2-3 business days.").exists())
check("staff reply flagged staff", thread.messages.last().sender_role == SupportMessage.Role.STAFF)
check("staff reply notifies user", emp.notifications.filter(kind="system").exists())

thread.refresh_from_db()
check("user message marked read by staff",
      thread.messages.get(body="How long does verification take?").is_read is True)
