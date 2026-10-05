"""Tests for the subscription lifecycle emails: admin approval, the 10-day
renewal warning, and the expiry notice — plus the premium shell every email
is wrapped in.

The important properties are not cosmetic. Time-based emails are guarded by
timestamp markers on the Subscription row, so these tests pin down the exact
invariant: a lifecycle email can only ever go out ONCE per subscription,
no matter how many times the sweep or the cron command runs.

Run with:  python manage.py test website.tests_subscription_emails
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .emails import _wrap_html, send_subscription_approved_email, SITE_URL
from .models import Payment, Profile, Subscription
from .subscription_sweep import REMINDER_DAYS, expire_if_due, remind_if_expiring

User = get_user_model()

LOC_MEM = {"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}


def make_employer(username, email):
    user = User.objects.create_user(
        username=username, email=email, password="pw-C0rrect!"
    )
    profile = Profile.objects.create(user=user, role=Profile.Role.EMPLOYER)
    return user, profile


def make_subscription(profile, days_from_now, active=True, plan="basic", amount=50000):
    now = timezone.now()
    return Subscription.objects.create(
        employer=profile, plan=plan, amount=amount,
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=days_from_now),
        is_active=active,
    )


@override_settings(**LOC_MEM)
class EmailShellTests(TestCase):
    def test_shell_is_a_complete_branded_document(self):
        """The wrapper must look like a corporate email, not a plain dump."""
        html = _wrap_html(
            "Subject line", "<p>Hello</p>", "Do the thing", "https://example.com/x"
        )
        for needle in (
            "<!doctype html>", "display:none", "Target", "JobSpace",
            "Do the thing", "https://example.com/x", "#eef1f7",
            "Bayo Dejonwo Street", "wa.me/2349136185082", "Privacy Policy",
            "Terms of Service", SITE_URL,
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, html)

    def test_preheader_defaults_to_title(self):
        """With no explicit preheader, inbox previews show the subject."""
        html = _wrap_html("My subject", "<p>Body</p>")
        self.assertIn("My subject", html)


@override_settings(**LOC_MEM)
class ApprovedEmailTests(TestCase):
    def test_approval_email_carries_plan_amount_and_expiry(self):
        user, _ = make_employer("emp", "emp@example.com")
        expires = timezone.now() + timedelta(days=30)
        send_subscription_approved_email(user, "Basic", 50000, expires, "REF-9")
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ["emp@example.com"])
        self.assertIn("Payment approved", msg.subject)
        self.assertIn("Basic", msg.body)
        self.assertIn("REF-9", msg.body)
        html = msg.alternatives[0][0]
        self.assertIn("50,000", html)
        self.assertIn(expires.strftime("%d %b %Y"), html)
        self.assertIn("Go to my subscription", html)

    def test_admin_approval_view_sends_the_email(self):
        """End to end: staff approves proof -> employer gets one email."""
        staff = User.objects.create_user(
            "boss", "boss@example.com", "pw-C0rrect!", is_staff=True
        )
        _, profile = make_employer("emp", "emp@example.com")
        sub = make_subscription(profile, days_from_now=30, active=False)
        payment = Payment.objects.create(
            employer=profile, subscription=sub, reference="REF-77",
            amount=50000,
        )
        self.client.force_login(staff)
        response = self.client.post(
            f"/dashboard/admin/payments/{payment.pk}/action/",
            {"action": "approve", "verified_amount": "50000",
             "final_plan": "basic", "admin_notes": ""},
        )
        self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Payment approved", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["emp@example.com"])


@override_settings(**LOC_MEM)
class ReminderSweepTests(TestCase):
    def setUp(self):
        _, self.profile = make_employer("emp", "emp@example.com")

    def test_reminder_fires_at_ten_days_and_only_once(self):
        sub = make_subscription(self.profile, days_from_now=REMINDER_DAYS)
        self.assertTrue(remind_if_expiring(sub))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("expires in", mail.outbox[0].subject)

        # Second sweep (or the daily cron) must not re-send.
        sub.refresh_from_db()
        self.assertIsNotNone(sub.renewal_reminder_sent_at)
        self.assertFalse(remind_if_expiring(sub))
        self.assertEqual(len(mail.outbox), 1)

    def test_no_reminder_outside_the_window(self):
        sub = make_subscription(self.profile, days_from_now=30)
        self.assertFalse(remind_if_expiring(sub))
        self.assertEqual(len(mail.outbox), 0)

    def test_reminder_inside_window_sends_even_when_not_exact(self):
        """An employer logging in with 4 days left still gets warned once."""
        sub = make_subscription(self.profile, days_from_now=4)
        self.assertTrue(remind_if_expiring(sub))
        self.assertEqual(len(mail.outbox), 1)


@override_settings(**LOC_MEM)
class ExpireSweepTests(TestCase):
    def setUp(self):
        _, self.profile = make_employer("emp", "emp@example.com")

    def test_expiry_deactivates_notifies_and_emails_exactly_once(self):
        sub = make_subscription(self.profile, days_from_now=-1)
        self.assertTrue(expire_if_due(sub))

        sub.refresh_from_db()
        self.assertFalse(sub.is_active)
        self.assertIsNotNone(sub.expiry_notified_at)
        self.assertEqual(self.profile.notifications.count(), 1)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("expired", mail.outbox[0].subject.lower())

        # A later sweep must do nothing — no second email, no second row.
        self.assertFalse(expire_if_due(sub))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.profile.notifications.count(), 1)

    def test_live_plan_is_left_alone(self):
        sub = make_subscription(self.profile, days_from_now=30)
        self.assertFalse(expire_if_due(sub))
        self.assertEqual(len(mail.outbox), 0)
        sub.refresh_from_db()
        self.assertTrue(sub.is_active)


@override_settings(**LOC_MEM)
class CommandTests(TestCase):
    def test_command_sends_both_and_dedupes_on_rerun(self):
        from django.core.management import call_command
        from .subscription_sweep import sweep_subscriptions

        _, soon = make_employer("soon", "soon@example.com")
        _, lapsed = make_employer("lapsed", "lapsed@example.com")
        _, far = make_employer("far", "far@example.com")
        make_subscription(soon, days_from_now=REMINDER_DAYS)
        make_subscription(lapsed, days_from_now=-1)
        make_subscription(far, days_from_now=40)

        call_command("send_subscription_reminders", verbosity=0)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIsNotNone(soon.subscriptions.get().renewal_reminder_sent_at)
        self.assertFalse(lapsed.subscriptions.get().is_active)

        # Running "tomorrow" sends nothing new.
        call_command("send_subscription_reminders", verbosity=0)
        self.assertEqual(len(mail.outbox), 2)

    def test_sweep_queryset_helper_counts(self):
        from .subscription_sweep import sweep_subscriptions

        _, profile = make_employer("emp", "emp@example.com")
        make_subscription(profile, days_from_now=5)
        reminded, expired = sweep_subscriptions(
            Subscription.objects.filter(is_active=True)
        )
        self.assertEqual((reminded, expired), (1, 0))