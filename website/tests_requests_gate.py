"""Tests for the employer subscription gate on the recruitment-requests page.

The bug these pin down: the template styled the locked state with
`emp-page-blurred` / `emp-sub-gate-overlay` while the stylesheet still
defined the OLD `.emp-sub-gate` selector. Dead CSS meant the modal was an
unstyled block after </main> — not centred in the viewport, and unreachable
because the gate script locks body scrolling. Template and stylesheet must
agree on the class names, and the overlay must be viewport-fixed.

Run with:  python manage.py test website.tests_requests_gate
"""

from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Profile, Subscription

User = get_user_model()

CSS_PATH = Path(__file__).resolve().parents[1] / "static" / "css" / "dashboard.css"
REQUESTS_URL = "/dashboard/employer/requests/"


def make_employer(username, email):
    user = User.objects.create_user(
        username=username, email=email, password="pw-C0rrect!"
    )
    profile = Profile.objects.create(user=user, role=Profile.Role.EMPLOYER)
    return user, profile


class SubscriptionGateRenderingTests(TestCase):
    def test_unsubscribed_employer_gets_the_gate_and_page_blur(self):
        user, _ = make_employer("noplan", "noplan@example.com")
        self.client.force_login(user)
        response = self.client.get(REQUESTS_URL)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('class="emp-sub-gate-overlay"', html)
        self.assertIn('id="empSubGate"', html)
        self.assertIn("emp-page-blurred", html)
        # The locked form keeps its inert guards.
        self.assertIn("emp-form-body", html)

    def test_subscribed_employer_sees_no_gate(self):
        user, profile = make_employer("hasplan", "hasplan@example.com")
        now = timezone.now()
        Subscription.objects.create(
            employer=profile, plan="basic", amount=50000,
            starts_at=now - timedelta(days=1),
            expires_at=now + timedelta(days=30),
            is_active=True,
        )
        self.client.force_login(user)
        response = self.client.get(REQUESTS_URL)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertNotIn("emp-sub-gate-overlay", html)
        self.assertNotIn("emp-page-blurred", html)


class SubscriptionGateCssTests(TestCase):
    """The stylesheet must style the classes the template actually renders."""

    @staticmethod
    def _rule(css, selector):
        """Return the declarations inside the first `selector { … }` block.

        Tolerates whitespace before the brace and selector mentions in
        comments: it jumps from the selector's first occurrence to the next
        `{`, then reads to the matching `}`.
        """
        try:
            after = css.split(selector, 1)[1]
            after = after[after.index("{") + 1:]
            return after.split("}", 1)[0]
        except (IndexError, ValueError):
            return ""

    def test_overlay_is_fixed_and_scrollable(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        overlay = self._rule(css, ".emp-sub-gate-overlay")
        self.assertIn("position: fixed", overlay)
        self.assertIn("inset: 0", overlay)
        self.assertIn("overflow-y: auto", overlay)
        # Must clear the dashboard chrome (sidebar/modals sit at ≤2000).
        self.assertIn("z-index: 9500", overlay)

    def test_card_centres_in_both_axes_and_stays_reachable(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        card = self._rule(css, ".emp-sub-gate-card")
        self.assertIn("margin: auto", card)
        self.assertIn("width: min(560px, 100%)", card)

    def test_page_blur_exists_and_form_lock_does_not_double_blur(self):
        css = CSS_PATH.read_text(encoding="utf-8")
        page = self._rule(css, ".emp-page-blurred")
        self.assertIn("filter: blur", page)
        # Guards only: stacking blur+opacity here would make the form region
        # double-dimmed compared with the rest of the page.
        locked = self._rule(css, ".emp-form-body.is-locked")
        self.assertNotIn("filter", locked)
        self.assertNotIn("opacity", locked)

    def test_dead_selector_was_removed(self):
        """`.emp-sub-gate` (the old, unused container) must not linger —
        seeing it again means template and CSS have drifted apart."""
        css = CSS_PATH.read_text(encoding="utf-8")
        self.assertNotIn(".emp-sub-gate {", css)
        self.assertNotIn('.emp-sub-gate[aria-hidden', css)
