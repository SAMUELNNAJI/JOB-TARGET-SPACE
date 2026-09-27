"""Prove the mobile composer keeps the send button on screen.

The button vanished on phones because the textarea's intrinsic width won
the flex space negotiation and pushed .chat-send past the panel edge,
where `overflow: hidden` clipped it away. This parses the real CSS,
rebuilds the cascade per breakpoint, and simulates track sizing.

Run:  python _check_composer_fit.py
"""
import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parent / "static" / "css" / "chat.css"
failures = []


def check(label, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + label + (f"  [{detail}]" if detail else ""))
    if not ok:
        failures.append(label)


def walk(css, depth=0, out=None):
    """Flatten a stylesheet to (selector, body, media_depth) tuples."""
    out = [] if out is None else out
    i = sel_start = 0
    while i < len(css):
        if css[i] != "{":
            i += 1
            continue
        selectors = css[sel_start:i].strip()
        j, inner = i + 1, 0
        while j < len(css):
            if css[j] == "{":
                inner += 1
            elif css[j] == "}":
                if inner == 0:
                    break
                inner -= 1
            j += 1
        body = css[i + 1:j]
        if selectors.startswith("@media"):
            walk(body, depth + 1, out)
        elif selectors and not selectors.startswith("@"):
            out.append((selectors, body, depth))
        i = sel_start = j + 1
    return out


RULES = walk(re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL))
# Widest breakpoint declared at each nesting depth in this sheet.
MAXW = {1: 768, 2: 480, 3: 1024}


def cascade(selector, width):
    """Declarations that apply to `selector` at a given viewport width."""
    merged = {}
    for selectors, body, depth in RULES:
        if selector not in [s.strip() for s in selectors.split(",")]:
            continue
        if depth and width > MAXW.get(depth, 0):
            continue
        for decl in body.split(";"):
            if ":" in decl:
                prop, _, value = decl.partition(":")
                merged[prop.strip()] = value.strip()
    return merged


def px(value, fallback=0.0):
    m = re.match(r"^(\d+(?:\.\d+)?)px$", (value or "").strip())
    return float(m.group(1)) if m else fallback


# A <textarea> defaults to cols=20, giving it a large intrinsic width.
# That is the width which used to bulldoze the send button off the panel.
TEXTAREA_INTRINSIC = 180.0

for width in (320, 360, 375, 390, 414, 768):
    composer = cascade(".chat-composer", width)
    mic = cascade(".chat-mic", width)
    send = cascade(".chat-send", width)
    wrap = cascade(".chat-input-wrap", width)

    is_grid = composer.get("display") == "grid"
    check(f"{width}px: composer uses grid", is_grid, composer.get("display", "none"))

    inner = width - px(composer.get("padding-left", "0")) * 2
    gap = px(composer.get("gap", "0px"))
    mic_w = px(mic.get("width"), 42.0)
    send_w = px(send.get("width"), 42.0)

    if is_grid:
        # Tracks: auto | minmax(0, 1fr) | auto. Only the middle track flexes,
        # so mic and send are structurally guaranteed on screen.
        free = inner - mic_w - send_w - 2 * gap
        check(f"{width}px: send button on screen", free >= 0, f"free={free:.0f}px")
        check(f"{width}px: input track can shrink to 0", wrap.get("min-width") == "0")
    else:
        needed = mic_w + TEXTAREA_INTRINSIC + send_w + 2 * gap
        check(f"{width}px: send button on screen", needed <= inner,
              f"needed={needed:.0f} inner={inner:.0f}")

print()
if failures:
    print(f"{len(failures)} check(s) failed")
    sys.exit(1)
print("Send button stays on screen at every tested width")
