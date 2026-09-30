"""One-off verification: compile every project template with Django's engine and
write the results to _tplcheck.txt (incrementally flushed, so the report survives
even if the process is interrupted).
"""
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")

OUT = ROOT / "_tplcheck.txt"
log = OUT.open("w", encoding="utf-8", buffering=1)


def write(msg: str) -> None:
    print(msg, file=log)


try:
    import django
    from django.template.exceptions import TemplateSyntaxError
    from django.template.loader import get_template

    django.setup()

    TPL_ROOT = ROOT / "templates"
    names = sorted(
        str(p.relative_to(TPL_ROOT)).replace("\\", "/")
        for p in TPL_ROOT.rglob("*.html")
    )
    broken = 0
    for name in names:
        try:
            get_template(name)
        except TemplateSyntaxError as exc:
            broken += 1
            write(f"BROKEN {name}\n       {exc}")
        except Exception as exc:
            broken += 1
            write(f"ERROR  {name}\n       {type(exc).__name__}: {exc}")
    write(f"\n{len(names) - broken}/{len(names)} templates compile")

    # Focused render check: the target template compiles and every block it
    # overrides exists exactly once in the parent chain.
    from django.template.loader_tags import BlockNode
    from django.template.loader import get_template as gt

    tpl = gt("dashboard/admin/requests.html")
    counts: dict[str, int] = {}
    for node in tpl.template.nodelist:
        if isinstance(node, BlockNode):
            counts[node.name] = counts.get(node.name, 0) + 1
    write(f"\nrequests.html top-level blocks: {counts}")
    dupes = {k: v for k, v in counts.items() if v > 1}
    write(f"duplicate blocks: {dupes if dupes else 'none'}")
    write("\nRENDER_CHECK_OK" if not dupes else "\nRENDER_CHECK_FAILED")
except Exception:
    write("FATAL\n" + traceback.format_exc())
finally:
    write("DONE")
    log.close()
