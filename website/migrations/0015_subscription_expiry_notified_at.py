# One-time expiry sweep for lapsed employer plans (see views._sweep_expired_plans).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0014_payment_verified_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='expiry_notified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
