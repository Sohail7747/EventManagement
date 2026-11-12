from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


def backfill_paid_earnings(apps, schema_editor):
    database = schema_editor.connection.alias
    PaymentAttempt = apps.get_model("payments", "PackagePaymentAttempt")
    Booking = apps.get_model("bookings", "Booking")
    SellerDecision = apps.get_model("bookings", "BookingSellerDecision")
    SellerEarning = apps.get_model("payments", "SellerEarning")

    for attempt in (
        PaymentAttempt.objects.using(database)
        .filter(status="PAID", booking__isnull=False)
        .select_related("booking")
        .iterator()
    ):
        booking = attempt.booking
        seller_ids = set()
        if booking.seller_id:
            seller_ids.add(booking.seller_id)
        if booking.service_id:
            service = booking.service
            if service.seller_id:
                seller_ids.add(service.seller_id)
        if booking.event_id:
            event = booking.event
            if event.seller_id:
                seller_ids.add(event.seller_id)
        if booking.package_event_id:
            package_event = booking.package_event
            if package_event.seller_id:
                seller_ids.add(package_event.seller_id)
        if booking.catalog_package_id:
            seller_ids.add(booking.catalog_package.seller_id)
        if booking.custom_package_id:
            seller_ids.update(
                booking.custom_package.package_services
                .filter(service__seller_id__isnull=False)
                .values_list("service__seller_id", flat=True)
            )
        seller_ids.update(
            booking.package_services
            .filter(seller_id__isnull=False)
            .values_list("seller_id", flat=True)
        )
        if not seller_ids:
            continue

        earnings_cents = int(
            (booking.total_price * 100).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        commission_cents = int(
            (Decimal(earnings_cents) * Decimal("0.10")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
        seller_pool_cents = earnings_cents - commission_cents
        seller_amount, seller_remainder = divmod(
            seller_pool_cents,
            len(seller_ids),
        )
        commission_amount, commission_remainder = divmod(
            commission_cents,
            len(seller_ids),
        )

        for index, seller_id in enumerate(sorted(seller_ids)):
            decision_status = (
                "ACCEPTED" if booking.status in {"CONFIRMED", "COMPLETED"}
                else "REJECTED" if booking.status == "REJECTED"
                else "PENDING"
            )
            SellerDecision.objects.using(database).get_or_create(
                booking_id=booking.pk,
                seller_id=seller_id,
                defaults={
                    "status": decision_status,
                    "rejection_reason": (
                        booking.rejection_reason
                        if decision_status == "REJECTED"
                        else ""
                    ),
                },
            )
            earning, created = SellerEarning.objects.using(database).get_or_create(
                booking_id=booking.pk,
                seller_id=seller_id,
                defaults={
                    "seller_amount": Decimal(
                        seller_amount + (index < seller_remainder)
                    ) / 100,
                    "commission_amount": Decimal(
                        commission_amount + (index < commission_remainder)
                    ) / 100,
                    "available_on": (
                        booking.booking_end_date or booking.booking_date
                    ),
                },
            )
            if created:
                SellerEarning.objects.using(database).filter(
                    pk=earning.pk
                ).update(created_at=attempt.created_at)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0002_payoutrequest_sellerearning_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_paid_earnings,
            migrations.RunPython.noop,
        ),
    ]
