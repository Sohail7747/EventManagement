
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from dashboard.models import Event, Service


class EventPackage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="event_packages"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="packages"
    )
    package_title = models.CharField(max_length=200, blank=True, default="")
    event_date = models.DateField()
    event_end_date = models.DateField(null=True, blank=True)
    guest_count = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    event_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    total_cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dashboard_eventpackage"

    def __str__(self):
        title = self.package_title or (
            self.event.title if self.event else "Custom package"
        )
        return f"Package #{self.id} - {title}"

    @property
    def total_price(self):
        return self.total_cost


class PackageService(models.Model):
    package = models.ForeignKey(
        EventPackage,
        on_delete=models.CASCADE,
        related_name="package_services"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="package_selections"
    )
    seller = models.ForeignKey(
        "dashboard.Seller",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="custom_package_services",
    )
    selected_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        db_table = "dashboard_packageservice"
        constraints = [
            models.UniqueConstraint(
                fields=["package", "service"],
                name="unique_service_per_event_package"
            )
        ]

    def __str__(self):
        return f"{self.service.name} - Package #{self.package_id}"


class CatalogPackage(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    is_deleted = models.BooleanField(default=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="catalog_packages"
    )
    seller = models.ForeignKey(
        "dashboard.Seller",
        on_delete=models.PROTECT,
        related_name="catalog_packages"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        from decimal import Decimal

        return sum(
            (item.selected_price for item in self.package_items.all()),
            Decimal("0.00")
        )


class CatalogPackageItem(models.Model):
    package = models.ForeignKey(
        CatalogPackage,
        on_delete=models.CASCADE,
        related_name="package_items"
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="catalog_package_items"
    )
    selected_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["package", "service"],
                name="unique_service_per_catalog_package"
            )
        ]

    def __str__(self):
        return f"{self.service.name} - {self.package.title}"


class ServiceQuoteRequest(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="service_quote_requests",
    )
    service_name = models.CharField(max_length=200)
    event_date = models.DateField(null=True, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.service_name} quote requested by {self.customer}"


class ServiceQuote(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Awaiting response"
        QUOTED = "QUOTED", "Quote provided"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    request = models.ForeignKey(
        ServiceQuoteRequest,
        on_delete=models.CASCADE,
        related_name="quotes",
    )
    seller = models.ForeignKey(
        "dashboard.Seller",
        on_delete=models.CASCADE,
        related_name="service_quotes",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    quoted_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    message = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["request", "seller"],
                name="unique_seller_service_quote",
            ),
        ]

    def __str__(self):
        return f"{self.request.service_name} quote from {self.seller}"
