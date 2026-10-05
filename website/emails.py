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
from django.utils import timezone

logger = logging.getLogger(__name__)

SITE_NAME = "Target JobSpace"
SITE_URL  = "https://targetjobspace.com"


def _send(subject, text_body, html_body, to_email):
    """Low-level wrapper — never raises, always logs failures."""
    if not to_email:
        logger.warning("Email skipped, no recipient — %s", subject)
        return
    try:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", f"{SITE_NAME} <noreply@targetjobspace.com>")
        msg = EmailMultiAlternatives(subject, text_body, from_email, [to_email])
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
    except Exception as exc:
        logger.error("Email failed to %s — %s: %s", to_email, type(exc).__name__, exc)


def _wrap_html(title, content_html, cta_text=None, cta_url=None, preheader=None):
    """Wrap content in the branded HTML email shell every message uses.

    Table-based layout (the only thing Gmail, Outlook and Apple Mail all
    render reliably), a hidden preheader so inbox previews show a useful
    sentence instead of the raw HTML, a red accent bar, the dark brand
    header, and a footer carrying the real-world contact details a
    corporate email should always have.
    """
    preheader = preheader or title
    cta_block = ""
    if cta_text and cta_url:
        cta_block = f"""
        <tr><td align="center" style="padding:26px 36px 2px">
          <a href="{cta_url}"
             style="display:inline-block;padding:15px 34px;background:linear-gradient(135deg,#d6001d,#9b0015);
                    color:#ffffff;text-decoration:none;border-radius:999px;
                    font:700 15px/1 'Helvetica Neue',Arial,sans-serif">
            {cta_text} &rarr;
          </a>
        </td></tr>"""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="x-apple-disable-message-reformatting">
  <meta name="format-detection" content="telephone=no,date=no,address=no,email=no">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#eef1f7;font-family:-apple-system,'Segoe UI','Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased">
  <!-- Hidden preheader: the sentence the inbox shows next to the subject -->
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:transparent">{preheader}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#eef1f7;padding:28px 12px">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid #e4e9f4;border-radius:16px;overflow:hidden">
        <!-- Accent bar -->
        <tr><td style="height:4px;background:linear-gradient(90deg,#d6001d,#ff4d6d);font-size:1px;line-height:1px">&nbsp;</td></tr>
        <!-- Brand header -->
        <tr><td style="background:#0a0c10;padding:22px 36px">
          <a href="{SITE_URL}" style="text-decoration:none">
            <span style="font:800 21px/1 'Helvetica Neue',Arial,sans-serif;color:#ffffff;letter-spacing:-.4px">Target&nbsp;<span style="color:#ff4d6d">JobSpace</span></span>
          </a>
        </td></tr>
        <!-- Body -->
        <tr><td style="padding:34px 36px 4px;color:#1f2937;font-size:15px;line-height:1.7;font-family:-apple-system,'Segoe UI','Helvetica Neue',Arial,sans-serif">
          {content_html}
        </td></tr>
        {cta_block}
        <!-- Spacer so the footer rule never hugs the CTA -->
        <tr><td style="height:24px;font-size:1px;line-height:1px">&nbsp;</td></tr>
        <!-- Footer -->
        <tr><td style="background:#f8fafc;border-top:1px solid #eef1f6;padding:22px 36px 28px">
          <p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#374151">Target JobSpace</p>
          <p style="margin:0 0 4px;font-size:12px;color:#8a93a6;line-height:1.7">
            Bayo Dejonwo Street, Maryland, Lagos, Nigeria<br>
            <a href="mailto:info@targetjobspace.com" style="color:#d6001d;text-decoration:none">info@targetjobspace.com</a>
            &nbsp;&middot;&nbsp;
            <a href="https://wa.me/2349136185082" style="color:#d6001d;text-decoration:none">+234 913 618 5082</a>
          </p>
          <p style="margin:14px 0 0;font-size:11px;color:#a5adbf;line-height:1.7">
            You received this email because you have an account on
            <a href="{SITE_URL}" style="color:#8a93a6;text-decoration:underline">targetjobspace.com</a>.
            &nbsp;&middot;&nbsp; <a href="{SITE_URL}/privacy/" style="color:#8a93a6;text-decoration:underline">Privacy Policy</a>
            &nbsp;&middot;&nbsp; <a href="{SITE_URL}/terms/" style="color:#8a93a6;text-decoration:underline">Terms of Service</a>
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


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


