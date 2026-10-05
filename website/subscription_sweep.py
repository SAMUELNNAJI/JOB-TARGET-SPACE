"""Subscription lifecycle sweeps — one implementation, two entry points.

  * ``views._sweep_subscriptions`` — lazy, runs on the first employer page
    view after a deadline passes. Works with no cron at all, matching the
    rest of this codebase's "no cron needed" approach.
  * ``manage.py send_subscription_reminders`` — a daily cron, so the emails
    land on time even for employers who never log in. DEPLOY.md has the line.

Both call ``sweep_subscriptions()``, which runs two steps, each guarded by a
timestamp on the Subscription row so nothing is ever sent twice:

  1. renewal reminder — once, when 10 days or fewer remain;
  2. expiry — once, the moment the plan lapses: deactivates the row, creates
     the in-app notification and emails the employer.
"""

from datetime import timedelta

from django.utils import timezone

from .emails import send_subscription_expiring_email, send_subscription_expired_email
from .models import Notification

# How many days before `expires_at` the renewal warning goes out.
REMINDER_DAYS = 10


def remind_if_expiring(sub):
    """Send the renewal warning once, when REMINDER_DAYS or fewer remain.

    Returns True when this call was the one that sent it.
    """
    now = timezone.now()
    if (
        not sub.is_active
        or sub.renewal_reminder_sent_at is not None
        or sub.expires_at is None
        or not (now < sub.expires_at <= now + timedelta(days=REMINDER_DAYS))
    ):
        return False
    # Mark BEFORE sending: a crashed send must not re-send on every later
    # sweep — a missed email is better than the same email every page view.
    sub.renewal_reminder_sent_at = now
    sub.save(update_fields=["renewal_reminder_sent_at"])
    send_subscription_expiring_email(sub)
    return True


def expire_if_due(sub):
    """Deactivate, notify in-app and email a lapsed plan — once.

    Returns True when this call was the one that fired it.
    """
    now = timezone.now()
    if (
        not sub.is_active
        or sub.expiry_notified_at is not None
        or sub.expires_at is None
        or sub.expires_at > now
    ):
        return False
    sub.is_active = False
    sub.expiry_notified_at = now
    sub.save(update_fields=["is_active", "expiry_notified_at"])
    employer = sub.employer
    employer.notify(
        title="Your subscription plan has expired",
        message=(
            f"Your {sub.get_plan_display()} plan expired on "
            f"{sub.expires_at.strftime('%d %b %Y')}. You can no longer submit "
            "recruitment requests until you renew or upgrade your plan. "
            "Visit the Subscription page to choose a plan and upload your payment proof."
        ),
        kind=Notification.Kind.PAYMENT,
    )
    send_subscription_expired_email(sub)
    return True


def sweep_subscriptions(queryset):
    """Run both steps over a queryset of ACTIVE subscriptions.

    Returns ``(reminded, expired)`` — how many of each email went out.
    """
    reminded = expired = 0
    for sub in queryset.select_related("employer__user"):
        if sub.expires_at is not None and sub.expires_at <= timezone.now():
            expired += bool(expire_if_due(sub))
        else:
            reminded += bool(remind_if_expiring(sub))
    return reminded, expired
