from decimal import Decimal

from django.db import migrations, models


def move_payment_data(apps, schema_editor):
    OldAttempt = apps.get_model("bookings", "PackagePaymentAttempt")
    PaymentAttempt = apps.get_model("payments", "PackagePaymentAttempt")
    Booking = apps.get_model("bookings", "Booking")
    database = schema_editor.connection.alias
    migrated_booking_ids = set()

    for old_attempt in OldAttempt.objects.using(database).all().iterator():
        new_attempt = PaymentAttempt.objects.using(database).create(
            user_id=old_attempt.user_id,
            package_id=old_attempt.package_id,
            booking_id=old_attempt.booking_id,
            receipt=old_attempt.receipt,
            order_id=old_attempt.order_id,
            payment_id=old_attempt.payment_id,
            amount_paise=old_attempt.amount_paise,
            total_price=old_attempt.total_price,
            booking_date=old_attempt.booking_date,
            booking_end_date=old_attempt.booking_end_date,
            guest_count=old_attempt.guest_count,
            customer_name=old_attempt.customer_name,
            customer_email=old_attempt.customer_email,
            customer_phone=old_attempt.customer_phone,
            customer_notes=old_attempt.customer_notes,
            status=old_attempt.status,
        )
        PaymentAttempt.objects.using(database).filter(pk=new_attempt.pk).update(
            created_at=old_attempt.created_at
        )
        if old_attempt.booking_id is not None:
            migrated_booking_ids.add(old_attempt.booking_id)

    bookings = Booking.objects.using(database).exclude(
        models.Q(advance_amount=Decimal("0.00"))
        & models.Q(payment_id="")
        & models.Q(payment_status="")
    )
    for booking in bookings.iterator():
        if booking.pk in migrated_booking_ids:
            continue
        if booking.catalog_package_id is None:
            raise RuntimeError(
                f"Booking {booking.pk} has payment data but no catalog package."
            )

        status = (
            "PAID"
            if booking.payment_id or booking.payment_status
            else "CREATED"
        )
        amount_paise = int(booking.advance_amount * 100)
        PaymentAttempt.objects.using(database).create(
            user_id=booking.user_id,
            package_id=booking.catalog_package_id,
            booking_id=booking.pk,
            receipt=f"legacy-booking-{booking.pk}",
            payment_id=booking.payment_id or None,
            amount_paise=amount_paise,
            total_price=booking.total_price,
            booking_date=booking.booking_date,
            booking_end_date=booking.booking_end_date,
            guest_count=booking.guest_count,
            customer_name=booking.customer_name,
            customer_email=booking.customer_email,
            customer_phone=booking.customer_phone,
            customer_notes=booking.customer_notes,
            status=status,
        )


def restore_payment_data(apps, schema_editor):
    PaymentAttempt = apps.get_model("payments", "PackagePaymentAttempt")
    OldAttempt = apps.get_model("bookings", "PackagePaymentAttempt")
    Booking = apps.get_model("bookings", "Booking")
    database = schema_editor.connection.alias

    for attempt in PaymentAttempt.objects.using(database).iterator():
        restored_attempt = OldAttempt.objects.using(database).create(
            user_id=attempt.user_id,
            package_id=attempt.package_id,
            booking_id=attempt.booking_id,
            receipt=attempt.receipt,
            order_id=attempt.order_id,
            payment_id=attempt.payment_id,
            amount_paise=attempt.amount_paise,
            total_price=attempt.total_price,
            booking_date=attempt.booking_date,
            booking_end_date=attempt.booking_end_date or attempt.booking_date,
            guest_count=attempt.guest_count,
            customer_name=attempt.customer_name,
            customer_email=attempt.customer_email,
            customer_phone=attempt.customer_phone,
            customer_notes=attempt.customer_notes,
            status=attempt.status,
            created_at=attempt.created_at,
        )
        OldAttempt.objects.using(database).filter(
            pk=restored_attempt.pk
        ).update(created_at=attempt.created_at)
        if attempt.booking_id is not None:
            Booking.objects.using(database).filter(pk=attempt.booking_id).update(
                advance_amount=(
                    Decimal(attempt.amount_paise) / Decimal("100")
                ),
                payment_id=attempt.payment_id or "",
                payment_status=(
                    "ADVANCE_PAID" if attempt.status == "PAID" else ""
                ),
            )


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0005_booking_payment_id_booking_payment_status_and_more"),
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(move_payment_data, restore_payment_data),
        migrations.RemoveField(
            model_name="booking",
            name="advance_amount",
        ),
        migrations.RemoveField(
            model_name="booking",
            name="payment_id",
        ),
        migrations.RemoveField(
            model_name="booking",
            name="payment_status",
        ),
        migrations.DeleteModel(
            name="PackagePaymentAttempt",
        ),
    ]
