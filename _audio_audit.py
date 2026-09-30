"""One-off audit: does every ChatMessage.audio_file exist on disk?

Run:  python _audio_audit.py
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.conf import settings  # noqa: E402
from apps.support.models import ChatMessage  # noqa: E402

print("MEDIA_ROOT :", settings.MEDIA_ROOT)
print("DEBUG      :", settings.DEBUG)

audio_dir = os.path.join(settings.MEDIA_ROOT, "chat_audio")
print("\n--- files actually present in chat_audio/ ---")
if os.path.isdir(audio_dir):
    names = sorted(os.listdir(audio_dir))
    for n in names:
        p = os.path.join(audio_dir, n)
        print("  %-46s %8d bytes" % (n, os.path.getsize(p)))
    print("total on disk:", len(names))
else:
    print("  (directory does not exist:", audio_dir, ")")

qs = ChatMessage.objects.exclude(audio_file="").exclude(
    audio_file=None
).order_by("id")
print("\n--- DB rows with an audio_file value ---")
missing = 0
present = 0
for m in qs:
    path = m.audio_file.path
    try:
        size = os.path.getsize(path)
        ok = size > 0
        present += 1
        flag = "OK " if ok else "ZERO-BYTE"
    except OSError:
        ok = False
        missing += 1
        size = "-"
        flag = "MISSING"
        if not os.path.isdir(os.path.dirname(path)):
            flag += " (dir absent)"
    print("  msg %-5s %-11s %-46s %s" % (m.id, flag, m.audio_file.name, size))

print("\nDB rows with audio :", qs.count())
print("present on disk    :", present)
print("missing / broken   :", missing)
