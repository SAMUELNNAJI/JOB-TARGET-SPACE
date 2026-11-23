"""Small, dependency-free HTML allow-list for staff-authored blog content."""

from html import escape
from html.parser import HTMLParser
import re
from urllib.parse import urlparse

from django.utils.safestring import mark_safe


ALLOWED_TAGS = {
    "p", "div", "br", "h1", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "s", "del", "strike",
    "ul", "ol", "li", "blockquote", "pre", "code", "hr", "table", "thead",
    "tbody", "tr", "th", "td", "a", "span",
}
VOID_TAGS = {"br", "hr"}
ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "span": {"style"},
    "p": {"style"},
    "div": {"style"},
}


def _safe_url(value):
    """Allow ordinary links, anchors and mail links; reject script-like URLs."""
    value = value.strip()
    scheme = urlparse(value).scheme.lower()
    return value if scheme in {"", "http", "https", "mailto"} else ""


def _safe_style(value):
    """Preserve the harmless text styles commonly supplied by office editors."""
    allowed = []
    for declaration in value.split(";"):
        match = re.fullmatch(r"\s*([\w-]+)\s*:\s*(.*?)\s*", declaration, flags=re.I)
        if not match:
            continue
        name, style_value = match.group(1).lower(), match.group(2)
        normalized = style_value.lower()
        if name == "color" and re.fullmatch(r"(?:#[0-9a-f]{3,8}|(?:rgb|rgba)\([0-9.,%\s]+\)|[a-z]+)", normalized):
            allowed.append(f"color: {style_value}")
        elif name == "font-weight" and (normalized in {"normal", "bold", "bolder", "lighter"} or re.fullmatch(r"[1-9]00", normalized)):
            allowed.append(f"font-weight: {style_value}")
        elif name == "font-style" and normalized in {"normal", "italic", "oblique"}:
            allowed.append(f"font-style: {style_value}")
        elif name == "text-decoration" and re.fullmatch(r"(?:none|underline|line-through)(?:\s+(?:underline|line-through))?", normalized):
            allowed.append(f"text-decoration: {style_value}")
    return "; ".join(allowed)


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
                value = _safe_style(value)
                if not value:
                    continue
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
