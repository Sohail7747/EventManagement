
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0004_eventpackage_packageservice"),
        ("packages", "0001_move_package_models"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name="eventpackage",
                    name="event",
                ),
                migrations.RemoveField(
                    model_name="eventpackage",
                    name="user",
                ),
                migrations.RemoveConstraint(
                    model_name="packageservice",
                    name="unique_service_per_event_package",
                ),
                migrations.RemoveField(
                    model_name="packageservice",
                    name="package",
                ),
                migrations.RemoveField(
                    model_name="packageservice",
                    name="service",
                ),
                migrations.DeleteModel(
                    name="EventPackage",
                ),
                migrations.DeleteModel(
                    name="PackageService",
                ),
            ],
        ),
    ]
