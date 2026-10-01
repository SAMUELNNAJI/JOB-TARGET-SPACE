"""Handlers for the custom error pages.

These are thin on purpose. The work is in the templates; all this does is return
the right template with an empty context.

Why the context is explicitly empty rather than left to Django:

  * handler404 normally receives `request_path` and `exception`. Harmless, but the
    templates do not use them, and passing less is passing less that could be
    wrong.
  * handler500 is the important one. Django calls it when the original exception
    handler itself failed — often because the database is down. Every context
    processor is therefore suspect, including the SEO one and
    `dashboard_badges`, which queries the database. Rendering with `{}` skips
    the request context entirely, so a database outage cannot turn a 500 page
    into a second 500.

`handler403` is here because the protected-download views raise
`PermissionDenied`, and Django's default text-only 403 would look like a bug
rather than a deliberate refusal.
"""

from django.http import HttpResponse
from django.template import TemplateDoesNotExist
from django.template.loader import get_template


def _render_bare(template_name, status):
    """Render a template with NO request and NO context processors.

    This is the important detail. `django.shortcuts.render()` builds a
    RequestContext, which runs every configured context processor — including
    `website.seo.seo` and `website.context_processors.dashboard_badges`, and the
    latter queries the database. During a 500 the database is frequently the
    thing that is down, so using render() here would raise a second exception
    while handling the first, and the user would get Django's bare
    "Server Error (500)" instead of the designed page.

    A plain Context skips the request entirely, so the page renders from the
    template alone. The 500 template is written to need nothing else.
    """
    try:
        template = get_template(template_name)
    except TemplateDoesNotExist:  # pragma: no cover - only if a file is deleted
        return HttpResponse("Server Error", status=status)
    # `get_template()` returns a backend template whose `render()` takes a dict
    # and builds the Context itself. Passing a Context here is a TypeError
    # ("context must be a dict rather than Context"), so pass {} — which is
    # still enough to keep context processors out, because that only happens
    # via a RequestContext, and this is a plain one.
    return HttpResponse(template.render({}), status=status)


def page_not_found(request, exception=None, template_name="404.html"):
    return _render_bare(template_name, 404)


def permission_denied(request, exception=None, template_name="403.html"):
    return _render_bare(template_name, 403)


def server_error(request, template_name="500.html"):
    return _render_bare(template_name, 500)
