
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from dashboard.models import Event, Service, Seller
from packages.models import CatalogPackage, EventPackage


class Booking(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    class ItemType(models.TextChoices):
        EVENT = "EVENT", "Event"
        SERVICE = "SERVICE", "Service"
        CATALOG_PACKAGE = "CATALOG_PACKAGE", "Published Package"
        CUSTOM_PACKAGE = "CUSTOM_PACKAGE", "Custom Package"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    item_type = models.CharField(
        max_length=20,
        choices=ItemType.choices,
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_bookings",
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_bookings",
    )

    catalog_package = models.ForeignKey(
        CatalogPackage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_bookings",
    )

    package_event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="package_bookings",
    )

    seller = models.ForeignKey(
        Seller,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_bookings",
    )

    package_services = models.ManyToManyField(
        Service,
        blank=True,
        related_name="package_bookings",
    )

    custom_package = models.ForeignKey(
        EventPackage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_bookings",
    )

    booking_date = models.DateField()
    booking_end_date = models.DateField(null=True, blank=True)
    booking_time = models.TimeField(null=True, blank=True)
    guest_count = models.PositiveIntegerField(default=1)
    customer_name = models.CharField(max_length=150, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    add_on_services = models.ManyToManyField(
        Service,
        blank=True,
        related_name="customer_booking_add_ons",
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    # Snapshot of the item's title at the time of booking.
    item_title = models.CharField(max_length=255)

    customer_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    customer_confirmed_at = models.DateTimeField(null=True, blank=True)
    admin_completed_at = models.DateTimeField(null=True, blank=True)
    customer_completion_rejected_at = models.DateTimeField(null=True, blank=True)
    customer_completion_rejection_reason = models.TextField(blank=True)
    customer_completion_proof = models.FileField(
        upload_to="completion_proofs/",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        item_type="EVENT",
                        event__isnull=False,
                        service__isnull=True,
                        catalog_package__isnull=True,
                        custom_package__isnull=True,
                    )
                    | Q(
                        item_type="SERVICE",
                        event__isnull=True,
                        service__isnull=False,
                        catalog_package__isnull=True,
                        custom_package__isnull=True,
                    )
                    | Q(
                        item_type="CATALOG_PACKAGE",
                        event__isnull=True,
                        service__isnull=True,
                        catalog_package__isnull=False,
                        custom_package__isnull=True,
                    )
                    | Q(
                        item_type="CUSTOM_PACKAGE",
                        event__isnull=True,
                        service__isnull=True,
                        catalog_package__isnull=True,
                        custom_package__isnull=False,
                    )
                ),
                name="booking_exactly_one_item",
            ),
        ]

    def __str__(self):
        return f"Booking #{self.pk} - {self.item_title}"

    @property
    def seller_display_name(self):
        if self.seller and self.seller.business_name:
            return self.seller.business_name
        if self.package_event and self.package_event.seller and self.package_event.seller.business_name:
            return self.package_event.seller.business_name
        if self.event and self.event.seller and self.event.seller.business_name:
            return self.event.seller.business_name
        if self.service and self.service.seller and self.service.seller.business_name:
            return self.service.seller.business_name
        if self.catalog_package and self.catalog_package.seller and self.catalog_package.seller.business_name:
            return self.catalog_package.seller.business_name
        if (
            self.custom_package
            and self.custom_package.event
            and self.custom_package.event.seller
            and self.custom_package.event.seller.business_name
        ):
            return self.custom_package.event.seller.business_name
        return "Multiple / unassigned"

    @property
    def payment_reference(self):
        try:
            attempt = getattr(self, "payment_attempt", None)
            if attempt:
                return attempt.payment_id or attempt.order_id or "—"
        except Exception:
            pass
        return "—"


class SellerUnavailableDate(models.Model):
    seller = models.ForeignKey(
        Seller,
        on_delete=models.CASCADE,
        related_name="unavailable_dates",
    )
    date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["seller", "date"],
                name="unique_seller_unavailable_date",
            ),
        ]


