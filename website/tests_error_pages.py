"""Tests for the custom error pages.

The 500 case is the one that matters. It is tested against a database that is
genuinely unreachable, because that is the real scenario: if the handler needs
a context processor (any of them touch the request, and one queries the
database), a database outage produces a second exception and the user gets
Django's bare "Server Error (500)" instead of the designed page.

Run with:  python manage.py test website.tests_error_pages
"""

import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError, connection
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

ANIMATION_MARKERS = ("@keyframes", "animation:")


class ErrorPageTests(TestCase):
    def assert_is_animated(self, html):
        for marker in ANIMATION_MARKERS:
            self.assertIn(marker, html, f"animation marker {marker!r} missing")

    def assert_respects_reduced_motion(self, html):
        """A looping animation is genuinely unpleasant for some people with
        vestibular disorders, so prefers-reduced-motion must switch it off."""
        self.assertIn("prefers-reduced-motion", html)

    # ── 404 ────────────────────────────────────────────────────────────────

    def test_unknown_url_renders_the_404_page(self):
        response = self.client.get("/definitely-not-a-page/")
        self.assertEqual(response.status_code, 404)
        html = response.content.decode()
        self.assertIn("find that page", html)
        self.assert_is_animated(html)
        self.assert_respects_reduced_motion(html)

    def test_404_is_noindex(self):
        """Indexing dead ends wastes crawl budget and can displace the page the
        visitor was actually trying to reach."""
        html = self.client.get("/definitely-not-a-page/").content.decode()
        self.assertIn('content="noindex', html)

    def test_404_offers_a_way_out(self):
        html = self.client.get("/definitely-not-a-page/").content.decode()
        self.assertIn('href="/"', html)

    # ── 403 ────────────────────────────────────────────────────────────────

    def test_another_users_document_returns_the_403_page(self):
        """The protected-download views raise PermissionDenied; the user should
        see a designed 'not for you', not a stack-trace-looking page."""
        from .models import CandidateDocument, Profile

        owner = User.objects.create_user(
            username="owner", email="o@example.com", password="pw-C0rrect!"
        )
        Profile.objects.create(user=owner, role=Profile.Role.CANDIDATE)
        document = CandidateDocument.objects.create(
            profile=owner.profile,
            file=SimpleUploadedFile("cv.pdf", b"%PDF-1.4", content_type="application/pdf"),
        )

        intruder = User.objects.create_user(
            username="intruder", email="i@example.com", password="pw-C0rrect!"
        )
        Profile.objects.create(user=intruder, role=Profile.Role.CANDIDATE)
        self.client.force_login(intruder)

        response = self.client.get(
            reverse("website:candidate_document_download", args=[document.id])
        )
        self.assertEqual(response.status_code, 403)
        html = response.content.decode()
        self.assertIn("available to you", html)
        self.assert_is_animated(html)

    def test_403_is_noindex(self):
        """A signed-in user reaching someone else's file gets the designed 403.

        Two ordering details matter here, and both are correct behaviour:

          * an ANONYMOUS request gets a 302 to /signin/, not a 403 — the view is
            @login_required, so the session check runs before the ownership
            check;
          * a REAL document belonging to someone else is a 403, not a 404. The
            view fetches the document first and only then checks ownership, so
            requesting a document that does not exist yields 404. This test
            therefore creates a real document owned by another user.
        """
        from .models import CandidateDocument, Profile

        owner = User.objects.create_user(
            username="owner2", email="o2@example.com", password="pw-C0rrect!"
        )
        Profile.objects.create(user=owner, role=Profile.Role.CANDIDATE)
        document = CandidateDocument.objects.create(
            profile=owner.profile,
            file=SimpleUploadedFile("cv.pdf", b"%PDF", content_type="application/pdf"),
        )

        viewer = User.objects.create_user(
            username="viewer", email="v@example.com", password="pw-C0rrect!"
        )
        Profile.objects.create(user=viewer, role=Profile.Role.CANDIDATE)
        self.client.force_login(viewer)

        response = self.client.get(
            reverse("website:candidate_document_download", args=[document.id])
        )
        self.assertEqual(response.status_code, 403)
        html = response.content.decode()
        self.assertIn('content="noindex', html)

    # ── 500, against a genuinely broken database ───────────────────────────

    def test_500_renders_even_when_the_database_is_unreachable(self):
        """The test that justifies the design of error_views.

        This reproduces the real outage: the database goes away, the view fails,
        and the error handler then has to render a page while the database is
        still down. If the handler used django.shortcuts.render() it would build
        a RequestContext, run the badge context processor (which queries), and
        raise a SECOND exception — leaving the user with Django's bare
        "Server Error (500)" instead of the designed page.

        Two details make this work:
          * raise_request_exception=False, because the test client otherwise
            re-raises so failures surface.
          * monkeypatching connect(). Calling connection.close() is NOT enough:
            Django transparently reconnects on the next query, so the "outage"
            would silently heal and the test would prove nothing.
        """
        from unittest import mock

        from .models import Profile

        client = self.client_class(raise_request_exception=False)

        # Log in first. An anonymous request to /dashboard/ is redirected to
        # /signin/ by @login_required and never reaches a database query, so it
        # would return 302 and prove nothing about the outage.
        user = User.objects.create_user(
            username="outage", email="o@example.com", password="pw-C0rrect!"
        )
        Profile.objects.create(user=user, role=Profile.Role.CANDIDATE)
        client.force_login(user)

        def refuse(*args, **kwargs):
            raise OperationalError("connection to server failed")

        # Patch ensure_connection, not connect(). Two reasons:
        #   * Django caches the open connection, so on SQLite — which is what
        #     the test suite runs on — a query may never call connect() at all;
        #   * ensure_connection is the single choke point every query passes
        #     through, so this is guaranteed to take effect regardless of
        #     backend or whether a connection is already open.
        with mock.patch(
            "django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
            refuse,
        ):
            # Prove the database really is unusable in this thread before
            # asserting anything, so a passing test cannot be a false one.
            with self.assertRaises(OperationalError):
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")

            response = client.get("/dashboard/candidate/")

        self.assertEqual(response.status_code, 500)
        html = response.content.decode()
        self.assertIn("Something went wrong", html)
        self.assert_is_animated(html)
        self.assert_respects_reduced_motion(html)

    def test_500_handler_needs_no_database(self):
        """The handler itself, called directly with no request and no context.

        This is the unit-level guarantee behind the integration test above: the
        page renders from the template alone.
        """
        from jobspace.error_views import server_error

        with connection.cursor() as cursor:  # sanity: DB works at this point
            cursor.execute("SELECT 1")

        response = server_error(request=None)
        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong", response.content.decode())

    def _read_500_template(self):
        """The 500 template with all comments stripped.

        The `{% comment %}` block at the top of the file deliberately quotes
        `{% static %}`, `{{ request }}` and `{% extends %}` to explain why they
        must not appear. Checking the raw text would match those explanations
        and fail for the wrong reason, so comments are removed first and only
        the executable part is inspected.
        """
        path = Path(__file__).resolve().parent.parent / "templates" / "500.html"
        text = path.read_text(encoding="utf-8")
        # {% comment %} ... {% endcomment %}
        text = re.sub(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", "", text, flags=re.S)
        # {# ... #}
        text = re.sub(r"\{#.*?#\}", "", text, flags=re.S)
        # CSS and HTML comments, so explanatory prose cannot trip the check.
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        return text

    def test_500_template_uses_no_static_tag(self):
        """{% static %} can hit the storage layer, which may be what is broken.
        A 500 page that depends on it is a 500 page that cannot render."""
        text = self._read_500_template()
        self.assertNotIn("{% static", text)
        self.assertNotIn("{% load", text)
        self.assertNotIn("{% extends", text)

    def test_500_template_uses_no_request_context(self):
        """`{{ request.x }}` would be empty here anyway, because the handler
        passes no request. Asserting the template stays that way prevents a
        future edit quietly reintroducing the dependency."""
        text = self._read_500_template()
        self.assertNotIn("{{ request", text)
        self.assertNotIn("{{ user", text)
        self.assertNotIn("{{ seo", text)

    def test_500_template_has_no_external_asset_references(self):
        """No <img>, <link> or @import. A 500 page that waits on a stylesheet
        or an image from a CDN renders blank exactly when it is needed most."""
        text = self._read_500_template()
        for tag in ("<img", "<link", "@import", "http://", "https://"):
            with self.subTest(tag=tag):
                self.assertNotIn(tag, text)

    # ── no page should leak internals ──────────────────────────────────────

    def test_error_pages_do_not_leak_tracebacks(self):
        for path in ("/definitely-not-a-page/", "/documents/999999/download/"):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode().lower()
                for leak in ("traceback", "django.db", "site-packages",
                             "exception class", "request.method"):
                    self.assertNotIn(leak, html)
