from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0002_package_booking_details"),
        ("dashboard", "0006_service_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="guest_count",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="booking",
            name="advance_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=12,
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="customer_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="booking",
            name="customer_email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="booking",
            name="customer_phone",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="booking",
            name="add_on_services",
            field=models.ManyToManyField(
                blank=True,
                related_name="customer_booking_add_ons",
                to="dashboard.service",
            ),
        ),
    ]
