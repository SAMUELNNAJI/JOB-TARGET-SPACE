"""Per-page SEO metadata for the public pages.

Only the marketing pages are indexable. Every dashboard page holds private
per-user data and must carry `noindex`, otherwise a crawler reaching
/dashboard/ can get somebody's logged-in view indexed — which leaks the very
download URLs the protected-download views exist to hide.

Kept in its own module so the badge logic in context_processors.py stays about
badges. Registered in settings.py as a second context processor.
"""

from django.conf import settings
from django.templatetags.static import static as static_url

# `title` is the visible <title>. `description` is what a search engine shows in
# the results. Written for a Nigerian job market, which is what this serves.
PAGE_SEO = {
    "home": {
        "title": "Target JobSpace — Verified Jobs & Career Opportunities in Nigeria",
        "description": (
            "Find vetted job opportunities and connect with verified employers "
            "across Nigeria. Build your profile, upload your CV and get matched "
            "to roles that fit."
        ),
        "priority": "1.0",
        "changefreq": "daily",
    },
    "about": {
        "title": "About Target JobSpace — Connecting Verified Talent with Employers",
        "description": (
            "How Target JobSpace verifies candidates and employers, vets every profile, "
            "and creates safer, more direct connections between professionals "
            "and companies hiring in Nigeria."
        ),
        "priority": "0.7",
        "changefreq": "monthly",
    },
    "employers": {
        "title": "For Employers — Hire Verified Candidates in Nigeria",
        "description": (
            "Post your recruitment needs and reach pre-vetted candidates across "
            "Nigeria. Review verified CVs, shortlist the best fit and fill your "
            "roles faster with Target JobSpace."
        ),
        "priority": "0.9",
        "changefreq": "weekly",
    },
    "candidates": {
        "title": "For Candidates — Build a Verified Professional Profile",
        "description": (
            "Create your profile, upload your CV and get matched with verified "
            "employers hiring in Nigeria. Your details stay private until you "
            "choose to apply."
        ),
        "priority": "0.9",
        "changefreq": "weekly",
    },
    "how_it_works": {
        "title": "How Target JobSpace Works — For Candidates and Employers",
        "description": (
            "A step-by-step guide to using Target JobSpace: how candidates register and "
            "get verified, how employers submit vacancies, and how matches and "
            "shortlisting work."
        ),
        "priority": "0.8",
        "changefreq": "monthly",
    },
    "contact": {
        "title": "Contact Target JobSpace — Support, Questions and Feedback",
        "description": (
            "Get in touch with the Target JobSpace team for help with your account, "
            "applications, employer plans or anything else. We aim to reply "
            "within one working day."
        ),
        "priority": "0.6",
        "changefreq": "monthly",
    },
    "privacy": {
        "title": "Privacy Policy — Target JobSpace",
        "description": (
            "How Target JobSpace collects, uses and protects your personal information, "
            "including the CVs and documents you upload and how employers are "
            "given access to them."
        ),
        "priority": "0.3",
        "changefreq": "yearly",
    },
    "terms": {
        "title": "Terms of Service — Target JobSpace",
        "description": (
            "The terms governing the use of Target JobSpace by candidates and "
            "employers, including subscriptions, verification standards and "
            "acceptable use."
        ),
        "priority": "0.3",
        "changefreq": "yearly",
    },
}

# The URL slug each page key is served at.
PAGE_SLUGS = {
    "about": "about",
    "employers": "employers",
    "candidates": "candidates",
    "how_it_works": "how-it-works",
    "contact": "contact",
    "privacy": "privacy",
    "terms": "terms",
}

# Reverse lookup, built once.
_SLUG_TO_KEY = {slug: key for key, slug in PAGE_SLUGS.items()}

# Anything under these prefixes is private and must never be indexed.
PRIVATE_PREFIXES = (
    "/dashboard/", "/admin/", "/signin/", "/signup/", "/logout/",
    "/documents/", "/payments/",
)


def _absolute(request, path):
    """Build an absolute URL from the request.

    Behind nginx, Host and X-Forwarded-Proto are forwarded and
    SECURE_PROXY_SSL_HEADER is set, so build_absolute_uri() correctly yields
    https:// in production while still working over http in local development.
    Hardcoding either scheme gets one of the two environments wrong, and
    a wrong canonical is worse than none.
    """
    return request.build_absolute_uri(path)


def _page_key(path):
    """Map a request path to a PAGE_SEO key, or None if it is not a public page."""
    if path == "/":
        return "home"
    return _SLUG_TO_KEY.get(path.strip("/"))


def _json_ld(request, key, meta, canonical):
    """schema.org payload. Rich results are the point of this — plain meta tags
    only get a blue link in the results."""
    site_url = _absolute(request, "/")
    site = {"@type": "WebSite", "name": "Target JobSpace", "url": site_url}

    if key == "home":
        return {
            "@context": "https://schema.org",
            **site,
            "description": meta["description"],
            "inLanguage": "en-NG",
        }
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": meta["title"],
        "description": meta["description"],
        "url": canonical,
        "inLanguage": "en-NG",
        "isPartOf": site,
    }


def seo(request):
    """Context processor: every template gets `seo` without a view opting in."""
    path = request.path or "/"
    canonical = _absolute(request, path)

    def page(data, indexable):
        return {
            "seo": {
                **data,
                "canonical": canonical,
                "indexable": indexable,
                "og_type": "website",
                "site_name": "Target JobSpace",
                # 1200x630 share card, not Logo.png (1779x884 letterboxes badly
                # in WhatsApp/Facebook previews). static() resolves the
                # ManifestStaticFilesStorage hash so the URL survives
                # collectstatic in production.
                "image": _absolute(request, static_url("images/og-share-card.png")),
                "image_width": 1200,
                "image_height": 630,
            }
        }

    # Private pages: noindex and NO description. Emitting a description for a
    # dashboard page risks leaking a page title into a search snippet.
    if path.startswith(PRIVATE_PREFIXES):
        return page(
            {
                "title": "Target JobSpace",
                "description": "",
                "robots": "noindex, nofollow",
                "json_ld": None,
            },
            indexable=False,
        )

    key = _page_key(path)
    if key is None:
        # An unknown public URL — a 404, or a new page with no metadata yet.
        # noindex is the safe default: absent from results beats a thin page
        # competing with the real content.
        return page(
            {
                "title": "Target JobSpace",
                "description": "",
                "robots": "noindex, follow",
                "json_ld": None,
            },
            indexable=False,
        )

    meta = PAGE_SEO[key]
    return page(
        {
            "title": meta["title"],
            "description": meta["description"],
            "robots": "index, follow",
            "priority": meta["priority"],
            "changefreq": meta["changefreq"],
            "json_ld": _json_ld(request, key, meta, canonical),
        },
        indexable=True,
    )
