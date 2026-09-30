"""Compile every project template with Django's own engine and report the ones
that raise TemplateSyntaxError (the `block 'title' appears more than once`
family of errors).

    python tools/check_templates.py            # list broken templates
    python tools/check_templates.py --quiet    # only the names, exit 1 if any
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")

import django  # noqa: E402
from django.template.exceptions import TemplateSyntaxError  # noqa: E402
from django.template.loader import get_template  # noqa: E402

django.setup()

TPL_ROOT = ROOT / "templates"


def template_names() -> list[str]:
    return sorted(str(p.relative_to(TPL_ROOT)).replace("\\", "/")
                  for p in TPL_ROOT.rglob("*.html")
                  if not p.name.startswith("_"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="also check partials (_*.html)")
    ns = ap.parse_args()

    names = template_names()
    if ns.all:
        names = sorted(str(p.relative_to(TPL_ROOT)).replace("\\", "/")
                       for p in TPL_ROOT.rglob("*.html"))

    broken = []
    for name in names:
        try:
            get_template(name)
        except TemplateSyntaxError as exc:
            broken.append(name)
            if not ns.quiet:
                print(f"BROKEN {name}\n       {exc}")
        except Exception as exc:                       # pragma: no cover
            broken.append(name)
            if not ns.quiet:
                print(f"ERROR  {name}\n       {type(exc).__name__}: {exc}")
    if not ns.quiet:
        print(f"\n{len(names) - len(broken)}/{len(names)} templates compile")
    if ns.quiet:
        for name in broken:
            print(name)
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
