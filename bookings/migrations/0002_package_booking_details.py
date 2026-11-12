from django.db import migrations, models
import django.db.models.deletion


def populate_package_booking_details(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    CatalogPackageItem = apps.get_model("packages", "CatalogPackageItem")
    database = schema_editor.connection.alias

    for booking in (
        Booking.objects.using(database)
        .filter(item_type="CATALOG_PACKAGE")
        .select_related("catalog_package")
        .iterator()
    ):
        package = booking.catalog_package
        booking.package_event_id = package.event_id
        booking.seller_id = package.seller_id
        booking.save(
            using=database,
            update_fields=["package_event", "seller"],
        )
        service_ids = CatalogPackageItem.objects.using(database).filter(
            package_id=package.pk,
        ).values_list("service_id", flat=True)
        booking.package_services.set(service_ids)


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0001_initial"),
        ("dashboard", "0006_service_image"),
        ("packages", "0003_alter_eventpackage_table_alter_packageservice_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="booking_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="package_event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="package_bookings",
                to="dashboard.event",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="seller",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="customer_bookings",
                to="dashboard.seller",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="package_services",
            field=models.ManyToManyField(
                blank=True,
                related_name="package_bookings",
                to="dashboard.service",
            ),
        ),
        migrations.RunPython(
            populate_package_booking_details,
            migrations.RunPython.noop,
        ),
    ]
