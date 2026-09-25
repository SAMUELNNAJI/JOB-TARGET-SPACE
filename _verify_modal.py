import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()
from django.template.loader import get_template
t = get_template("dashboard/admin/candidates.html")
src = t.template.source
import re
checks = {
  "candProfileModal id": src.count('id="candProfileModal"'),
  "candProfileBody id": src.count('id="candProfileBody"'),
  "close button": src.count("adm-modal-close"),
  "cand-row class": src.count('class="cand-row"'),
  "profile-source": src.count("cand-profile-source"),
  "openProfile(": src.count("openProfile("),
  "closeProfile(": src.count("closeProfile("),
  "mouseenter": src.count("mouseenter"),
  "aria-haspopup": src.count('aria-haspopup="dialog"'),
}
for k,v in checks.items(): print(f"{k}: {v}")