# ─────────────────────────────────────────────────────────────────────────────
# 6. Subscription approved — admin verified the payment proof
# ─────────────────────────────────────────────────────────────────────────────

def send_subscription_approved_email(user, plan_label, amount, expires_at, reference=""):
    """Confirm to an employer that their payment was approved and plan is live.

    Called from views.admin_payment_action the moment staff approve a proof.
    """
    name = user.first_name or user.username
    sub_url = f"{SITE_URL}/dashboard/employer/subscription/"
    expires_str = expires_at.strftime("%d %b %Y")
    subject = f"Payment approved — your {plan_label} plan is now active"
    ref_row = ""
    if reference:
        ref_row = (
            '<tr><td style="padding:12px 18px;color:#6b7280;border-bottom:1px solid #eef1f6">Payment reference</td>'
            '<td style="padding:12px 18px;font-weight:700;color:#111827;border-bottom:1px solid #eef1f6;text-align:right">'
            f"{reference}</td></tr>"
        )
    content_html = f"""
    <h2 style="margin:0 0 14px;font-size:22px;font-weight:800;color:#111827">You're all set, {name}! 🎉</h2>
    <p style="margin:0 0 18px">Your payment has been reviewed and approved by our team.
    Your <strong>{plan_label}</strong> subscription is now live — you can post recruitment
    requests and receive matched candidates right away.</p>
    <table style="width:100%;border-collapse:collapse;background:#f8fafc;border:1px solid #e4e9f4;border-radius:12px;font-size:14px">
      <tr><td style="padding:12px 18px;color:#6b7280;border-bottom:1px solid #eef1f6">Plan activated</td>
          <td style="padding:12px 18px;font-weight:700;color:#111827;border-bottom:1px solid #eef1f6;text-align:right">{plan_label}</td></tr>
      <tr><td style="padding:12px 18px;color:#6b7280;border-bottom:1px solid #eef1f6">Amount verified</td>
          <td style="padding:12px 18px;font-weight:700;color:#111827;border-bottom:1px solid #eef1f6;text-align:right">₦{amount:,}</td></tr>
      {ref_row}
      <tr><td style="padding:12px 18px;color:#6b7280">Active until</td>
          <td style="padding:12px 18px;font-weight:700;color:#d6001d;text-align:right">{expires_str}</td></tr>
    </table>
    <p style="margin:18px 0 0;color:#6b7280;font-size:13.5px">
      Questions about your plan or invoice? Reply to this email or message us on
      WhatsApp — a real person will help.</p>"""
    text_body = (
        f"Hi {name},\n\n"
        "Your payment has been approved and your subscription is now active.\n\n"
        f"Plan: {plan_label}\n"
        f"Amount verified: ₦{amount:,}\n"
        + (f"Reference: {reference}\n" if reference else "")
        + f"Active until: {expires_str}\n\n"
        f"Subscription page: {sub_url}\n"
    )
    html_body = _wrap_html(
        subject, content_html, "Go to my subscription", sub_url,
        preheader=f"Your {plan_label} plan is active until {expires_str}.",
    )
    _send(subject, text_body, html_body, user.email)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Renewal reminder — 10 days before the plan expires
# ─────────────────────────────────────────────────────────────────────────────

