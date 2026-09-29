import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
from django.conf import settings

django.setup()

from website.models import SupportMessage as M

qs = M.objects.exclude(audio="").exclude(audio=None).order_by("id")
print("total audio messages:", qs.count())
for m in qs:
    if not m.audio:
        print(m.id, "NONE")
        continue
    path = os.path.join(str(settings.MEDIA_ROOT), m.audio.name)
    print(m.id, m.audio.name, m.created_at.strftime("%Y-%m-%d %H:%M"),
          "EXISTS" if os.path.exists(path) else "MISSING",
          os.path.getsize(path) if os.path.exists(path) else "")
