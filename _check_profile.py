import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1,testserver"

import django

django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from website.models import CandidateProfile

candidates = list(CandidateProfile.objects.select_related("user"))
print("candidates:", [p.user.username for p in candidates])

if candidates:
    profile = candidates[0]
    c = Client(HTTP_HOST="localhost")
    c.force_login(profile.user)
    r = c.get("/dashboard/candidate/profile/")
    body = r.content.decode()
    print(
        "profile:", r.status_code,
        "wizard-script:", "profile-wizard.js" in body,
        "panes:", body.count('class="pf-pane'),
        "continue-btn:", 'id="pfNext"' in body,
        "back-btn:", 'id="pfBack"' in body,
    )
