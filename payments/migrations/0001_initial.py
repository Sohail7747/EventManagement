import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bookings", "0005_booking_payment_id_booking_payment_status_and_more"),
        ("packages", "0004_add_event_price_column"),
    ]

    operations = [
        migrations.CreateModel(
            name="PackagePaymentAttempt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("receipt", models.CharField(max_length=40, unique=True)),
                (
                    "order_id",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        unique=True,
                    ),
                ),
                (
                    "payment_id",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        unique=True,
                    ),
                ),
                ("amount_paise", models.PositiveBigIntegerField()),
                ("total_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("booking_date", models.DateField()),
                ("booking_end_date", models.DateField(blank=True, null=True)),
                ("guest_count", models.PositiveIntegerField()),
                ("customer_name", models.CharField(max_length=150)),
                ("customer_email", models.EmailField(max_length=254)),
                ("customer_phone", models.CharField(max_length=20)),
                ("customer_notes", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("PAID", "Paid"),
                            ("FAILED", "Failed"),
                        ],
                        default="CREATED",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "booking",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_attempt",
                        to="bookings.booking",
                    ),
                ),
                (
                    "package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_attempts",
                        to="packages.catalogpackage",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="package_payment_attempts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
