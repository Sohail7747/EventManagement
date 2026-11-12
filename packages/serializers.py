
from rest_framework import serializers

from admin_panel.models import Event, Service
from .models import EventPackage, PackageService


class EventOptionSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "location",
            "event_date",
            "price",
            "image",
        ]

    def get_image(self, obj):
        request = self.context.get("request")

        if obj.image:
            image_url = obj.image.url

            if request:
                return request.build_absolute_uri(image_url)

            return image_url

        return None


class ServiceOptionSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(
        source="seller.business_name",
        read_only=True,
        default="Unassigned",
    )

    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "description",
            "price",
            "seller",
            "seller_name",
        ]


class PackageServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(
        source="service.name",
        read_only=True,
    )

    seller_name = serializers.SerializerMethodField()

    class Meta:
        model = PackageService
        fields = [
            "id",
            "service",
            "service_name",
            "seller_name",
            "selected_price",
        ]

    def get_seller_name(self, obj):
        seller = obj.seller or obj.service.seller
        return seller.business_name if seller else "Unassigned"


class EventPackageSerializer(serializers.ModelSerializer):
    event_name = serializers.CharField(
        source="event.title",
        read_only=True,
        allow_null=True,
    )

    event_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    package_services = PackageServiceSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = EventPackage
        fields = [
            "id",
            "user",
            "package_title",
            "event",
            "event_name",
            "event_date",
            "event_end_date",
            "guest_count",
            "event_price",
            "package_services",
            "total_cost",
            "created_at",
        ]
        read_only_fields = fields
