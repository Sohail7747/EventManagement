from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0003_booking_checkout_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="booking_end_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
