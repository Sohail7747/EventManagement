from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0008_seed_static_pages"),
    ]

    operations = [
        migrations.AddField(
            model_name="service",
            name="is_deleted",
            field=models.BooleanField(default=False),
        ),
    ]
