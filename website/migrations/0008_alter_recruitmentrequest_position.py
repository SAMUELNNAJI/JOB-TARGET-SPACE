from django.db import migrations, models


class Migration(migrations.Migration):
    """Allow employers to submit any profession, not only the built-in list.

    The suggestion list (RecruitmentRequest.POSITION_CHOICES) still populates the
    dropdown in the employer request form, but the stored value is no longer
    constrained to it, so a custom profession can be typed in.
    """

    dependencies = [
        ('website', '0007_alter_profile_verification_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recruitmentrequest',
            name='position',
            field=models.CharField(max_length=120),
        ),
    ]