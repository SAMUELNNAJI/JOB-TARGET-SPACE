"""Repair Django templates damaged by generic-block tag substitution.

The damage pattern: real `{{ … }}` / `{% … %}` tags were overwritten with a tag
that already existed elsewhere in the same file (`{% block title %}`,
`{% endblock %}`, `{% block body_class %}`, sometimes an `{% if … %}`) with a
counter digit fused to the text that followed it, e.g.

    <td>{% block title %}4        ->  <td>{{ match.profile.legal_name }}

Strategy: take the tag stream of a known-good revision (default `HEAD~1`) and
walk it in lockstep with the damaged file. Whichever damaged tag no longer
matches the tag the clean revision has at the same position *and* carries a
trailing digit run is a corrupted marker; it is restored from the clean stream
and its counter digits are dropped. Everything else - including genuine edits
made after that revision - is left untouched.

Nothing is written unless --apply is given, and a file is only rewritten when
its repaired tag stream is identical to the reference one.

Usage:
    python tools/tpl_repair.py                      # check the broken ones
    python tools/tpl_repair.py --apply templates/dashboard/employer/index.html
    python tools/tpl_repair.py --rev HEAD~1 --apply
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TAG_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)


def git_show(rev: str, rel: str) -> str:
    return subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=ROOT,
                          check=True, capture_output=True).stdout.decode("utf-8")


def tags_of(text: str) -> list[str]:
    return [m.group(0) for m in TAG_RE.finditer(text)]


def segments(text: str, digits: str = "greedy"):
    """Split `text` into (kind, tag, fused_digits) tuples.

    kind is 'text' or 'tag'; fused_digits holds the run of decimal digits that
    sits immediately after a tag (the corruption's counter, or innocent text).
    digits='one' captures a single digit, 'greedy' the whole run, 'none' keeps
    them in the surrounding text.
    """
    segs, pos = [], 0
    for m in TAG_RE.finditer(text):
        if m.start() > pos:
            segs.append(("text", text[pos:m.start()], ""))
        digs = ""
        if digits != "none":
            j = m.end()
            if digits == "one":
                j = m.end() + 1 if text[m.end():m.end() + 1].isdigit() else m.end()
            else:
                while j < len(text) and text[j].isdigit():
                    j += 1
            digs = text[m.end():j]
        segs.append(("tag", m.group(0), digs))
        pos = j if digits != "none" else m.end()
    if pos < len(text):
        segs.append(("text", text[pos:], ""))
    return segs


def positional_map(segs, good_tags):
    """Align damaged segments with a clean tag stream.

    Returns ({seg_index: replacement_tag}, consumed) or None when the two
    streams cannot be matched one to one.
    """
    repl, i = {}, 0
    for idx, (kind, value, digs) in enumerate(segs):
        if kind != "tag":
            continue
        expected = good_tags[i] if i < len(good_tags) else None
        if value == expected:
            i += 1
        elif digs and expected is not None:
            repl[idx] = expected
            i += 1
        else:
            return None
    return (repl, i) if i == len(good_tags) else None


def rebuild(segs, repl, digits: str = "greedy"):
    """Reassemble: restored markers lose their counter digits, real tags keep all."""
    out = []
    for idx, (kind, value, digs) in enumerate(segs):
        if kind == "text":
            out.append(value)
        elif idx in repl:
            out.append(repl[idx])
        else:
            out.append(value + digs)
    return "".join(out)


def ambiguous_digits(good: str, segs, repl) -> list[str]:
    """Flag restored tags after which the clean file really does have a digit.

    Those are the only places where dropping the digit run could lose text.
    """
    after = []
    for m in TAG_RE.finditer(good):
        after.append(good[m.end():m.end() + 1])
    hits = []
    nth = -1
    for idx, (kind, value, digs) in enumerate(segs):
        if kind != "tag":
            continue
        nth += 1
        if idx in repl and after[nth:nth + 1] and after[nth].isdigit():
            hits.append(value)
    return hits


def damaged_files(quiet: bool = True) -> list[str]:
    """Template paths (relative to the repo) that Django cannot compile.

    Delegates to the project's own checker so the real settings engine, loaders
    and context processors are used.
    """
    checker = Path(__file__).with_name("check_templates.py")
    cmd = [sys.executable, str(checker)] + (["--quiet", "--all"] if quiet else ["--all"])
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return sorted({"templates/" + line.strip().replace("\\", "/")
                   for line in proc.stdout.splitlines() if line.strip()})


def main(argv=None) -> int:
    ns = build_parser().parse_args(argv)
    files = ns.files or damaged_files()
    if not files:
        print("all templates compile - nothing to repair")
        return 0
    failed = []
    for rel in files:
        bad = (ROOT / rel).read_text(encoding="utf-8")
        good = git_show(ns.rev, rel)
        good_tags = tags_of(good)
        for mode in ([ns.digits] if ns.digits != "auto" else ["greedy", "one"]):
            segs = segments(bad, mode)
            mapped = positional_map(segs, good_tags)
            if not mapped:
                continue
            repl, _ = mapped
            fixed = rebuild(segs, repl, mode)
            if tags_of(fixed) != good_tags:
                continue
            ambiguous = ambiguous_digits(good, segs, repl)
            if ns.apply:
                (ROOT / rel).write_text(fixed, encoding="utf-8", newline="")
            note = ("" if not ambiguous else
                    f"  [review: {len(ambiguous)} digit(s) follow a restored tag in {ns.rev}]")
            print(f"{'applied' if ns.apply else 'ready '} {rel}: "
                  f"{len(repl)} marker(s) restored from {ns.rev} ({mode} digits){note}")
            break
        else:
            print(f"FAIL  {rel}: damaged tags do not align with {ns.rev} - manual repair needed")
            failed.append(rel)

    print(f"\n{len(files) - len(failed)}/{len(files)} file(s) "
          f"{'repaired' if ns.apply else 'repairable'}")
    if failed:
        print("needs manual work: " + ", ".join(failed))
    if ns.apply:
        print("re-running Django template compiler to confirm ...")
        still = damaged_files()
        print("COMPILED CLEAN - every template parses" if not still
              else "STILL BROKEN: " + ", ".join(still))
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*", help="template paths relative to the repo "
                                             "(default: every template that fails to compile)")
    ap.add_argument("--rev", default="HEAD~1", help="revision with intact templates (default HEAD~1)")
    ap.add_argument("--apply", action="store_true", help="write the repaired files")
    ap.add_argument("--digits", choices=["auto", "greedy", "one", "none"], default="auto",
                    help="how much of the digit run fused to a tag belongs to the corruption")
    return ap


if __name__ == "__main__":
    raise SystemExit(main())
