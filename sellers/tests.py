from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from dashboard.models import Event, Profile, Seller, Service
from packages.models import CatalogPackage, CatalogPackageItem


class SellerSharedCatalogWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="shared-catalog-seller",
            password="test-password",
        )
        Profile.objects.create(user=self.user, role="SELLER")
        self.seller = Seller.objects.create(
            user=self.user,
            business_name="Shared Catalog Seller",
        )
        self.admin_event = Event.objects.create(
            title="Admin Wedding Event",
            description="Shared wedding event",
            location="Patna",
            event_date="2030-05-10",
            price=2000,
        )
        self.admin_service = Service.objects.create(
            name="Admin Photography",
            description="Shared photography service",
            price=500,
        )
        self.private_event = Event.objects.create(
            title="Seller-owned Event",
            description="Legacy seller event",
            location="Delhi",
            event_date="2030-06-10",
            price=1000,
            seller=self.seller,
        )
        self.private_service = Service.objects.create(
            name="Seller-owned Service",
            description="Legacy seller service",
            price=300,
            seller=self.seller,
        )
        self.client.force_login(self.user)

    def test_dashboard_shows_shared_catalog_counts_without_event_service_sections(self):
        response = self.client.get(reverse("seller-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["events_count"], 1)
        self.assertEqual(response.context["services_count"], 1)
        self.assertContains(response, "Available events")
        self.assertContains(response, "Available services")
        self.assertNotContains(response, "My Events")
        self.assertNotContains(response, "My Services")
        self.assertNotContains(response, "Manage events")
        self.assertNotContains(response, "Manage services")

    def test_seller_can_create_package_from_admin_catalog_items(self):
        response = self.client.get(reverse("seller-create-package"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin_event.title)
        self.assertContains(response, self.admin_service.name)
        self.assertNotContains(response, self.private_event.title)
        self.assertNotContains(response, self.private_service.name)

        response = self.client.post(
            reverse("seller-create-package"),
            {
                "title": "Seller-curated Wedding",
                "description": "A package using shared catalog content",
                "event": self.admin_event.pk,
                "services": [self.admin_service.pk],
                f"price_{self.admin_service.pk}": "450.00",
            },
        )

        self.assertRedirects(response, reverse("seller-packages"))
        package = CatalogPackage.objects.get(
            title="Seller-curated Wedding",
            seller=self.seller,
        )
        self.assertEqual(package.event, self.admin_event)
        self.assertEqual(
            package.package_items.get().selected_price,
            450,
        )

        dashboard_response = self.client.get(reverse("seller-dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(dashboard_response.context["packages_count"], 1)
        self.assertContains(dashboard_response, package.title)

    def test_seller_event_and_service_management_routes_are_removed(self):
        for path in ("/seller/events/", "/seller/services/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
