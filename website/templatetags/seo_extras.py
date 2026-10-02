"""Template filters for SEO markup.

Registered as a builtin in settings.py so `{{ value|json_script_safe }}` works
in any template without `{% load %}`.
"""

import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="initials")
def initials(value, max_chars=2):
    """Return up to *max_chars* initials from a full name.

    "John Doe"     → "JD"
    "Mary Jane Watson" → "MJ"   (first two words only)
    "John"         → "JO"       (first 2 chars of single word)
    ""             → "JS"       (fallback)
    """
    name = str(value or "").strip()
    if not name:
        return "JS"
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    # Single word — take first two characters
    return name[:2].upper()


@register.filter(name="json_script_safe", is_safe=True)
def json_script_safe(value):
    """Serialise a dict to JSON for embedding inside a <script> block.

    The escaping is the whole point of this filter. A raw `json.dumps` inside
    <script type="application/ld+json"> is an injection vector: any value
    containing `</script>` closes the tag early and everything after it is
    parsed as HTML. Where a description is built from user-supplied text, that
    is a real stored-XSS route.

    Escaping `<`, `>` and `&` to unicode escapes is what JSON.stringify and
    PHP's json_encode do, and it makes `</script>` unmatchable. The sequences
    introduced are valid JSON, so the parser is unaffected.
    """
    if value is None:
        return ""
    text = json.dumps(value, ensure_ascii=False, sort_keys=False)
    text = (
        text.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    return mark_safe(text)

