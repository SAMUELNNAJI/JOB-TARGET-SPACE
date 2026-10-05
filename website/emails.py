"""
Centralised email sending for Target JobSpace.

All emails go through send_email() which wraps Django's send_mail with:
  - graceful failure (logs but never crashes the request)
  - consistent From address from settings
  - plain-text fallback alongside HTML

Usage:
    from .emails import send_welcome_email, send_contact_email, ...
"""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

SITE_NAME = "Target JobSpace"
SITE_URL  = "https://targetjobspace.com"


def _send(subject, text_body, html_body, to_email):
    """Low-level wrapper — never raises, always logs failures."""
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", f"{SITE_NAME} <noreply@targetjobspace.com>")
        msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    except Exception as exc:
        logger.error("Email failed to %s — %s: %s", to_email, type(exc).__name__, exc)


def _wrap_html(title, content_html, cta_text=None, cta_url=None):
    """Wrap content in a minimal branded HTML email template."""
    cta_block = ""
    if cta_text and cta_url:
        cta_block = f"""
        <tr><td align="center" style="padding:24px 0 8px">
          <a href="{cta_url}"
             style="display:inline-block;padding:14px 32px;background:#d90429;
                    color:#fff;text-decoration:none;border-radius:999px;
                    font-weight:700;font-size:15px;font-family:'Helvetica Neue',Arial,sans-serif">
            {cta_text}
          </a>
        </td></tr>"""
    return f"""<!doctype html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:'Helvetica Neue',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:32px 0">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)">
      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#090909,#1a0a0a);padding:28px 36px">
        <span style="font-size:22px;font-weight:800;color:#fff;letter-spacing:-.5px">
          Target <span style="color:#d90429">JobSpace</span>
        </span>
      </td></tr>
      <!-- Body -->
      <tr><td style="padding:36px 36px 24px;color:#111827;font-size:15px;line-height:1.7">
        {content_html}
      </td></tr>
      {cta_block}
      <!-- Footer -->
      <tr><td style="padding:20px 36px 28px;border-top:1px solid #f0f0f0">
        <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6">
          You received this email because you have an account on
          <a href="{SITE_URL}" style="color:#d90429">targetjobspace.com</a>.
          If you did not create an account, please ignore this email.
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# 1. Welcome email — sent on signup
# ─────────────────────────────────────────────────────────────────────────────

def send_welcome_email(user, role):
    """Send a role-specific welcome + profile-complete reminder."""
    is_candidate = (role == "candidate")
    name = user.first_name or user.username

    if is_candidate:
        subject = f"Welcome to Target JobSpace, {name} 🎉 — Your next career move starts here"
        profile_url = f"{SITE_URL}/dashboard/candidate/profile/"
        cta_text = "Complete my profile now"
        content_html = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:800;color:#111827">
          Welcome, {name}! 👋
        </h2>
        <p>Your candidate account is ready. Here is what happens next:</p>
        <ol style="padding-left:20px;margin:12px 0">
          <li style="margin-bottom:8px"><strong>Complete your professional profile</strong> — add your degree, skills, certifications and a professional pitch.</li>
          <li style="margin-bottom:8px"><strong>Upload your CV</strong> — our administrators review it before adding you to the talent pool.</li>
          <li style="margin-bottom:8px"><strong>Get matched</strong> — once verified, our team introduces you directly to employers looking for your exact skills.</li>
        </ol>
        <p style="margin:16px 0 8px;padding:16px;background:#fff8f8;border-left:4px solid #d90429;border-radius:0 8px 8px 0;font-size:14px">
          <strong>Important:</strong> Employers cannot see your profile until it is complete and verified.
          Click the button below to fill it in now — it takes about 10 minutes.
        </p>"""
        text_body = (
            f"Welcome to Target JobSpace, {name}!\n\n"
            "Complete your professional profile so employers can find you:\n"
            f"{profile_url}\n\n"
            "1. Add your degree, skills, certifications and pitch.\n"
            "2. Upload your CV.\n"
            "3. Get matched with employers looking for your skills.\n\n"
            "Employers cannot see your profile until it is complete and verified."
        )
    else:
        subject = f"Welcome to Target JobSpace, {name} — Start hiring smarter"
        profile_url = f"{SITE_URL}/dashboard/employer/profile/"
        cta_text = "Complete my company profile"
        content_html = f"""
        <h2 style="margin:0 0 16px;font-size:22px;font-weight:800;color:#111827">
          Welcome, {name}! 👋
        </h2>
        <p>Your employer account is ready. Here is what to do first:</p>
        <ol style="padding-left:20px;margin:12px 0">
          <li style="margin-bottom:8px"><strong>Complete your company profile</strong> — add your company name, industry, office address and hiring contact.</li>
          <li style="margin-bottom:8px"><strong>Choose a subscription plan</strong> — unlock access to our verified talent pool.</li>
          <li style="margin-bottom:8px"><strong>Post a recruitment request</strong> — tell us exactly who you need and our team sources, vets and pushes the right candidates straight to your dashboard.</li>
        </ol>
        <p style="margin:16px 0 8px;padding:16px;background:#fff8f8;border-left:4px solid #d90429;border-radius:0 8px 8px 0;font-size:14px">
          <strong>Get started:</strong> Complete your company profile first — it takes less than 5 minutes and unlocks everything else.
        </p>"""
        text_body = (
            f"Welcome to Target JobSpace, {name}!\n\n"
            "Complete your company profile to start hiring:\n"
            f"{profile_url}\n\n"
            "1. Add your company details.\n"
            "2. Choose a subscription plan.\n"
            "3. Post a recruitment request — we source and vet candidates for you.\n"
        )

    html_body = _wrap_html(subject, content_html, cta_text, profile_url)
    _send(subject, text_body, html_body, user.email)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Contact form email — forwarded to CONTACT_EMAIL
