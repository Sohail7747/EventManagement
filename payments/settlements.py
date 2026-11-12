from decimal import Decimal, ROUND_HALF_UP

from .models import SellerEarning
from bookings.models import ensure_booking_seller_decisions


COMMISSION_RATE = Decimal("0.10")


def create_booking_earnings(booking):
    ensure_booking_seller_decisions(booking)
    sellers = list(
        booking.seller_decisions
        .select_related("seller")
        .order_by("seller_id")
    )
    if not sellers:
        return

    gross_cents = int(
        (booking.total_price * 100).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    commission_cents = int(
        (Decimal(gross_cents) * COMMISSION_RATE).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )
    seller_pool_cents = gross_cents - commission_cents
    each_seller_cents, seller_remainder = divmod(
        seller_pool_cents,
        len(sellers),
    )
    each_commission_cents, commission_remainder = divmod(
        commission_cents,
        len(sellers),
    )

    for index, decision in enumerate(sellers):
        SellerEarning.objects.get_or_create(
            booking=booking,
            seller=decision.seller,
            defaults={
                "seller_amount": Decimal(
                    each_seller_cents + (index < seller_remainder)
                ) / 100,
                "commission_amount": Decimal(
                    each_commission_cents + (index < commission_remainder)
                ) / 100,
                "available_on": booking.booking_end_date or booking.booking_date,
            },
        )
