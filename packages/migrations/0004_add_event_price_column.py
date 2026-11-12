
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("packages", "0003_alter_eventpackage_table_alter_packageservice_table"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE dashboard_eventpackage
                ADD COLUMN IF NOT EXISTS event_price NUMERIC(10, 2) NOT NULL DEFAULT 0;
            """,
            reverse_sql="""
                ALTER TABLE dashboard_eventpackage
                DROP COLUMN IF EXISTS event_price;
            """,
        ),
    ]