# ─────────────────────────────────────────────────────────────────────────────

def send_contact_email(sender_name, sender_email, sender_phone, subject_line, message_body):
    """Forward a contact form submission to the team inbox."""
    contact_email = getattr(settings, "CONTACT_EMAIL", "info@targetjobspace.com")
    subject = f"[Contact Form] {subject_line or 'New message'} — from {sender_name}"
    text_body = (
        f"Name: {sender_name}\n"
        f"Email: {sender_email}\n"
        f"Phone: {sender_phone or '—'}\n"
        f"Subject: {subject_line or '—'}\n\n"
        f"Message:\n{message_body}"
    )
    content_html = f"""
    <h2 style="margin:0 0 16px;font-size:20px;font-weight:800">New contact form message</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <tr><td style="padding:8px 0;color:#6b7280;width:90px">Name</td><td style="padding:8px 0;font-weight:600">{sender_name}</td></tr>
      <tr><td style="padding:8px 0;color:#6b7280">Email</td><td style="padding:8px 0"><a href="mailto:{sender_email}" style="color:#d90429">{sender_email}</a></td></tr>
      <tr><td style="padding:8px 0;color:#6b7280">Phone</td><td style="padding:8px 0">{sender_phone or '—'}</td></tr>
      <tr><td style="padding:8px 0;color:#6b7280">Subject</td><td style="padding:8px 0">{subject_line or '—'}</td></tr>
    </table>
    <hr style="border:none;border-top:1px solid #f0f0f0;margin:20px 0">
    <p style="white-space:pre-wrap;font-size:14px;color:#374151">{message_body}</p>"""
    html_body = _wrap_html(subject, content_html)

    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", f"{SITE_NAME} <noreply@targetjobspace.com>")
        msg = EmailMultiAlternatives(subject, text_body, from_email, [contact_email],
                                     reply_to=[f"{sender_name} <{sender_email}>"])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    except Exception as exc:
        logger.error("Contact email failed — %s: %s", type(exc).__name__, exc)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Support nudge — admin replied, user is offline
