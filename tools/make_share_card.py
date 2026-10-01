# Generates the WhatsApp / social share card.
#
# WHY THIS EXISTS: the site's og:image pointed at Logo.png, which is 1779x884
# (ratio 2.01). WhatsApp, Facebook, X and LinkedIn all want roughly 1.91:1 —
# 1200x630. Pointing them at a 2.01 logo letterboxes it into a strip with empty
# bands, and the result is unreadable at thumbnail size. A share card has to be
# a COMPOSED image: brand mark, headline, value proposition, and the domain.
#
# Run from the project root:  python tools/make_share_card.py
# Output: static/images/og-share-card.png
#
# Requires Pillow. It is a build-time-only tool, not a runtime dependency, so it
# is deliberately NOT in requirements.txt — adding it would put an image library
# on every production install for something that runs once, by hand.
import os

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit(
        "Pillow is required to build the share card.\n"
        "  pip install Pillow\n"
        "It is intentionally not in requirements.txt — this script runs by hand,"
        " not on the server."
    )

W, H = 1200, 630
OUT = os.path.join("static", "images", "og-share-card.png")
LOGO = os.path.join("static", "images", "Logo.png")

# Brand colours, matching templates/base.html.
INK = (14, 20, 32)
RED = (214, 0, 29)
WHITE = (255, 255, 255)
MUTED = (203, 213, 225)


def font(size, bold=False):
    """Load a font, preferring the site's actual typeface."""
    candidates = (
        ["C:/Windows/Fonts/montserratbd.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["C:/Windows/Fonts/montserrat.ttf", "C:/Windows/Fonts/segoeui.ttf"]
    )
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main():
    # Dark base, matching the site header.
    card = Image.new("RGB", (W, H), INK)
    draw = ImageDraw.Draw(card)

    # Subtle vertical gradient so the card is not a flat rectangle in a feed.
    for i in range(H):
        t = i / H
        shade = int(14 + 18 * t)
        draw.line([(0, i), (W, i)], fill=(shade, shade + 4, shade + 12))

    # Logo, top-left.
    pad = 72
    logo_h = 104
    if os.path.exists(LOGO):
        logo = Image.open(LOGO).convert("RGBA")
        ratio = logo_h / logo.height
        logo = logo.resize((int(logo.width * ratio), logo_h), Image.LANCZOS)
        card.paste(logo, (pad, pad - 18), logo)
    else:
        print(f"  warning: {LOGO} not found, continuing without the logo")

    # Red accent rule.
    draw.rectangle([pad, pad + 118, pad + 84, pad + 126], fill=RED)

    # Headline, split by hand. ImageDraw does not wrap text, so a single long
    # string would run off the canvas; the break points are chosen to fit 1200px
    # at 60px bold. Vertical positions are checked against the subtitle and the
    # domain box below so nothing overlaps (an earlier version did).
    headline = font(60, bold=True)
    draw.text((pad, pad + 156), "Verified jobs and", font=headline, fill=WHITE)
    draw.text((pad, pad + 228), "career opportunities", font=headline, fill=WHITE)
    draw.text((pad, pad + 300), "in Nigeria", font=headline, fill=RED)

    sub = font(27)
    draw.text(
        (pad, pad + 378),
        "Create a profile, upload your CV, get matched with vetted employers.",
        font=sub,
        fill=MUTED,
    )

    # Domain, bottom-left. This is what stops the card looking like a generic
    # ad — the reader can see where it came from.
    domain = font(26, bold=True)
    draw.rectangle([pad, H - 104, pad + 272, H - 52], outline=RED, width=2)
    draw.text((pad + 24, H - 94), "targetjobspace.com", font=domain, fill=WHITE)

    card.save(OUT, "PNG", optimize=True)
    kb = os.path.getsize(OUT) // 1024
    print(f"wrote {OUT}  {card.width}x{card.height}  "
          f"ratio={card.width / card.height:.2f}  {kb} KB")

    # WhatsApp's crawler is conservative about size; a very large PNG can be
    # skipped where a smaller file would be fetched and shown.
    if kb > 300:
        card.save(OUT, "JPEG", quality=88, optimize=True)
        print(f"  over 300 KB as PNG — re-saved as JPEG "
              f"({os.path.getsize(OUT) // 1024} KB)")


if __name__ == "__main__":
    main()

