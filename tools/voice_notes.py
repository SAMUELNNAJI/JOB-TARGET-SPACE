"""Audit and repair the voice notes attached to support chat messages.

A SupportMessage.audio row stores only a relative path; the .webm bytes live
under MEDIA_ROOT, which is per-machine storage (the Render disk in prod, this
`media/` folder in dev) while Postgres is shared. So a note recorded on one
environment is a perfectly good database row whose file simply never existed on
the other, and the chat shows "Voice note file missing".

    python tools/voice_notes.py audit                     # what is dangling
    python tools/voice_notes.py install <folder>          # dry run
    python tools/voice_notes.py install <folder> --apply  # put clips back
    python tools/voice_notes.py link 130 clip.webm --apply
    python tools/voice_notes.py clear-missing --apply     # drop dead pointers
    python tools/voice_notes.py prune --apply             # tidy unused files

Nothing here writes anything without --apply, and the two destructive commands
keep a manifest/backup of whatever they touch.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from website.models import SupportMessage  # noqa: E402

MEDIA_ROOT = Path(settings.MEDIA_ROOT)
AUDIO_DIR = MEDIA_ROOT / "chat_audio"


def audio_rows():
    """Every message that names a clip, oldest first."""
    return list(
        SupportMessage.objects.exclude(audio="").exclude(audio=None)
        .order_by("created_at", "id")
    )


def stored_rows():
    """The clip paths the database believes exist, as posix strings."""
    return {m.audio.name for m in audio_rows()}


def missing_rows():
    """Rows whose path is set but whose file this server cannot serve."""
    return [m for m in audio_rows() if not m.audio_available]


def orphan_files():
    """Files under chat_audio/ that no database row points at."""
    if not AUDIO_DIR.exists():
        return []
    used = stored_rows()
    return sorted(
        p for p in AUDIO_DIR.rglob("*")
        if p.is_file()
        and str(p.relative_to(MEDIA_ROOT)).replace("\\", "/") not in used
    )


def describe(row) -> str:
    return f"#{row.id} {row.created_at:%Y-%m-%d %H:%M} [{row.sender_role}] {row.audio.name}"


def cmd_audit(ns) -> int:
    rows, missing, orphans = audio_rows(), missing_rows(), orphan_files()
    print(f"MEDIA_ROOT : {MEDIA_ROOT}")
    print(f"clips named by the database : {len(rows)}")
    print(f"clips playable from here    : {len(rows) - len(missing)}")
    print(f"clips with no file here     : {len(missing)}")
    print(f"files on disk, no row       : {len(orphans)}\n")

    if missing:
        print("MISSING — the row is fine, the bytes are not:")
        for row in missing:
            print(f"  {describe(row)}")
            print(f"      expected: {MEDIA_ROOT / row.audio.name}")
        print("\n  Where to look for them: the Render service shell")
        print("    ls -l /opt/render/project/src/media/chat_audio")
        print("  or the laptop/browser that recorded the note. Then run:")
        print("    python tools/voice_notes.py install <folder-with-the-files> --apply")
    if orphans:
        print("\nORPHAN — files this folder holds that no row references:")
        for p in orphans:
            print(f"  {p.relative_to(MEDIA_ROOT)}  ({p.stat().st_size}B)")
    if not missing and not orphans:
        print("Everything the database names is here, and nothing is unused.")
    return 1 if missing else 0


def cmd_install(ns) -> int:
    """Copy recovered clips into MEDIA_ROOT at the exact path a row expects."""
    src = Path(ns.folder).expanduser().resolve()
    if not src.exists():
        print(f"no such folder: {src}")
        return 2

    wanted = {}
    for row in missing_rows():
        wanted.setdefault(row.audio.name, []).append(row)
    if not wanted:
        print("No row is missing a clip — nothing to install.")
        return 0

    plans = []
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src).as_posix()
        # Accept either the full stored path or just chat_audio/<...>/name.
        candidates = {rel}
        if "chat_audio/" in rel:
            candidates.add(rel[rel.index("chat_audio/"):])
        candidates.add(Path("chat_audio") / path.name)
        for name in candidates:
            if name in wanted:
                plans.append((wanted[name], path, Path(MEDIA_ROOT) / name))
                break

    print(f"rows needing a clip : {len(wanted)}")
    print(f"files matched here  : {len(plans)}")
    for rows, src_file, dest in plans:
        verb = "copy" if ns.apply else "would copy"
        for row in rows:
            print(f"  {verb} {src_file.name} -> {dest}   (row #{row.id})")
    matched = {id(r) for rows, _, _ in plans for r in rows}
    for name, rows in wanted.items():
        for row in rows:
            if id(row) not in matched:
                print(f"  still missing: {describe(row)}")

    if not plans:
        print("\nNothing matched. Filenames must equal the stored path, e.g.")
        print(f"  {AUDIO_DIR / '2026' / '09' / 'voice_XXXXXXXX.webm'}")
        return 1
    if not ns.apply:
        print("\ndry run — add --apply to copy.")
        return 0
    for rows, src_file, dest in plans:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_file, dest)
        for row in rows:
            row.__dict__.pop("audio_available", None)   # drop the stale cache
        print(f"  copied -> {dest}")
    left = len(missing_rows())
    print(f"\nrows still missing a clip: {left}")
    return 0


def cmd_link(ns) -> int:
    """Put one recovered clip at the exact path one message expects."""
    row = SupportMessage.objects.filter(pk=ns.message_id).first()
    if row is None:
        print(f"no message #{ns.message_id}")
        return 2
    if not row.audio:
        print(f"message #{row.id} has no audio path stored; re-record instead.")
        return 2

    src = Path(ns.file).expanduser().resolve()
    if not src.is_file():
        print(f"no such file: {src}")
        return 2
    dest = MEDIA_ROOT / row.audio.name
    print(f"message {describe(row)}")
    print(f"{'copy' if ns.apply else 'would copy'} {src} ({src.stat().st_size}B)")
    print(f"            -> {dest}")
    if src.suffix.lower() != dest.suffix.lower():
        print(f"  note: saving a {src.suffix or 'extensionless'} file as "
              f"{dest.suffix}; browsers may refuse to decode it.")
    if not ns.apply:
        print("\ndry run — add --apply to write.")
        return 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    print("done — the bubble will play this clip.")
    return 0


def cmd_clear(ns) -> int:
    """Blank the audio pointer on rows whose clip is gone for good.

    The transcript keeps the text and the timestamp; only the dead player is
    removed. The old paths are written to media/_lost_voice_notes.json first,
    so the pairing can be restored by hand if a file turns up later.
    """
    rows = missing_rows()
    print(f"rows to clear: {len(rows)}")
    for row in rows:
        print(f"  {describe(row)}")
    if not rows:
        return 0
    if not ns.apply:
        print("\ndry run — add --apply to clear them (a manifest is written first).")
        return 0

    manifest = MEDIA_ROOT / "_lost_voice_notes.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps([{"id": r.id, "audio": r.audio.name,
                     "thread": r.thread_id, "created_at": r.created_at.isoformat()}
                    for r in rows], indent=2),
        encoding="utf-8",
    )
    print(f"\nmanifest written: {manifest}")
    for row in rows:
        row.audio = None
        row.save(update_fields=["audio"])
    print(f"cleared audio on {len(rows)} message(s).")
    return 0


def cmd_prune(ns) -> int:
    """Move chat audio files that no row references into a backup folder."""
    orphans = orphan_files()
    print(f"unreferenced files: {len(orphans)}")
    for p in orphans:
        print(f"  {p.relative_to(MEDIA_ROOT)}  ({p.stat().st_size}B)")
    if not orphans:
        return 0
    if not ns.apply:
        print("\ndry run — add --apply to move them to media/_orphan_backup/.")
        return 0
    backup = MEDIA_ROOT / "_orphan_backup"
    for p in orphans:
        dest = backup / p.relative_to(MEDIA_ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dest))
        print(f"  moved -> {dest}")
    print(f"\n{len(orphans)} file(s) moved; nothing deleted.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("audit", help="report dangling rows and orphan files (default)")

    p = sub.add_parser("install", help="copy a recovered media folder into place")
    p.add_argument("folder")
    p.add_argument("--apply", action="store_true")

    p = sub.add_parser("link", help="attach one recovered clip to one message")
    p.add_argument("message_id", type=int)
    p.add_argument("file")
    p.add_argument("--apply", action="store_true")

    p = sub.add_parser("clear-missing", help="drop audio on rows with no file")
    p.add_argument("--apply", action="store_true")

    p = sub.add_parser("prune", help="move files no row references into a backup")
    p.add_argument("--apply", action="store_true")
    return ap


def main(argv=None) -> int:
    ns = build_parser().parse_args(argv)
    handlers = {"audit": cmd_audit, "install": cmd_install, "link": cmd_link,
                "clear-missing": cmd_clear, "prune": cmd_prune}
    return handlers[ns.cmd or "audit"](ns)


if __name__ == "__main__":
    raise SystemExit(main())
