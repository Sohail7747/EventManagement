import json
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from bookings.models import (
    Booking,
    BookingSellerDecision,
    PackageReview,
    SellerUnavailableDate,
    ensure_booking_seller_decisions,
)
from dashboard.models import Event, Profile, Seller, Service
from payments.models import PackagePaymentAttempt
from payments.settlements import create_booking_earnings
from bookings.availability import seller_ids_for_item

from .models import (
    CatalogPackage,
    CatalogPackageItem,
    EventPackage,
    PackageService,
    ServiceQuote,
    ServiceQuoteRequest,
)


class CustomPackageBuilderTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create_user(
            username="package-builder-customer",
            email="customer@example.com",
            password="test-password",
        )
        Profile.objects.create(user=self.customer, role="USER")

        first_seller_user = user_model.objects.create_user(
            username="package-builder-seller-one",
            email="seller-one@example.com",
            password="test-password",
        )
        Profile.objects.create(user=first_seller_user, role="SELLER")
        self.first_seller = Seller.objects.create(
            user=first_seller_user,
            business_name="Celebrations One",
        )

        second_seller_user = user_model.objects.create_user(
            username="package-builder-seller-two",
            email="seller-two@example.com",
            password="test-password",
        )
        Profile.objects.create(user=second_seller_user, role="SELLER")
        self.second_seller = Seller.objects.create(
            user=second_seller_user,
            business_name="Celebrations Two",
        )

        self.event = Event.objects.create(
            title="Wedding Celebration",
            description="A celebration",
            location="Patna",
            event_date=timezone.localdate() + timedelta(days=30),
            price=1000,
            seller=self.first_seller,
        )
        self.catering_one = Service.objects.create(
            name="Catering",
            description="Wedding catering",
            price=500,
            seller=self.first_seller,
        )
        self.catering_two = Service.objects.create(
            name="Catering",
            description="Premium wedding catering",
            price=650,
            seller=self.second_seller,
        )
        self.photography = Service.objects.create(
            name="Photography",
            description="Event photography",
            price=300,
            seller=self.second_seller,
        )
        self.catering_one_package = CatalogPackage.objects.create(
            title="Classic Catering Package",
            description="Classic catering",
            event=self.event,
            seller=self.first_seller,
        )
        self.catering_one_offering = CatalogPackageItem.objects.create(
            package=self.catering_one_package,
            service=self.catering_one,
            selected_price=450,
        )
        self.catering_two_package = CatalogPackage.objects.create(
            title="Premium Catering Package",
            description="Premium catering",
            event=self.event,
            seller=self.second_seller,
        )
        self.catering_two_offering = CatalogPackageItem.objects.create(
            package=self.catering_two_package,
            service=self.catering_two,
            selected_price=750,
        )
        self.photography_package = CatalogPackage.objects.create(
            title="Photography Package",
            description="Event photography package",
            event=self.event,
            seller=self.second_seller,
        )
        self.photography_offering = CatalogPackageItem.objects.create(
            package=self.photography_package,
            service=self.photography,
            selected_price=275,
        )
        self.client.force_login(self.customer)
        self.api_client = APIClient()
        self.api_client.force_login(self.customer)

    def test_package_finder_shows_budget_date_and_service_steps(self):
        response = self.client.get(reverse("package-selection"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "budget-step-title")
        self.assertContains(response, "date-step-title")
        self.assertContains(response, "services-step-title")
        self.assertContains(response, "Make room for")
        self.assertContains(response, "Your package options")
        self.assertContains(response, 'id="service-picker-toggle"')
        self.assertContains(response, 'id="service-picker-menu"')
        self.assertContains(response, 'id="guest-count"')
        self.assertContains(response, "A fixed fee of ₹150 is charged per guest")
        self.assertContains(response, "package_finder.js")
        self.assertNotContains(response, "custom-package-event")
        self.assertNotContains(response, "Event type")
        self.assertNotContains(response, "event details")
        self.assertNotContains(response, "Classic Catering Package")

    def test_customer_panel_hides_quote_requests_and_promotes_package_builder(self):
        response = self.client.get(reverse("my-custom-packages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Account menu")
        self.assertContains(response, "Planning something special?")
        self.assertNotContains(response, reverse("my-service-quotes"))
        self.assertNotContains(response, "Quote Requests")

    def test_my_packages_handles_services_without_a_seller(self):
        shared_service = Service.objects.create(
            name="Shared catalog service",
            description="A service without an assigned seller",
            price=125,
        )
        package = EventPackage.objects.create(
            user=self.customer,
            event_date=timezone.localdate() + timedelta(days=30),
            total_cost=125,
        )
        PackageService.objects.create(
            package=package,
            service=shared_service,
            selected_price=125,
        )

        response = self.client.get(reverse("my-custom-packages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shared catalog service")
        self.assertContains(response, "Seller")

    def test_event_date_can_prefill_recommendation_page(self):
        event_date = timezone.localdate() + timedelta(days=35)
        response = self.client.get(
            reverse("package-selection"),
            {"event_date": event_date.isoformat()},
        )

        self.assertEqual(response.context["selected_date"], event_date)
        self.assertContains(response, event_date.isoformat())
        self.assertFalse(EventPackage.objects.filter(user=self.customer).exists())

    def test_service_finder_includes_offerings_without_a_published_package(self):
        Service.objects.create(
            name="Live Music",
            description="Live event music",
            price=400,
            seller=self.first_seller,
        )

        response = self.client.get(reverse("package-selection"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live Music")
        self.assertContains(response, 'data-service-name="Live Music"')
        self.assertContains(response, "service-offerings-data")

    def test_service_finder_uses_seller_package_price_over_service_default(self):
        response = self.client.get(reverse("package-selection"))

        self.assertEqual(response.status_code, 200)
        offers = response.context["service_offerings"]
        catering_offers = [
            offer for offer in offers if offer["category"] == "catering"
        ]
        self.assertEqual(len(catering_offers), 2)
        by_seller = {
            offer["seller_id"]: offer for offer in catering_offers
        }
        self.assertEqual(
            Decimal(by_seller[self.first_seller.pk]["price"]),
            self.catering_one_offering.selected_price,
        )
        self.assertEqual(
            by_seller[self.first_seller.pk]["offer_type"],
            "PACKAGE_ITEM",
        )
        self.assertEqual(
            Decimal(by_seller[self.second_seller.pk]["price"]),
            self.catering_two_offering.selected_price,
        )
        self.assertEqual(
            by_seller[self.second_seller.pk]["offer_type"],
            "PACKAGE_ITEM",
        )

    def test_service_finder_includes_service_image_url(self):
        self.catering_one.image = "services/catering.jpg"
        self.catering_one.save(update_fields=["image"])

        response = self.client.get(reverse("package-selection"))

        self.assertEqual(response.status_code, 200)
        catering_offer = next(
            offer
            for offer in response.context["service_offerings"]
            if offer["service_id"] == self.catering_one.pk
        )
        self.assertEqual(
            catering_offer["image_url"],
            "/media/services/catering.jpg",
        )

    def test_package_builder_calendar_and_creation_reject_unavailable_seller_date(self):
        blocked_date = timezone.localdate() + timedelta(days=45)
        SellerUnavailableDate.objects.create(
            seller=self.first_seller,
            date=blocked_date,
        )

        availability_response = self.api_client.post(
            reverse("package-builder-availability"),
            data={
                "categories": ["catering"],
                "budget": "700",
                "month": blocked_date.strftime("%Y-%m"),
            },
            format="json",
        )

        self.assertEqual(availability_response.status_code, 200)
        blocked_by_seller = availability_response.data["unavailable_by_seller"]
        self.assertIn(
            blocked_date.isoformat(),
            blocked_by_seller[self.first_seller.pk],
        )
        self.assertNotIn(self.second_seller.pk, blocked_by_seller)

        creation_response = self.api_client.post(
            reverse("create-event-package"),
            data=json.dumps(
                {
                    "event_date": blocked_date.isoformat(),
                    "budget": "700",
                    "guest_count": "4",
                    "services": [
                        {
                            "service_id": self.catering_one.pk,
                            "seller_id": self.first_seller.pk,
                            "offer_type": "PACKAGE_ITEM",
                            "offer_id": self.catering_one_offering.pk,
                        },
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(creation_response.status_code, 409)
        self.assertIn("unavailable", creation_response.data["error"])
        self.assertFalse(EventPackage.objects.filter(user=self.customer).exists())

    def test_service_picker_includes_shared_catalog_services_in_seller_packages(self):
        shared_service = Service.objects.create(
            name="Shared Catalog Photography",
            description="A shared admin service",
            price=500,
        )
        package = CatalogPackage.objects.create(
            title="Shared Catalog Package",
            description="A seller package using shared catalog service",
            event=self.event,
            seller=self.first_seller,
        )
        CatalogPackageItem.objects.create(
            package=package,
            service=shared_service,
            selected_price=450,
        )

        response = self.client.get(reverse("package-selection"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'data-service-name="Shared Catalog Photography"',
        )

    def test_service_quote_request_is_sent_to_every_seller(self):
        response = self.client.post(
            reverse("request-service-quote"),
            {
                "service_name": "Live streaming",
                "event_date": (
                    timezone.localdate() + timedelta(days=35)
                ).isoformat(),
                "details": "Two cameras, please.",
            },
        )

        self.assertRedirects(response, reverse("my-service-quotes"))
        quote_request = ServiceQuoteRequest.objects.get(customer=self.customer)
        self.assertEqual(quote_request.service_name, "Live streaming")
        self.assertEqual(quote_request.details, "Two cameras, please.")
        self.assertSetEqual(
            set(quote_request.quotes.values_list("seller_id", flat=True)),
            {self.first_seller.pk, self.second_seller.pk},
        )

    def test_quote_request_for_a_listed_service_is_rejected(self):
        response = self.client.post(
            reverse("request-service-quote"),
            {"service_name": "catering"},
        )

        self.assertRedirects(response, reverse("package-selection"))
        self.assertFalse(ServiceQuoteRequest.objects.exists())

    def test_seller_can_send_quote_and_customer_can_review_it(self):
        quote_request = ServiceQuoteRequest.objects.create(
            customer=self.customer,
            service_name="Live streaming",
        )
        quote = ServiceQuote.objects.create(
            request=quote_request,
            seller=self.first_seller,
        )
        self.client.force_login(self.first_seller.user)

        response = self.client.post(
            reverse("seller-service-quote-response", args=[quote.pk]),
            {
                "action": "quote",
                "quoted_price": "250.00",
                "message": "Includes two cameras.",
            },
        )

        self.assertRedirects(response, reverse("seller-dashboard"))
        quote.refresh_from_db()
        self.assertEqual(quote.status, ServiceQuote.Status.QUOTED)
        self.assertEqual(quote.quoted_price, 250)
        self.assertEqual(quote.message, "Includes two cameras.")

        self.client.force_login(self.customer)
        response = self.client.get(reverse("my-service-quotes"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live streaming")
        self.assertContains(response, self.first_seller.business_name)
        self.assertContains(response, "₹250.00")

    def test_selected_event_date_is_preserved_through_package_details(self):
        event_date = timezone.localdate() + timedelta(days=35)
        response = self.client.get(
            reverse(
                "public-package-detail",
                args=[self.catering_one_package.pk],
            ),
            {"booking_date": event_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'?booking_date={event_date.isoformat()}',
        )

    def test_legacy_create_submission_does_not_create_a_custom_package(self):
        response = self.client.post(
            reverse("package-selection"),
            {
                "event_id": self.event.pk,
                "event_date": (
                    timezone.localdate() + timedelta(days=35)
                ).isoformat(),
                "services": [self.catering_two_offering.pk],
                "budget_min_1": "600.00",
                "budget_max_1": "700.00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventPackage.objects.filter(user=self.customer).exists())
        self.assertContains(response, "Services and seller prices")
        self.assertNotContains(response, "Recommended for you")

    def test_completed_catalog_booking_can_submit_one_verified_review(self):
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CATALOG_PACKAGE,
            catalog_package=self.catering_one_package,
            package_event=self.event,
            seller=self.first_seller,
            booking_date=timezone.localdate() - timedelta(days=2),
            booking_end_date=timezone.localdate() - timedelta(days=2),
            total_price=500,
            item_title=self.catering_one_package.title,
            status=Booking.Status.COMPLETED,
        )

        response = self.client.post(
            reverse("submit-package-review", args=[booking.pk]),
            {"rating": "5", "comment": "Excellent service."},
        )

        self.assertRedirects(response, reverse("booking-detail", args=[booking.pk]))
        review = PackageReview.objects.get(booking=booking)
        self.assertEqual(review.package, self.catering_one_package)
        self.assertEqual(review.user, self.customer)
        self.assertEqual(review.rating, 5)
        self.assertContains(
            self.client.get(
                reverse(
                    "public-package-detail",
                    args=[self.catering_one_package.pk],
                )
            ),
            "Excellent service.",
        )
        self.assertEqual(
            self.client.post(
                reverse("submit-package-review", args=[booking.pk]),
                {"rating": "4"},
            ).status_code,
            302,
        )
        self.assertEqual(PackageReview.objects.filter(booking=booking).count(), 1)

    def test_booking_must_be_completed_before_review_submission(self):
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CATALOG_PACKAGE,
            catalog_package=self.catering_one_package,
            package_event=self.event,
            seller=self.first_seller,
            booking_date=timezone.localdate() + timedelta(days=2),
            total_price=500,
            item_title=self.catering_one_package.title,
            status=Booking.Status.CONFIRMED,
        )

        response = self.client.post(
            reverse("submit-package-review", args=[booking.pk]),
            {"rating": "5"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(PackageReview.objects.filter(booking=booking).exists())

    def test_admin_can_remove_package_without_deleting_payment_history(self):
        payment_attempt = PackagePaymentAttempt.objects.create(
            user=self.customer,
            package=self.catering_one_package,
            receipt="catalog-delete-payment-attempt",
            amount_paise=45000,
            total_price=450,
            booking_date=timezone.localdate() + timedelta(days=35),
            guest_count=1,
            customer_name="Package Customer",
            customer_email=self.customer.email,
            customer_phone="555-0123",
        )
        admin = get_user_model().objects.create_user(
            username="package-delete-admin",
            email="package-delete-admin@example.com",
            is_staff=True,
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse(
                "admin-catalog-package-delete",
                args=[self.catering_one_package.pk],
            )
        )

        self.assertRedirects(response, reverse("admin-catalog-packages"))
        self.catering_one_package.refresh_from_db()
        self.assertTrue(self.catering_one_package.is_deleted)
        payment_attempt.refresh_from_db()
        self.assertEqual(payment_attempt.package, self.catering_one_package)
        self.assertNotContains(
            self.client.get(reverse("admin-catalog-packages")),
            self.catering_one_package.title,
        )

        self.client.force_login(self.customer)
        self.assertNotContains(
            self.client.get(reverse("public-packages")),
            self.catering_one_package.title,
        )
        self.assertNotContains(
            self.client.get(reverse("package-selection")),
            self.catering_one_package.title,
        )
        self.assertEqual(
            self.client.get(
                reverse("package-booking", args=[self.catering_one_package.pk])
            ).status_code,
            404,
        )

    def test_finder_does_not_create_package_for_multiple_seller_offerings(self):
        response = self.client.post(
            reverse("package-selection"),
            {
                "event_date": (
                    timezone.localdate() + timedelta(days=35)
                ).isoformat(),
                "budget": "700",
                "services": [
                    self.catering_one_offering.pk,
                    self.catering_two_offering.pk,
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventPackage.objects.filter(user=self.customer).exists())
        self.assertContains(response, "Services and seller prices")
        self.assertNotContains(response, "Recommended for you")

    def test_package_creation_api_uses_seller_price_not_client_submitted_price(self):
        response = self.api_client.post(
            reverse("create-event-package"),
            data=json.dumps(
                {
                    "event_date": (
                        timezone.localdate() + timedelta(days=35)
                    ).isoformat(),
                    "budget": "700",
                    "guest_count": "4",
                    "services": [
                        {
                            "service_id": self.catering_two.pk,
                            "selected_price": "1.00",
                        },
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        package = EventPackage.objects.get(user=self.customer)
        self.assertIsNone(package.event)
        self.assertEqual(package.event_price, 0)
        self.assertEqual(package.total_cost, 650)
        self.assertEqual(package.guest_count, 4)
        self.assertEqual(
            package.package_services.get().selected_price,
            650,
        )

    def test_package_creation_api_accepts_more_than_five_services(self):
        services = [
            Service.objects.create(
                name=f"Additional service {index}",
                description="Event service",
                price=10,
                seller=self.first_seller,
            )
            for index in range(6)
        ]
        response = self.api_client.post(
            reverse("create-event-package"),
            data=json.dumps(
                {
                    "event_date": (
                        timezone.localdate() + timedelta(days=35)
                    ).isoformat(),
                    "budget": "100",
                    "services": [
                        {
                            "service_id": service.pk,
                            "seller_id": self.first_seller.pk,
                            "offer_type": "SERVICE",
                            "offer_id": service.pk,
                        }
                        for service in services
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        package = EventPackage.objects.get(user=self.customer)
        self.assertEqual(package.package_services.count(), 6)
        self.assertEqual(package.total_cost, 60)
        self.assertEqual(
            response.data["booking_url"],
            reverse("custom-package-booking", args=[package.pk]),
        )
        booking_page = self.client.get(response.data["booking_url"])
        self.assertEqual(booking_page.status_code, 200)
        self.assertEqual(
            booking_page.context["total_price"],
            Decimal("210"),
        )
        self.assertEqual(booking_page.context["guest_count"], 1)

    def test_package_creation_api_rejects_invalid_guest_count(self):
        response = self.api_client.post(
            reverse("create-event-package"),
            data=json.dumps(
                {
                    "event_date": (
                        timezone.localdate() + timedelta(days=35)
                    ).isoformat(),
                    "budget": "700",
                    "guest_count": 0,
                    "services": [
                        {
                            "service_id": self.catering_one.pk,
                            "seller_id": self.first_seller.pk,
                            "offer_type": "SERVICE",
                            "offer_id": self.catering_one.pk,
                        },
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("guest count", response.data["error"])
        self.assertFalse(EventPackage.objects.filter(user=self.customer).exists())

    def test_package_creation_api_rejects_fractional_guest_count(self):
        response = self.api_client.post(
            reverse("create-event-package"),
            data=json.dumps(
                {
                    "event_date": (
                        timezone.localdate() + timedelta(days=35)
                    ).isoformat(),
                    "budget": "700",
                    "guest_count": 1.5,
                    "services": [
                        {
                            "service_id": self.catering_one.pk,
                            "seller_id": self.first_seller.pk,
                            "offer_type": "SERVICE",
                            "offer_id": self.catering_one.pk,
                        },
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("guest count", response.data["error"])
        self.assertFalse(EventPackage.objects.filter(user=self.customer).exists())

    def test_selected_package_item_seller_reaches_booking_and_payout_workflow(self):
        shared_service = Service.objects.create(
            name="Shared Seller Photography",
            description="A shared catalog service",
            price=500,
        )
        seller_package = CatalogPackage.objects.create(
            title="Seller Photography Offer",
            description="A seller-specific offering",
            event=self.event,
            seller=self.second_seller,
        )
        offering = CatalogPackageItem.objects.create(
            package=seller_package,
            service=shared_service,
            selected_price=700,
        )

        response = self.api_client.post(
            reverse("create-event-package"),
            data=json.dumps(
                {
                    "event_date": (
                        timezone.localdate() + timedelta(days=35)
                    ).isoformat(),
                    "budget": "1200",
                    "package_title": "Photography celebration",
                    "services": [
                        {
                            "service_id": self.catering_one.pk,
                            "seller_id": self.first_seller.pk,
                            "offer_type": "PACKAGE_ITEM",
                            "offer_id": self.catering_one_offering.pk,
                        },
                        {
                            "service_id": shared_service.pk,
                            "seller_id": self.second_seller.pk,
                            "offer_type": "PACKAGE_ITEM",
                            "offer_id": offering.pk,
                        },
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        custom_package = EventPackage.objects.get(user=self.customer)
        self.assertIsNone(custom_package.event)
        package_service = custom_package.package_services.get(
            service=shared_service
        )
        self.assertEqual(package_service.seller, self.second_seller)
        self.assertEqual(package_service.selected_price, 700)
        self.assertEqual(custom_package.total_cost, 1150)
        self.assertEqual(custom_package.guest_count, 1)
        self.assertEqual(response.data["booking_url"], reverse(
            "custom-package-booking",
            args=[custom_package.pk],
        ))
        booking_page = self.client.get(response.data["booking_url"])
        self.assertEqual(booking_page.status_code, 200)
        self.assertContains(booking_page, "Photography celebration")
        self.assertContains(booking_page, "Catering")
        self.assertContains(booking_page, "Shared Seller Photography")
        self.assertEqual(booking_page.context["total_price"], Decimal("1300"))
        self.assertContains(booking_page, "customPackageBookingForm")

        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CUSTOM_PACKAGE,
            custom_package=custom_package,
            booking_date=custom_package.event_date,
            total_price=custom_package.total_cost + Decimal("150"),
            item_title=custom_package.package_title,
        )
        ensure_booking_seller_decisions(booking)
        self.assertSetEqual(
            set(
                booking.seller_decisions.values_list(
                    "seller_id",
                    flat=True,
                )
            ),
            {self.first_seller.pk, self.second_seller.pk},
        )
        self.assertEqual(
            seller_ids_for_item("CUSTOM_PACKAGE", custom_package),
            [self.first_seller.pk, self.second_seller.pk],
        )

        create_booking_earnings(booking)
        self.assertSetEqual(
            set(
                booking.seller_earnings.values_list(
                    "seller_id",
                    flat=True,
                )
            ),
            {self.first_seller.pk, self.second_seller.pk},
        )

    def test_package_finder_rejects_services_over_budget(self):
        response = self.api_client.post(
            reverse("create-event-package"),
            data=json.dumps(
                {
                    "event_date": (
                        timezone.localdate() + timedelta(days=35)
                    ).isoformat(),
                    "budget": "400",
                    "services": [
                        {
                            "service_id": self.catering_one.pk,
                            "seller_id": self.first_seller.pk,
                            "offer_type": "PACKAGE_ITEM",
                            "offer_id": self.catering_one_offering.pk,
                        },
                    ],
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("exceed your budget", response.data["error"])
        self.assertFalse(EventPackage.objects.filter(user=self.customer).exists())

    def test_admin_packages_page_shows_customer_created_package_details(self):
        package = EventPackage.objects.create(
            user=self.customer,
            event=self.event,
            event_date=timezone.localdate() + timedelta(days=35),
            event_price=self.event.price,
            total_cost=1650,
        )
        PackageService.objects.create(
            package=package,
            service=self.catering_two,
            selected_price=self.catering_two.price,
        )
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CUSTOM_PACKAGE,
            custom_package=package,
            package_event=self.event,
            booking_date=package.event_date,
            total_price=package.total_cost,
            item_title="Custom wedding package",
        )
        booking.package_services.set([self.catering_two])
        admin = get_user_model().objects.create_user(
            username="package-builder-admin",
            email="admin@example.com",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("admin-catalog-packages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer-created packages")
        self.assertContains(response, self.customer.email)
        self.assertContains(response, self.event.title)
        self.assertContains(response, self.second_seller.business_name)
        self.assertContains(response, "₹650.00")

        booking_response = self.client.get(reverse("admin-bookings"))
        self.assertEqual(booking_response.status_code, 200)
        self.assertContains(booking_response, "Custom package breakdown")
        self.assertContains(booking_response, "Custom wedding package")
        self.assertContains(booking_response, self.second_seller.business_name)
