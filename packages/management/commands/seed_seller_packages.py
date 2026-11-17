from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.models import User

<<<<<<< HEAD
from admin_panel.models import Event, Seller, Service
=======
from dashboard.models import Event, Seller, Service
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
from packages.models import CatalogPackage, CatalogPackageItem


PACKAGE_PLANS = (
    ("Essential Celebration", 2),
    ("Signature Experience", 3),
    ("Premium Event", 3),
    ("Elegant Gathering", 2),
    ("Complete Celebration", 3),
)

SAMPLE_SERVICE_PRICES = {
    "catering": Decimal("15000.00"),
    "photography": Decimal("15000.00"),
    "videography": Decimal("18000.00"),
    "floral decoration": Decimal("12000.00"),
    "stage and venue decor": Decimal("25000.00"),
    "dj and sound": Decimal("12000.00"),
    "event lighting": Decimal("10000.00"),
    "bridal makeup": Decimal("8000.00"),
    "mehndi artist": Decimal("5000.00"),
    "wedding cake": Decimal("4000.00"),
    "live music": Decimal("15000.00"),
    "event transportation": Decimal("10000.00"),
}
DEFAULT_SAMPLE_SERVICE_PRICE = Decimal("5000.00")


def sample_service_price(service):
    if service.price > 0:
        return service.price
    return SAMPLE_SERVICE_PRICES.get(
        service.name.strip().casefold(),
        DEFAULT_SAMPLE_SERVICE_PRICE,
    )


class Command(BaseCommand):
    help = "Create up to five sample packages for each seller profile."

    def handle(self, *args, **options):
        sellers = list(Seller.objects.order_by("pk"))
        incomplete_seller_count = User.objects.filter(
            profile__role="SELLER",
            seller_profile__isnull=True,
        ).count()
        if not sellers:
            self.stdout.write(self.style.WARNING("No seller business profiles found."))
            return

        events = list(
            Event.objects.filter(seller__isnull=True, is_deleted=False).order_by("pk")
        )
        services = list(
            Service.objects.filter(seller__isnull=True, is_deleted=False).order_by("pk")
        )
        if not events or not services:
            raise CommandError(
                "Add at least one active shared event and service before seeding packages."
            )

        created_count = 0
        updated_price_count = 0
        with transaction.atomic():
            sample_items = CatalogPackageItem.objects.filter(
                package__title__startswith="Sample:",
                package__is_deleted=False,
                selected_price=Decimal("0.00"),
            ).select_related("service")
            for item in sample_items:
                item.selected_price = sample_service_price(item.service)
                item.save(update_fields=["selected_price"])
                updated_price_count += 1

            for seller_index, seller in enumerate(sellers):
                active_count = CatalogPackage.objects.filter(
                    seller=seller,
                    is_deleted=False,
                ).count()
                existing_titles = set(
                    CatalogPackage.objects.filter(seller=seller).values_list(
                        "title", flat=True
                    )
                )

                for plan_index, (plan_name, service_count) in enumerate(PACKAGE_PLANS):
                    if active_count >= len(PACKAGE_PLANS):
                        break

                    title = f"Sample: {plan_name}"
                    suffix = 2
                    while title in existing_titles:
                        title = f"Sample: {plan_name} ({suffix})"
                        suffix += 1

                    event = events[(seller_index + plan_index) % len(events)]
                    service_start = (seller_index + plan_index * 2) % len(services)
                    selected_services = [
                        services[(service_start + offset) % len(services)]
                        for offset in range(min(service_count, len(services)))
                    ]
                    description = (
                        f"A sample {plan_name.lower()} featuring "
                        f"{', '.join(service.name for service in selected_services)} "
                        f"for {event.title}."
                    )

                    package = CatalogPackage.objects.create(
                        seller=seller,
                        title=title,
                        description=description,
                        event=event,
                    )
                    CatalogPackageItem.objects.bulk_create(
                        [
                            CatalogPackageItem(
                                package=package,
                                service=service,
                                selected_price=sample_service_price(service),
                            )
                            for service in selected_services
                        ]
                    )
                    existing_titles.add(title)
                    active_count += 1
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} sample packages for {len(sellers)} sellers."
            )
        )
        if updated_price_count:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated sample prices for {updated_price_count} package services."
                )
            )
        if incomplete_seller_count:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {incomplete_seller_count} seller account"
                    f"{'s' if incomplete_seller_count != 1 else ''} without a business profile."
                )
            )
