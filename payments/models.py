from decimal import Decimal

from django.conf import settings
from django.db import models

from bookings.models import Booking
from packages.models import CatalogPackage, EventPackage


class PackagePaymentAttempt(models.Model):
    class Status(models.TextChoices):
        CREATED = "CREATED", "Created"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="package_payment_attempts",
    )
    package = models.ForeignKey(
        CatalogPackage,
        on_delete=models.PROTECT,
        related_name="payment_attempts",
        null=True,
        blank=True,
    )
    custom_package = models.ForeignKey(
        EventPackage,
        on_delete=models.PROTECT,
        related_name="payment_attempts",
        null=True,
        blank=True,
    )
    booking = models.OneToOneField(
        Booking,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payment_attempt",
    )
    receipt = models.CharField(max_length=40, unique=True)
    order_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )
    payment_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
    )
    amount_paise = models.PositiveBigIntegerField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    booking_date = models.DateField()
    booking_end_date = models.DateField(null=True, blank=True)
    guest_count = models.PositiveIntegerField()
    customer_name = models.CharField(max_length=150)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    customer_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.CREATED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(package__isnull=False, custom_package__isnull=True)
                    | models.Q(package__isnull=True, custom_package__isnull=False)
                ),
                name="payment_attempt_exactly_one_package",
            ),
        ]

    @property
    def amount(self):
        return Decimal(self.amount_paise) / Decimal("100")


class BookingCancellationRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        PROCESSING = "PROCESSING", "Processing"
        REFUNDED = "REFUNDED", "Refunded"
        REJECTED = "REJECTED", "Rejected"
        FAILED = "FAILED", "Refund failed"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        related_name="cancellation_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="booking_cancellation_requests",
    )
    reason = models.TextField(max_length=1000)
    admin_note = models.TextField(blank=True)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2)
    refund_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking"],
                condition=models.Q(
                    status__in=["REQUESTED", "PROCESSING", "FAILED"]
                ),
                name="one_open_booking_cancellation_request",
            ),
        ]


class SellerEarning(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        related_name="seller_earnings",
    )
    seller = models.ForeignKey(
        "dashboard.Seller",
        on_delete=models.PROTECT,
        related_name="earnings",
    )
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2)
    seller_amount = models.DecimalField(max_digits=12, decimal_places=2)
    available_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    payout_request = models.ForeignKey(
        "PayoutRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="earnings",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "seller"],
                name="unique_booking_seller_earning",
            ),
        ]


class PayoutRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        PAID = "PAID", "Paid"
        REJECTED = "REJECTED", "Rejected"

    seller = models.ForeignKey(
        "dashboard.Seller",
        on_delete=models.PROTECT,
        related_name="payout_requests",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    payment_method = models.CharField(max_length=80, blank=True)
    payment_reference = models.CharField(max_length=150, blank=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
