from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('packages', '0002_catalogpackage_catalogpackageitem'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        DO $$
                        BEGIN
                            IF to_regclass('packages_eventpackage') IS NOT NULL
                                AND to_regclass('dashboard_eventpackage') IS NULL THEN
                                ALTER TABLE packages_eventpackage RENAME TO dashboard_eventpackage;
                            END IF;

                            IF to_regclass('packages_packageservice') IS NOT NULL
                                AND to_regclass('dashboard_packageservice') IS NULL THEN
                                ALTER TABLE packages_packageservice RENAME TO dashboard_packageservice;
                            END IF;
                        END $$;
                    """,
                    reverse_sql="""
                        DO $$
                        BEGIN
                            IF to_regclass('dashboard_eventpackage') IS NOT NULL
                                AND to_regclass('packages_eventpackage') IS NULL THEN
                                ALTER TABLE dashboard_eventpackage RENAME TO packages_eventpackage;
                            END IF;

                            IF to_regclass('dashboard_packageservice') IS NOT NULL
                                AND to_regclass('packages_packageservice') IS NULL THEN
                                ALTER TABLE dashboard_packageservice RENAME TO packages_packageservice;
                            END IF;
                        END $$;
                    """,
                ),
            ],
            state_operations=[
                migrations.AlterModelTable(
                    name='eventpackage',
                    table='dashboard_eventpackage',
                ),
                migrations.AlterModelTable(
                    name='packageservice',
                    table='dashboard_packageservice',
                ),
            ],
        ),
    ]