from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("packages", "0004_add_event_price_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="catalogpackage",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
    ]
