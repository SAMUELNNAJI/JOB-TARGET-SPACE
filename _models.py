"""List every model in the website app with its concrete fields."""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jobspace.settings")
django.setup()

from django.apps import apps  # noqa: E402

for model in apps.get_app_config("website").get_models():
    fields = ", ".join(f.name for f in model._meta.get_fields())
    print("=" * 78)
    print(f"{model._meta.db_table}   ({model.__name__})")
    print(f"    {fields}")
print("=" * 78)
print("LOCAL BACKEND:", __import__("django.db", fromlist=["connection"]).connection.vendor)
