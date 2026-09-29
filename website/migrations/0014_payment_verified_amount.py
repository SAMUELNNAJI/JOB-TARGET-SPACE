# Receipt-amount verification for manual (bank-transfer) approvals.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('website', '0013_alter_payment_options_payment_admin_notes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='verified_amount',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
