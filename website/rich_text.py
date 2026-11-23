"""Small, dependency-free HTML allow-list for staff-authored blog content."""

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

from django.utils.safestring import mark_safe


ALLOWED_TAGS = {
    "p", "br", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "s",
    "ul", "ol", "li", "blockquote", "pre", "code", "hr", "table", "thead",
    "tbody", "tr", "th", "td", "a", "span",
}
VOID_TAGS = {"br", "hr"}
ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "span": {"style"},
}


def _safe_url(value):
    """Allow ordinary links, anchors and mail links; reject script-like URLs."""
    value = value.strip()
    scheme = urlparse(value).scheme.lower()
    return value if scheme in {"", "http", "https", "mailto"} else ""


class _BlogHTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.open_tags = []
        self.ignored_content_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.ignored_content_depth += 1
            return
        if self.ignored_content_depth:
            return
        if tag not in ALLOWED_TAGS:
            return
        allowed = ALLOWED_ATTRS.get(tag, set())
        clean_attrs = []
        for name, value in attrs:
            name = name.lower()
            if name not in allowed or value is None:
                continue
            if name == "href":
                value = _safe_url(value)
                if not value:
                    continue
            if name == "target" and value != "_blank":
                continue
            if name == "rel":
                value = "noopener noreferrer"
            if name == "style":
                # Summernote's colour toolbar only needs this declaration.
                declarations = [d.strip() for d in value.split(";") if d.strip().lower().startswith("color:")]
                if not declarations:
                    continue
                value = "; ".join(declarations)
            clean_attrs.append(f' {name}="{escape(value, quote=True)}"')
        if tag == "a" and any(name == "target" and value == "_blank" for name, value in attrs):
            if not any(attr.startswith(" rel=") for attr in clean_attrs):
                clean_attrs.append(' rel="noopener noreferrer"')
        self.parts.append(f"<{tag}{''.join(clean_attrs)}>")
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.ignored_content_depth = max(0, self.ignored_content_depth - 1)
            return
        if self.ignored_content_depth:
            return
        if tag not in ALLOWED_TAGS or tag in VOID_TAGS or tag not in self.open_tags:
            return
        # Close any still-open nested tags first, keeping the resulting HTML valid.
        while self.open_tags:
            open_tag = self.open_tags.pop()
            self.parts.append(f"</{open_tag}>")
            if open_tag == tag:
                break

    def handle_data(self, data):
        if not self.ignored_content_depth:
            self.parts.append(escape(data))

    def result(self):
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


def sanitize_blog_html(value):
    parser = _BlogHTMLSanitizer()
    parser.feed(value or "")
    parser.close()
    return parser.result()


def safe_blog_html(value):
    return mark_safe(sanitize_blog_html(value))
