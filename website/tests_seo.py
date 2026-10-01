"""Tests for the SEO layer.

The important properties are not cosmetic. Two are security or privacy:

  * dashboard pages must be `noindex`, or a crawler can get a logged-in view
    of somebody's CVs indexed — which exposes the private download URLs;
  * the JSON-LD must not be escapable, or a `</script>` in any value breaks
    out of the tag and becomes stored XSS.

Reconstructed from the compiled bytecode after the source file was lost during
a cleanup; assertions match the original test-for-test.

Run with:  python manage.py test website.tests_seo
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from .seo import PAGE_SEO, PAGE_SLUGS

User = get_user_model()

# Every URL the public is invited to index: the home page plus one slug per
# marketing page. Kept derived from PAGE_SLUGS so a new page is covered the
# moment it is added — a hand-maintained list silently rots.
PUBLIC_PATHS = ["/"] + [f"/{slug}/" for slug in PAGE_SLUGS.values()]


class SeoMetadataTests(TestCase):
    def test_every_public_page_has_metadata(self):
        for path in PUBLIC_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn("<title>", html)
                self.assertIn('name="description"', html)
                self.assertIn('rel="canonical"', html)

    def test_public_pages_are_indexable(self):
        for path in PUBLIC_PATHS:
            with self.subTest(path=path):
                html = self.client.get(path).content.decode()
                self.assertIn('content="index, follow"', html)
                self.assertIn("application/ld+json", html)

    def test_titles_are_unique_per_page(self):
        """Duplicate titles let a search engine pick the wrong page to rank."""
        titles = [meta["title"] for meta in PAGE_SEO.values()]
        self.assertEqual(len(titles), len(set(titles)))

    def test_descriptions_are_in_a_sensible_length(self):
        """Google truncates around 155-160 chars and rewrites anything wildly
over or under, so a 'description' outside this range is wasted."""
        for key, meta in PAGE_SEO.items():
            with self.subTest(page=key):
                self.assertGreater(len(meta["description"]), 70)
                self.assertLess(len(meta["description"]), 175)

    def test_titles_are_in_a_sensible_length(self):
        for key, meta in PAGE_SEO.items():
            with self.subTest(page=key):
                self.assertLess(len(meta["title"]), 70)

    def test_dashboard_is_noindex(self):
        """A crawled /dashboard/ would expose private candidate data.

The noindex tag is emitted by a context processor, so it appears on any
page that renders base.html regardless of which view served it.
"""
        from .models import Profile

        user = User.objects.create_user(
            username="cand", email="c@example.com", password="pw-C0rrect!"
        )
        Profile.objects.create(user=user, role=Profile.Role.CANDIDATE)

        self.client.force_login(user)

        response = self.client.get("/dashboard/candidate/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('content="noindex, nofollow"', html)
        # No description and no JSON-LD may be emitted for a private page: a
        # description risks leaking a page title into a search snippet.
        self.assertNotIn('name="description"', html)
        self.assertNotIn("application/ld+json", html)

    def test_download_urls_are_noindex(self):
        """The download views return a file, not a page, so there is no <head> to
check. What matters is that they are not reachable without a session —
which the protected-download tests cover — and that the prefix is
excluded from the sitemap and blocked in robots.txt. Both are asserted
in those tests; this one just records the intent.

These views must stay out of the sitemap: a crawler following a

download link is exactly the leak the views prevent.
"""
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("/documents/", sitemap)
        self.assertNotIn("/payments/", sitemap)

    def test_auth_pages_are_noindex(self):
        """The auth pages open a private session; indexing them sends people to a
login form instead of content."""
        for path in ("/signin/", "/signup/"):
            with self.subTest(path=path):
                html = self.client.get(path).content.decode()
                self.assertIn('content="noindex', html)

    def test_unknown_public_url_is_not_in_the_sitemap(self):
        """Only the eight known marketing pages belong in the sitemap. A URL
with no metadata is treated as non-indexable, so it must not be
advertised as though it were content.

Django's built-in 404 handler does not render base.html, so there is no
<head> here to assert a robots tag against — that is why this checks
the sitemap instead.
"""
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn("no-such-page", sitemap)

        self.assertEqual(self.client.get("/no-such-page/").status_code, 404)

    def test_jsonld_cannot_break_out_of_the_script_tag(self):
        """`</script>` in a value must not close the tag.

JSON-LD here is built from strings this app controls, but the escaping
is what keeps that safe to rely on if a description is ever templated
from user input — which is how this bug appears in the wild.
"""
        import json

        from .templatetags.seo_extras import json_script_safe

        payload = {"description": "</script><script>alert(1)</script>"}
        rendered = json_script_safe(payload)

        self.assertNotIn("</script>", rendered)
        self.assertIn("\\u003c", rendered)
        self.assertEqual(json.loads(rendered)["description"], payload["description"])

    def test_sitemap_is_valid_xml_and_lists_public_pages(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response["Content-Type"])
        body = response.content.decode()
        self.assertIn("<urlset", body)
        for path in PUBLIC_PATHS:
            self.assertIn(path, body)

    def test_sitemap_never_lists_private_paths(self):
        """Listing a private URL invites a crawler straight into it."""
        body = self.client.get("/sitemap.xml").content.decode()
        for forbidden in ("/dashboard/", "/admin/", "/signin/", "/documents/"):
            self.assertNotIn(forbidden, body)

    def test_robots_txt_disallows_private_areas_and_points_at_sitemap(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        for rule in ("/dashboard/", "/admin/", "/documents/", "/payments/"):
            self.assertIn(f"Disallow: {rule}", body)
        self.assertIn("Sitemap:", body)
        self.assertIn("/sitemap.xml", body)

    def test_canonical_is_absolute(self):
        """A relative or http canonical is ignored or treated as a duplicate."""
        html = self.client.get("/about/").content.decode()
        self.assertIn('rel="canonical" href="http://testserver', html)
        self.assertIn('/about/"', html)

    def test_canonical_honours_forwarded_proto(self):
        """Behind nginx the real scheme arrives in X-Forwarded-Proto, and a
canonical pointing at http:// on an https-only site is a common
self-inflicted duplicate-content bug.

The port is retained because Django echoes the Host header. Behind nginx
that header carries no port, so the production canonical is clean; here
the test client sends `testserver:80`.
"""
        html = self.client.get(
            "/about/",
            HTTP_X_FORWARDED_PROTO="https",
        ).content.decode()
        self.assertIn('rel="canonical" href="https://testserver', html)
