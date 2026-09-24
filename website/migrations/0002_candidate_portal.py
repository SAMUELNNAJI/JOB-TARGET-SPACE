from django.db import migrations, models
import django.db.models.deletion


def seed_specializations(apps, schema_editor):
    Specialization = apps.get_model("website", "Specialization")
    names = [
        "Finance & Auditing",
        "Engineering & Systems Infrastructure",
        "Corporate Marketing & Growth",
        "Architecture & Space Planning",
        "Healthcare & Medical Operations",
        "Technical Operations & Equipment Management",
    ]
    for name in names:
        Specialization.objects.get_or_create(name=name, slug=name.lower().replace(" & ", "-").replace(" ", "-"))


def remove_specializations(apps, schema_editor):
    apps.get_model("website", "Specialization").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("website", "0001_initial")]

    operations = [
        migrations.AddField(model_name="profile", name="address", field=models.TextField(blank=True)),
        migrations.AddField(model_name="profile", name="availability", field=models.CharField(blank=True, choices=[("immediate", "Immediate"), ("one_month", "1 Month Notice")], max_length=20)),
        migrations.AddField(model_name="profile", name="certifications", field=models.TextField(blank=True)),
        migrations.AddField(model_name="profile", name="equipment_competencies", field=models.TextField(blank=True)),
        migrations.AddField(model_name="profile", name="expected_salary", field=models.PositiveIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="profile", name="legal_name", field=models.CharField(blank=True, max_length=150)),
        migrations.AddField(model_name="profile", name="primary_degree", field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name="profile", name="professional_pitch", field=models.TextField(blank=True)),
        migrations.AddField(model_name="profile", name="software_competencies", field=models.TextField(blank=True)),
        migrations.AddField(model_name="profile", name="submitted_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="profile", name="updated_at", field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name="profile", name="verification_notes", field=models.TextField(blank=True)),
        migrations.AddField(model_name="profile", name="verification_status", field=models.CharField(choices=[("draft", "Draft"), ("pending", "Pending Review"), ("verifying", "Under Verification"), ("verified", "Vetted & Verified"), ("changes", "Requires Changes")], default="draft", max_length=20)),
        migrations.AddField(model_name="profile", name="verified_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(name="Specialization", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("name", models.CharField(max_length=120, unique=True)), ("slug", models.SlugField(max_length=140, unique=True))], options={"ordering": ("name",)}),
        migrations.AddField(model_name="profile", name="specializations", field=models.ManyToManyField(blank=True, related_name="profiles", to="website.specialization")),
        migrations.CreateModel(name="CandidateDocument", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("file", models.FileField(upload_to="candidate_documents/%Y/%m/")), ("uploaded_at", models.DateTimeField(auto_now_add=True)), ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cv_documents", to="website.profile"))]),
        migrations.CreateModel(name="Qualification", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("title", models.CharField(max_length=200)), ("institution", models.CharField(blank=True, max_length=200)), ("year", models.PositiveIntegerField(blank=True, null=True)), ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="qualifications", to="website.profile"))]),
        migrations.CreateModel(name="Notification", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("title", models.CharField(max_length=180)), ("message", models.TextField()), ("is_read", models.BooleanField(default=False)), ("created_at", models.DateTimeField(auto_now_add=True)), ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="website.profile"))], options={"ordering": ("-created_at",)}),
        migrations.CreateModel(name="CandidateMatch", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("note", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("is_active", models.BooleanField(default=True)), ("employer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="candidate_matches", to="website.profile")), ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="matches", to="website.profile"))], options={"ordering": ("-created_at",)}),
        migrations.RunPython(seed_specializations, remove_specializations),
    ]
