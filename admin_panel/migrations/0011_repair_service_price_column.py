from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0010_event_is_deleted"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                """
                ALTER TABLE dashboard_service
                ADD COLUMN IF NOT EXISTS price NUMERIC(10, 2)
                """,
                """
                UPDATE dashboard_service
                SET price = 0
                WHERE price IS NULL
                """,
                """
                ALTER TABLE dashboard_service
                ALTER COLUMN price SET NOT NULL
                """,
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
