"""sitemap.xml and robots.txt.

Both are generated rather than static files because the site name appears in
them, and a static robots.txt is the classic place to leak a staging hostname
or a private path. Generating them keeps one source of truth.

The sitemap lists ONLY the public marketing pages. No dashboard, admin or
download URL appears — listing them would invite a crawler into the private
per-user pages, which the `noindex` tag alone does not reliably prevent.
"""

from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .seo import PAGE_SLUGS, PAGE_SEO


def _abs(request, path):
    return request.build_absolute_uri(path)


@never_cache
def sitemap(request):
    """XML sitemap of the public pages.

    @never_cache is deliberate: a crawler must see the current list, and a
    cached sitemap is the usual reason new pages stay undiscovered.
    """
    base = _abs(request, "/")
    lastmod = timezone.now().date().isoformat()

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for key, meta in PAGE_SEO.items():
        path = "/" if key == "home" else f"/{PAGE_SLUGS[key]}/"
        lines += [
            "  <url>",
            f"    <loc>{base.rstrip('/')}{path}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            f"    <changefreq>{meta['changefreq']}</changefreq>",
            f"    <priority>{meta['priority']}</priority>",
            "  </url>",
        ]
    lines.append("</urlset>")

    return HttpResponse(
        "\n".join(lines), content_type="application/xml; charset=utf-8"
    )


@never_cache
def robots_txt(request):
    """robots.txt.

    The Disallow rules are a crawl-budget guard, not the privacy control —
    `noindex` on the pages themselves is what actually keeps private pages out
    of results, because a disallowed URL can still be indexed from an external
    link. Both are needed.
    """
    base = _abs(request, "/").rstrip("/")
    lines = [
        "User-agent: *",
        "",
        "# Private, per-user areas. These must never appear in search results.",
        "Disallow: /dashboard/",
        "Disallow: /admin/",
        "Disallow: /signin/",
        "Disallow: /signup/",
        "Disallow: /logout/",
        "Disallow: /documents/",
        "Disallow: /payments/",
        "",
        "Allow: /static/",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
