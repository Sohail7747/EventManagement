
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("dashboard", "0004_eventpackage_packageservice"),
        migrations.swappable_dependency("auth.User"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="EventPackage",
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
                        (
                            "event_date",
                            models.DateField(),
                        ),
                        (
                            "event_price",
                            models.DecimalField(
                                decimal_places=2,
                                default=0,
                                max_digits=10,
                            ),
                        ),
                        (
                            "total_cost",
                            models.DecimalField(
                                decimal_places=2,
                                default=0,
                                max_digits=12,
                            ),
                        ),
                        (
                            "created_at",
                            models.DateTimeField(auto_now_add=True),
                        ),
                        (
                            "event",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="packages",
                                to="dashboard.event",
                            ),
                        ),
                        (
                            "user",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="event_packages",
                                to="auth.user",
                            ),
                        ),
                    ],
                ),
                migrations.CreateModel(
                    name="PackageService",
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
                        (
                            "selected_price",
                            models.DecimalField(
                                decimal_places=2,
                                max_digits=10,
                                validators=[
                                    django.core.validators.MinValueValidator(0)
                                ],
                            ),
                        ),
                        (
                            "package",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="package_services",
                                to="packages.eventpackage",
                            ),
                        ),
                        (
                            "service",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.PROTECT,
                                related_name="package_selections",
                                to="dashboard.service",
                            ),
                        ),
                    ],
                    options={
                        "constraints": [
                            models.UniqueConstraint(
                                fields=("package", "service"),
                                name="unique_service_per_event_package",
                            ),
                        ],
                    },
                ),
            ],
        ),
    ]
