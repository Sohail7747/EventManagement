from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0009_service_is_deleted"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
    ]