# ─────────────────────────────────────────────────────────────────────────────

def send_support_reply_nudge(user):
    """Notify a user by email that admin has replied in their support chat."""
    name = user.first_name or user.username
    chat_url = f"{SITE_URL}/dashboard/support/chat/"
    subject = "Target JobSpace Support has replied to your message"
    content_html = f"""
    <h2 style="margin:0 0 12px;font-size:20px;font-weight:800">You have a new reply 💬</h2>
    <p>Hi {name},</p>
    <p>The Target JobSpace support team has replied to your message.
    Log in to continue the conversation.</p>"""
    text_body = (
        f"Hi {name},\n\n"
        "The Target JobSpace support team has replied to your message.\n"
        f"Log in to continue the conversation: {chat_url}\n"
    )
    html_body = _wrap_html(subject, content_html, "View reply", chat_url)
    _send(subject, text_body, html_body, user.email)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Candidate matched — notify employer by email
# ─────────────────────────────────────────────────────────────────────────────

def send_candidate_matched_email(employer_user, candidate_name, position):
    """Notify an employer by email that a new candidate has been matched."""
    name = employer_user.first_name or employer_user.username
    candidates_url = f"{SITE_URL}/dashboard/employer/candidates/"
    subject = f"New candidate matched to your {position} request — Target JobSpace"
    content_html = f"""
    <h2 style="margin:0 0 12px;font-size:20px;font-weight:800">A new candidate is ready for you 🎯</h2>
    <p>Hi {name},</p>
    <p>
      <strong>{candidate_name}</strong> has been matched to your
      <strong>{position}</strong> recruitment request by the Target JobSpace team.
    </p>
    <p>Log in to your dashboard to review their profile, shortlist them, or accept them.</p>"""
    text_body = (
        f"Hi {name},\n\n"
        f"{candidate_name} has been matched to your {position} request.\n"
        f"Log in to review: {candidates_url}\n"
    )
    html_body = _wrap_html(subject, content_html, "Review candidate", candidates_url)
    _send(subject, text_body, html_body, employer_user.email)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Employer accepted candidate — notify candidate
# ─────────────────────────────────────────────────────────────────────────────

def send_candidate_accepted_email(candidate_user, employer_name, position):
    """Notify a candidate that an employer has accepted their profile."""
    name = candidate_user.first_name or candidate_user.username
    dashboard_url = f"{SITE_URL}/dashboard/candidate/"
    subject = f"Great news — {employer_name} has accepted your profile!"
    content_html = f"""
    <h2 style="margin:0 0 12px;font-size:20px;font-weight:800">You have been accepted! 🎉</h2>
    <p>Hi {name},</p>
    <p>
      <strong>{employer_name}</strong> has reviewed your profile and formally accepted you
      for their <strong>{position}</strong> opening.
    </p>
    <p style="padding:16px;background:#f0fdf4;border-left:4px solid #10b981;border-radius:0 8px 8px 0;font-size:14px">
      <strong>What happens next?</strong> The Target JobSpace team will be in touch shortly
      to coordinate the next steps between you and the employer. Please keep an eye on your
      email and your dashboard notifications.
    </p>
    <p>In the meantime, log in to your dashboard to see the full status of your profile.</p>"""
    text_body = (
        f"Hi {name},\n\n"
        f"{employer_name} has accepted your profile for the {position} role.\n\n"
        "What happens next: The Target JobSpace team will contact you to coordinate "
        "next steps. Please monitor your email and dashboard notifications.\n\n"
        f"Dashboard: {dashboard_url}\n"
    )
    html_body = _wrap_html(subject, content_html, "Go to my dashboard", dashboard_url)
    _send(subject, text_body, html_body, candidate_user.email)
