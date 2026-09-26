import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()
from django.db import connection
from django.contrib.auth.models import User
from website.models import Profile, Specialization, Notification
print("DB ENGINE:", connection.vendor)
print("users:", User.objects.count())
print("profiles:", Profile.objects.count())
print("specializations:", Specialization.objects.count())
print("notifications:", Notification.objects.count())
print("superusers:", list(User.objects.filter(is_superuser=True).values_list("username", flat=True)))
for u in User.objects.all():
    print("  user:", u.username, "pk=", u.pk, "su=", u.is_superuser)
