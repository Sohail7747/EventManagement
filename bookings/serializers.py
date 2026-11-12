
from rest_framework import serializers

from .models import Booking, Favourite


class BookingSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "item_type",
            "event",
            "service",
            "catalog_package",
            "package_event",
            "seller",
            "package_services",
            "custom_package",
            "booking_date",
            "booking_end_date",
            "booking_time",
            "guest_count",
            "customer_name",
            "customer_email",
            "customer_phone",
            "total_price",
            "item_title",
            "customer_notes",
            "status",
            "rejection_reason",
            "status_display",
            "created_at",
            "updated_at",
            "cancelled_at",
        ]
        read_only_fields = [
            "id",
            "event",
            "service",
            "catalog_package",
            "package_event",
            "seller",
            "package_services",
            "custom_package",
            "customer_name",
            "customer_email",
            "customer_phone",
            "total_price",
            "item_title",
            "status",
            "rejection_reason",
            "created_at",
            "updated_at",
            "cancelled_at",
        ]


class FavouriteSerializer(serializers.ModelSerializer):
    item_type = serializers.SerializerMethodField()
    item_title = serializers.SerializerMethodField()

    class Meta:
        model = Favourite
        fields = [
            "id",
            "event",
            "service",
            "catalog_package",
            "item_type",
            "item_title",
            "created_at",
        ]
        read_only_fields = fields

    def get_item_type(self, obj):
        if obj.event_id:
            return "EVENT"
        if obj.service_id:
            return "SERVICE"
        if obj.catalog_package_id:
            return "CATALOG_PACKAGE"
        return None

    def get_item_title(self, obj):
        if obj.event_id:
            return obj.event.title
        if obj.service_id:
            return obj.service.name
        if obj.catalog_package_id:
            return obj.catalog_package.title
        return None
