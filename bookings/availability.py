from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
<<<<<<< HEAD
from admin_panel.models import Seller
=======

from admin_panel.models import Seller
from packages.models import CatalogPackage, EventPackage
>>>>>>> acb5f62 (Third commit)

from .models import Booking, BookingDateReservation, SellerUnavailableDate


class BookingUnavailableError(Exception):
    pass


def seller_ids_for_item(item_type, item):
    seller_ids = set()
    if item_type == "EVENT" and item.seller_id:
        seller_ids.add(item.seller_id)
    elif item_type == "SERVICE" and item.seller_id:
        seller_ids.add(item.seller_id)
    elif item_type == "CATALOG_PACKAGE":
        if item.seller_id:
            seller_ids.add(item.seller_id)
        seller_ids.update(
            item.package_items.exclude(service__seller_id=None)
            .values_list("service__seller_id", flat=True)
        )
    elif item_type == "CUSTOM_PACKAGE":
        if item.event and item.event.seller_id:
            seller_ids.add(item.event.seller_id)
        seller_ids.update(
            seller_id or service_seller_id
            for seller_id, service_seller_id in (
                item.package_services.filter(
                    Q(seller_id__isnull=False)
                    | Q(service__seller_id__isnull=False)
                ).values_list("seller_id", "service__seller_id")
            )
        )
    return sorted(seller_ids)


def unavailable_dates_for_sellers(
    seller_ids,
    start_date,
    end_date,
    *,
    exclude_booking_id=None,
):
    if not seller_ids:
        return []
    blocked_dates = set(
        SellerUnavailableDate.objects.filter(
            seller_id__in=seller_ids,
            date__range=(start_date, end_date),
        ).values_list("date", flat=True)
    )
    blocked_dates.update(
        BookingDateReservation.objects.filter(
            seller_id__in=seller_ids,
            date__range=(start_date, end_date),
        )
        .filter(
            booking__isnull=False,
        )
        .values_list("date", flat=True)
    )
    now = timezone.now()
    blocked_dates.update(
        BookingDateReservation.objects.filter(
            seller_id__in=seller_ids,
            date__range=(start_date, end_date),
            booking__isnull=True,
            hold_expires_at__gt=now,
        ).values_list("date", flat=True)
    )
    existing_bookings = Booking.objects.filter(
        Q(seller_id__in=seller_ids)
        | Q(event__seller_id__in=seller_ids)
        | Q(service__seller_id__in=seller_ids)
        | Q(package_event__seller_id__in=seller_ids)
        | Q(catalog_package__seller_id__in=seller_ids)
        | Q(catalog_package__package_items__service__seller_id__in=seller_ids)
        | Q(package_services__seller_id__in=seller_ids)
        | Q(custom_package__event__seller_id__in=seller_ids)
        | Q(custom_package__package_services__seller_id__in=seller_ids)
        | Q(
            custom_package__package_services__service__seller_id__in=seller_ids
        ),
        status__in=[
            Booking.Status.PENDING,
            Booking.Status.CONFIRMED,
            Booking.Status.REJECTED,
        ],
        booking_date__lte=end_date,
    ).filter(
        Q(booking_end_date__isnull=True, booking_date__gte=start_date)
        | Q(booking_end_date__gte=start_date)
    )
    if exclude_booking_id is not None:
        existing_bookings = existing_bookings.exclude(pk=exclude_booking_id)
    for booking_start, booking_end in existing_bookings.values_list(
        "booking_date",
        "booking_end_date",
    ).distinct():
        last_day = min(booking_end or booking_start, end_date)
        first_day = max(booking_start, start_date)
        for offset in range((last_day - first_day).days + 1):
            blocked_dates.add(first_day + timedelta(days=offset))
    return sorted(blocked_dates)


def assert_dates_available(
    seller_ids,
    start_date,
    end_date,
    *,
    exclude_booking_id=None,
):
    unavailable = unavailable_dates_for_sellers(
        seller_ids,
        start_date,
        end_date,
        exclude_booking_id=exclude_booking_id,
    )
    if unavailable:
        raise BookingUnavailableError(
            "The seller is unavailable for one or more selected dates."
        )


def reserve_booking_dates(
    seller_ids,
    start_date,
    end_date,
    *,
    booking=None,
    payment_receipt=None,
    hold_minutes=30,
):
    if not seller_ids:
        return
    if end_date < start_date or (end_date - start_date).days > 365:
        raise BookingUnavailableError("Choose a valid date range.")

    with transaction.atomic():
        list(
            Seller.objects.select_for_update()
            .filter(pk__in=seller_ids)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        now = timezone.now()
        BookingDateReservation.objects.filter(
            seller_id__in=seller_ids,
            date__range=(start_date, end_date),
            booking__isnull=True,
            hold_expires_at__lte=now,
        ).delete()

        assert_dates_available(
            seller_ids,
            start_date,
            end_date,
            exclude_booking_id=booking.pk if booking else None,
        )

        date_count = (end_date - start_date).days + 1
        reservations = [
            BookingDateReservation(
                seller_id=seller_id,
                date=start_date + timedelta(days=offset),
                booking=booking,
                payment_receipt=payment_receipt,
                hold_expires_at=(
                    None
                    if booking
                    else now + timedelta(minutes=hold_minutes)
                ),
            )
            for seller_id in seller_ids
            for offset in range(date_count)
        ]
        try:
            with transaction.atomic():
                BookingDateReservation.objects.bulk_create(reservations)
        except IntegrityError as error:
            raise BookingUnavailableError(
                "The selected date is no longer available."
            ) from error


def attach_reservations_to_booking(payment_receipt, booking):
    reservations = BookingDateReservation.objects.filter(
        payment_receipt=payment_receipt,
        booking__isnull=True,
    )
    if not reservations.exists():
        raise BookingUnavailableError(
            "The booking date hold expired. Please contact support."
        )
    reservations.update(
        booking=booking,
        payment_receipt=None,
        hold_expires_at=None,
    )


def release_booking_reservations(booking):
    BookingDateReservation.objects.filter(booking=booking).delete()
