from decimal import Decimal, ROUND_HALF_UP

from .models import SellerEarning
from bookings.models import ensure_booking_seller_decisions


COMMISSION_RATE = Decimal("0.10")


def allocate_cents(total_cents, weights):
    weight_total = sum(weights.values())
    if weight_total == 0:
        weights = {seller_id: 1 for seller_id in weights}
        weight_total = len(weights)

    allocations = {}
    remainders = []
    allocated_cents = 0
    for seller_id, weight in weights.items():
        amount, remainder = divmod(total_cents * weight, weight_total)
        allocations[seller_id] = amount
        allocated_cents += amount
        remainders.append((remainder, seller_id))

    remainders.sort(key=lambda value: (-value[0], value[1]))
    for _, seller_id in remainders[:total_cents - allocated_cents]:
        allocations[seller_id] += 1
    return allocations


def create_booking_earnings(booking):
    ensure_booking_seller_decisions(booking)
    sellers = list(
        booking.seller_decisions
        .select_related("seller")
        .order_by("seller_id")
    )
    if not sellers:
        return

    seller_weights = {decision.seller_id: 0 for decision in sellers}
    if booking.custom_package_id:
        package_services = (
            booking.custom_package.package_services
            .select_related("service")
            .values_list("seller_id", "service__seller_id", "selected_price")
        )
        for selected_seller_id, service_seller_id, selected_price in package_services:
            seller_id = selected_seller_id or service_seller_id
            if seller_id in seller_weights:
                seller_weights[seller_id] += int(
                    (selected_price * 100).quantize(
                        Decimal("1"),
                        rounding=ROUND_HALF_UP,
                    )
                )

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
    seller_amounts = allocate_cents(seller_pool_cents, seller_weights)
    commission_amounts = allocate_cents(commission_cents, seller_weights)

    for decision in sellers:
        SellerEarning.objects.get_or_create(
            booking=booking,
            seller=decision.seller,
            defaults={
                "seller_amount": Decimal(
                    seller_amounts[decision.seller_id]
                ) / 100,
                "commission_amount": Decimal(
                    commission_amounts[decision.seller_id]
                ) / 100,
                "available_on": booking.booking_end_date or booking.booking_date,
            },
        )