def send_subscription_expiring_email(subscription):
    """Warn the employer once, with 10 days or fewer left on the plan.

    Sent by website.subscription_sweep — never directly from a view.
    """
    sub = subscription
    user = sub.employer.user
    name = user.first_name or user.username
    plan = sub.get_plan_display()
    renew_url = f"{SITE_URL}/dashboard/employer/subscription/"
    expires_str = sub.expires_at.strftime("%d %B %Y")
    days = max((sub.expires_at.date() - timezone.now().date()).days, 0)
    day_word = "day" if days == 1 else "days"
    subject = f"Your {plan} plan expires in {days} {day_word} — renew to stay matched"
    content_html = f"""
    <h2 style="margin:0 0 14px;font-size:22px;font-weight:800;color:#111827">Your plan is expiring soon ⏳</h2>
    <p style="margin:0 0 18px">Hi {name},</p>
    <p style="margin:0 0 18px">
      Your <strong>{plan}</strong> subscription expires on
      <strong>{expires_str}</strong> — in <strong>{days} {day_word}</strong>.
      Renew before then to keep your recruitment requests running and your
      matched candidates flowing without a break.</p>
    <p style="margin:0 0 6px;padding:16px 18px;background:#fff8f8;border-left:4px solid #d6001d;border-radius:0 8px 8px 0;font-size:14px">
      <strong>What happens if it lapses:</strong> you won't be able to submit new
      recruitment requests or receive candidate matches until you renew.</p>
    <p style="margin:16px 0 0;color:#6b7280;font-size:13.5px">
      Renewing takes about two minutes — choose your plan, transfer, and upload
      your proof; our team verifies it the same day.</p>"""
    text_body = (
        f"Hi {name},\n\n"
        f"Your {plan} subscription expires on {expires_str} — in {days} {day_word}.\n\n"
        "Renew to keep your recruitment requests running without a break. "
        "After expiry you cannot submit new requests or receive candidate "
        "matches until you renew.\n\n"
        f"Renew here: {renew_url}\n"
    )
    html_body = _wrap_html(
        subject, content_html, "Renew my plan", renew_url,
        preheader=f"Your {plan} plan expires {expires_str} — {days} {day_word} left.",
    )
    _send(subject, text_body, html_body, user.email)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Expired — the plan has lapsed and access is off
# ─────────────────────────────────────────────────────────────────────────────

def send_subscription_expired_email(subscription):
    """Tell the employer the plan has expired (sent once, alongside the in-app
    notification created by website.subscription_sweep)."""
    sub = subscription
    user = sub.employer.user
    name = user.first_name or user.username
    plan = sub.get_plan_display()
    renew_url = f"{SITE_URL}/dashboard/employer/subscription/"
    expires_str = sub.expires_at.strftime("%d %B %Y")
    subject = f"Your {plan} subscription has expired"
    content_html = f"""
    <h2 style="margin:0 0 14px;font-size:22px;font-weight:800;color:#111827">Your subscription has expired</h2>
    <p style="margin:0 0 18px">Hi {name},</p>
    <p style="margin:0 0 18px">
      Your <strong>{plan}</strong> plan expired on <strong>{expires_str}</strong>.
      Your account, profiles and history are all still here — but you can no
      longer submit recruitment requests or receive matched candidates.</p>
    <p style="margin:0 0 6px;padding:16px 18px;background:#fff8f8;border-left:4px solid #d6001d;border-radius:0 8px 8px 0;font-size:14px">
      <strong>Renew in minutes:</strong> choose a plan, transfer, and upload your
      payment proof. Our team verifies it the same day and your access resumes
      straight away.</p>
    <p style="margin:16px 0 0;color:#6b7280;font-size:13.5px">
      Questions? Reply to this email or contact us on WhatsApp — we're happy to help.</p>"""
    text_body = (
        f"Hi {name},\n\n"
        f"Your {plan} subscription expired on {expires_str}.\n\n"
        "Your account and history are still here, but you cannot submit "
        "recruitment requests or receive matched candidates until you renew.\n\n"
        f"Renew here: {renew_url}\n"
    )
    html_body = _wrap_html(
        subject, content_html, "Renew your plan", renew_url,
        preheader=f"Your {plan} plan expired {expires_str}. Renew to restore access.",
    )
    _send(subject, text_body, html_body, user.email)
