from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.test import override_settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse

from .models import Event, Profile, Seller, Service, StaticPage
from packages.models import CatalogPackage, CatalogPackageItem


class DashboardOverviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="dashboard-admin",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(self.admin)

    def test_dashboard_renders_analytics_and_six_month_series(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment volume")
        self.assertContains(response, "Platform commission")
        self.assertContains(response, "Booking activity")
        self.assertContains(response, "Account growth")
        self.assertContains(response, "Recent bookings")
        self.assertContains(response, "Review all bookings")
        self.assertContains(response, "No bookings yet")
        self.assertEqual(response.context["payment_volume_total"], 0)
        for key in (
            "monthly_payment_volume",
            "monthly_commissions",
            "monthly_bookings",
            "monthly_users",
            "monthly_sellers",
        ):
            self.assertEqual(len(response.context[key]), 6)

    def test_admin_can_add_shared_events_and_services(self):
        response = self.client.post(
            reverse("event-create"),
            {
                "title": "Shared Admin Event",
                "description": "Event for seller packages",
                "location": "Patna",
                "event_date": "2030-05-10",
                "price": "1200.00",
            },
        )

        self.assertRedirects(response, reverse("admin-events"))
        event = Event.objects.get(title="Shared Admin Event")
        self.assertIsNone(event.seller)
        self.assertEqual(event.price, 0)

        response = self.client.post(
            reverse("service-create"),
            {
                "name": "Shared Admin Service",
                "description": "Service for seller packages",
                "price": "300.00",
            },
        )

        self.assertRedirects(response, reverse("admin-services"))
        service = Service.objects.get(name="Shared Admin Service")
        self.assertIsNone(service.seller)
        self.assertEqual(service.price, 0)

    def test_seed_sample_services_creates_images_visible_to_admin(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = MagicMock()
                response.__enter__.return_value = response
                response.headers.get.return_value = "image/jpeg"
                response.read.return_value = b"\xff\xd8sample image data"
                with patch(
                    "dashboard.management.commands.seed_sample_services.urlopen",
                    return_value=response,
                ) as image_download:
                    call_command("seed_sample_services", stdout=StringIO())
                    call_command("seed_sample_services", stdout=StringIO())
                self.assertEqual(image_download.call_count, 12)

                services = Service.objects.filter(is_deleted=False)
                self.assertEqual(services.count(), 12)

                service = services.get(name="Catering")
                self.assertEqual(service.image.name, "services/catering.jpg")
                self.assertTrue(
                    Path(media_root, service.image.name).is_file()
                )
                self.assertTrue(
                    Path(media_root, "services", "IMAGE_SOURCES.txt").is_file()
                )

                response = self.client.get(reverse("admin-services"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, service.name)
                self.assertContains(response, service.image.url)

    def test_seed_sample_events_creates_images_visible_to_admin(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = MagicMock()
                response.__enter__.return_value = response
                response.headers.get.return_value = "image/jpeg"
                response.read.return_value = b"\xff\xd8sample image data"
                with patch(
                    "dashboard.management.commands.seed_sample_events.urlopen",
                    return_value=response,
                ) as image_download:
                    call_command("seed_sample_events", stdout=StringIO())
                    call_command("seed_sample_events", stdout=StringIO())
                self.assertEqual(image_download.call_count, 15)

                events = Event.objects.filter(is_deleted=False)
                self.assertEqual(events.count(), 15)

                event = events.get(title="Wedding Ceremony")
                self.assertEqual(
                    event.image.name,
                    "events/wedding-ceremony.jpg",
                )
                self.assertTrue(
                    Path(media_root, event.image.name).is_file()
                )
                self.assertTrue(
                    Path(media_root, "events", "IMAGE_SOURCES.txt").is_file()
                )

                response = self.client.get(reverse("admin-events"))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, event.title)
                self.assertContains(response, event.image.url)

    def test_admin_packages_page_is_view_only(self):
        response = self.client.get(reverse("admin-catalog-packages"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Add Package")
        self.assertEqual(self.client.get("/catalog/create/").status_code, 404)

    def test_seed_seller_packages_are_idempotent_and_visible_on_admin_dashboard(self):
        event = Event.objects.create(
            title="Sample Wedding",
            description="Sample event",
            location="Patna",
            event_date="2030-05-10",
            price=0,
        )
        services = [
            Service.objects.create(
                name=f"Sample Service {index}",
                description="Sample service",
                price=100 * index,
            )
            for index in range(1, 4)
        ]
        sellers = [
            Seller.objects.create(
                user=User.objects.create_user(username=f"sample-seller-{index}"),
                business_name=f"Sample Seller {index}",
            )
            for index in range(2)
        ]

        call_command("seed_seller_packages", stdout=StringIO())
        call_command("seed_seller_packages", stdout=StringIO())

        self.assertEqual(CatalogPackage.objects.count(), 10)
        for seller in sellers:
            packages = CatalogPackage.objects.filter(seller=seller)
            self.assertEqual(packages.count(), 5)
            self.assertTrue(
                all(package.package_items.count() > 0 for package in packages)
            )
            self.assertTrue(
                all(package.total_price > 0 for package in packages)
            )

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["packages_count"], 10)
        self.assertContains(response, "Published packages")
        self.assertContains(response, "Sample:")

    def test_deleting_catalog_service_preserves_package_history(self):
        seller_user = User.objects.create_user(
            username="catalog-package-seller",
            password="test-password",
        )
        Profile.objects.create(user=seller_user, role="SELLER")
        seller = Seller.objects.create(
            user=seller_user,
            business_name="Catalog Package Seller",
        )
        event = Event.objects.create(
            title="Catalog Package Event",
            description="An event",
            location="Patna",
            event_date="2030-05-10",
            price="1000.00",
        )
        service = Service.objects.create(
            name="Protected Catalog Service",
            description="A service included in the package",
            price="500.00",
        )
        package = CatalogPackage.objects.create(
            title="Package with Protected Service",
            description="Preserved package history",
            event=event,
            seller=seller,
        )
        package_item = CatalogPackageItem.objects.create(
            package=package,
            service=service,
            selected_price="450.00",
        )

        response = self.client.post(
            reverse("service-delete", args=[service.pk])
        )

        self.assertRedirects(response, reverse("admin-services"))
        service.refresh_from_db()
        self.assertTrue(service.is_deleted)
        package_item.refresh_from_db()
        self.assertEqual(package_item.service, service)
        self.assertEqual(package_item.selected_price, 450)
        self.assertNotContains(
            self.client.get(reverse("admin-services")),
            service.name,
        )
        self.assertNotContains(
            self.client.get(reverse("public-services")),
            service.name,
        )
        self.assertNotContains(
            self.client.get(reverse("public-packages")),
            package.title,
        )

        customer = User.objects.create_user(
            username="catalog-package-customer",
            password="test-password",
        )
        Profile.objects.create(user=customer, role="USER")
        self.client.force_login(customer)
        self.assertEqual(
            self.client.get(
                reverse("package-booking", args=[package.pk])
            ).status_code,
            404,
        )

    def test_deleting_event_preserves_packages_and_blocks_new_bookings(self):
        seller_user = User.objects.create_user(
            username="event-delete-package-seller",
            password="test-password",
        )
        Profile.objects.create(user=seller_user, role="SELLER")
        seller = Seller.objects.create(
            user=seller_user,
            business_name="Event Delete Seller",
        )
        event = Event.objects.create(
            title="Protected Catalog Event",
            description="An event referenced by a package",
            location="Patna",
            event_date="2030-05-10",
            price="1000.00",
        )
        package = CatalogPackage.objects.create(
            title="Package with Protected Event",
            description="Preserved package history",
            event=event,
            seller=seller,
        )
        service = Service.objects.create(
            name="Event Package Service",
            description="A service included in the package",
            price="500.00",
        )
        package_item = CatalogPackageItem.objects.create(
            package=package,
            service=service,
            selected_price="450.00",
        )

        response = self.client.post(
            reverse("event-delete", args=[event.pk])
        )

        self.assertRedirects(response, reverse("admin-events"))
        event.refresh_from_db()
        package.refresh_from_db()
        package_item.refresh_from_db()
        self.assertTrue(event.is_deleted)
        self.assertEqual(package.event, event)
        self.assertEqual(package_item.package, package)
        self.assertNotContains(
            self.client.get(reverse("admin-events")),
            event.title,
        )
        self.assertNotContains(
            self.client.get(reverse("public-events")),
            event.title,
        )
        self.assertNotContains(
            self.client.get(reverse("public-packages")),
            package.title,
        )

        customer = User.objects.create_user(
            username="event-delete-package-customer",
            password="test-password",
        )
        Profile.objects.create(user=customer, role="USER")
        self.client.force_login(customer)
        self.assertEqual(
            self.client.get(
                reverse("package-booking", args=[package.pk])
            ).status_code,
            404,
        )


class StaticPageAdminCRUDTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(self.admin)

    def test_static_page_admin_crud(self):
        response = self.client.get(reverse("admin-static-pages"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "About Us")
        self.assertContains(response, "Contact Us")

        response = self.client.post(reverse("static-page-create"), {
            "title": "Terms of Service",
            "slug": "terms-of-service",
            "content": "Information about the platform.",
        })
        page = StaticPage.objects.get(slug="terms-of-service")
        self.assertRedirects(
            response,
            reverse("static-page-detail", args=[page.pk]),
        )
        self.assertContains(
            self.client.get(reverse("static-page-detail", args=[page.pk])),
            "Information about the platform.",
        )

        response = self.client.post(
            reverse("static-page-edit", args=[page.pk]),
            {
                "title": "About EventSphere",
                "slug": "about-eventsphere",
                "content": "Updated page content.",
            },
        )
        self.assertRedirects(
            response,
            reverse("static-page-detail", args=[page.pk]),
        )
        page.refresh_from_db()
        self.assertEqual(page.title, "About EventSphere")
        self.assertEqual(page.slug, "about-eventsphere")
        self.assertEqual(page.content, "Updated page content.")

        response = self.client.post(
            reverse("static-page-delete", args=[page.pk]),
        )
        self.assertRedirects(response, reverse("admin-static-pages"))
        self.assertFalse(StaticPage.objects.filter(pk=page.pk).exists())

    def test_default_static_pages_render_database_content(self):
        about = StaticPage.objects.get(slug="about")
        about.content = "About content managed from admin."
        about.save()
        response = self.client.get(reverse("about"))
        self.assertContains(response, "About content managed from admin.")

        contact = StaticPage.objects.get(slug="contact")
        contact.content = "Contact content managed from admin."
        contact.save()
        response = self.client.get(reverse("contact"))
        self.assertContains(response, "Contact content managed from admin.")
        self.assertContains(response, 'name="message"')

    def test_static_page_admin_routes_require_staff(self):
        self.client.logout()
        response = self.client.get(reverse("admin-static-pages"))
        self.assertEqual(response.status_code, 302)