class BookingDateReservation(models.Model):
    seller = models.ForeignKey(
        Seller,
        on_delete=models.PROTECT,
        related_name="booking_date_reservations",
    )
    date = models.DateField()
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="date_reservations",
    )
    payment_receipt = models.CharField(max_length=40, null=True, blank=True)
    hold_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["seller", "date"],
                name="unique_seller_booking_date",
            ),
            models.CheckConstraint(
                condition=(
                    Q(booking__isnull=False, payment_receipt__isnull=True)
                    | Q(booking__isnull=True, payment_receipt__isnull=False)
                ),
                name="booking_reservation_has_booking_or_payment",
            ),
        ]


class PackageReview(models.Model):
    package = models.ForeignKey(
        CatalogPackage,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name="package_review",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="package_reviews",
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name="package_review_rating_1_to_5",
            ),
        ]

    def __str__(self):
        return f"{self.package.title} — {self.rating}/5"


class BookingSellerDecision(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="seller_decisions",
    )
    seller = models.ForeignKey(
        Seller,
        on_delete=models.PROTECT,
        related_name="booking_decisions",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    rejection_reason = models.TextField(blank=True)
    seller_completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "seller"],
                name="unique_booking_seller_decision",
            ),
        ]


def ensure_booking_seller_decisions(booking):
    seller_ids = set()
    if booking.seller_id:
        seller_ids.add(booking.seller_id)
    if booking.service_id:
        service_seller_id = booking.service.seller_id
        if service_seller_id:
            seller_ids.add(service_seller_id)
    if booking.event_id:
        event_seller_id = booking.event.seller_id
        if event_seller_id:
            seller_ids.add(event_seller_id)
    if booking.package_event_id:
        event_seller_id = booking.package_event.seller_id
        if event_seller_id:
            seller_ids.add(event_seller_id)
    if booking.catalog_package_id:
        seller_ids.add(booking.catalog_package.seller_id)
    if booking.custom_package_id:
        seller_ids.update(
            seller_id or service_seller_id
            for seller_id, service_seller_id in (
                booking.custom_package.package_services
                .filter(
                    Q(seller_id__isnull=False)
                    | Q(service__seller_id__isnull=False)
                )
                .values_list("seller_id", "service__seller_id")
            )
        )
    if booking.package_services.exists():
        seller_ids.update(
            booking.package_services
            .filter(seller_id__isnull=False)
            .values_list("seller_id", flat=True)
        )

    BookingSellerDecision.objects.bulk_create(
        [
            BookingSellerDecision(booking=booking, seller_id=seller_id)
            for seller_id in seller_ids
        ],
        ignore_conflicts=True,
    )


class Favourite(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favourites",
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_favourites",
    )

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_favourites",
    )

    catalog_package = models.ForeignKey(
        CatalogPackage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="user_favourites",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        event__isnull=False,
                        service__isnull=True,
                        catalog_package__isnull=True,
                    )
                    | Q(
                        event__isnull=True,
                        service__isnull=False,
                        catalog_package__isnull=True,
                    )
                    | Q(
                        event__isnull=True,
                        service__isnull=True,
                        catalog_package__isnull=False,
                    )
                ),
                name="favourite_exactly_one_item",
            ),
            models.UniqueConstraint(
                fields=["user", "event"],
                condition=Q(event__isnull=False),
                name="unique_user_favourite_event",
            ),
            models.UniqueConstraint(
                fields=["user", "service"],
                condition=Q(service__isnull=False),
                name="unique_user_favourite_service",
            ),
            models.UniqueConstraint(
                fields=["user", "catalog_package"],
                condition=Q(catalog_package__isnull=False),
                name="unique_user_favourite_catalog_package",
            ),
        ]

    def __str__(self):
        return f"Favourite #{self.pk} - User #{self.user_id}"
