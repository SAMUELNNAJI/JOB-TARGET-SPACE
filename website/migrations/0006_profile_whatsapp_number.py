from django.db import migrations, models


def copy_whatsapp_url_to_number(apps, schema_editor):
    Profile = apps.get_model("website", "Profile")
    for profile in Profile.objects.exclude(whatsapp_url=""):
        url = (profile.whatsapp_url or "").strip()
        digits = "".join(ch for ch in url.rsplit("/", 1)[-1] if ch.isdigit())
        if digits and not profile.whatsapp_number:
            profile.whatsapp_number = digits
            profile.save(update_fields=["whatsapp_number"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0005_notification_kind'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='whatsapp_number',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.RunPython(copy_whatsapp_url_to_number, noop),
    ]