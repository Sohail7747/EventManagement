from datetime import date, timedelta
from decimal import Decimal
import hashlib
import hmac
import json
from unittest.mock import patch

import razorpay
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

<<<<<<< HEAD
from admin_panel.models import Event, Profile, Seller, Service
=======
from dashboard.models import Event, Profile, Seller, Service
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
from bookings.availability import reserve_booking_dates
from bookings.models import BookingDateReservation, SellerUnavailableDate
from packages.models import (
    CatalogPackage,
    CatalogPackageItem,
    EventPackage,
    PackageService,
)

from bookings.models import (
    Booking,
    BookingSellerDecision,
<<<<<<< HEAD
    PackageReview,
=======
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
    ensure_booking_seller_decisions,
)
from .models import (
    BookingCancellationRequest,
    PackagePaymentAttempt,
    PayoutRequest,
    SellerEarning,
)
from bookings.availability import BookingUnavailableError


class PackageBookingPageTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create_user(
            username="package-customer",
            email="customer@example.com",
            password="testpass123",
        )
        Profile.objects.create(user=self.customer, role="USER")

        seller_user = user_model.objects.create_user(
            username="package-seller",
            email="seller@example.com",
            password="testpass123",
        )
        self.seller_user = seller_user
        Profile.objects.get_or_create(
            user=seller_user,
            defaults={"role": "SELLER"},
        )
        self.seller = Seller.objects.create(
            user=seller_user,
            business_name="Celebrations Co.",
            phone="555-1000",
            address="Patna, Bihar",
        )

        self.event = Event.objects.create(
            title="Wedding Celebration",
            description="A celebration",
            location="Patna",
            event_date=date.today() + timedelta(days=30),
            price=1000,
            seller=self.seller,
        )

        service = Service.objects.create(
            name="Photography",
            description="Event photography",
            image="services/photography.jpg",
            price=500,
            seller=self.seller,
        )

        self.package = CatalogPackage.objects.create(
            title="Wedding Essentials",
            description="A curated wedding package.",
            event=self.event,
            seller=self.seller,
        )

        CatalogPackageItem.objects.create(
            package=self.package,
            service=service,
            selected_price=500,
        )

    def test_package_booking_page_shows_details_and_form(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("package-booking", args=[self.package.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.package.title)
        self.assertContains(response, self.event.title)
        self.assertContains(response, "Photography")
        self.assertContains(response, "included-service-card")
        self.assertContains(response, "/media/services/photography.jpg")
        self.assertContains(response, "Event details")
        self.assertContains(response, "Event start date")
        self.assertContains(response, "End date")
        self.assertContains(response, "Contact information")
        self.assertContains(response, "Seller details")
        self.assertContains(response, self.seller.phone)
        self.assertContains(response, "seller@example.com")
        self.assertNotContains(response, "Add-ons")
        self.assertContains(response, "Pay full amount securely")
        self.assertContains(response, "Full payment due now")
        self.assertNotContains(response, "advance")
        self.assertContains(response, "summaryTotal")

    def test_custom_booking_page_shows_selected_services_and_seller_prices(self):
        service = self.package.package_items.get().service
        package = EventPackage.objects.create(
            user=self.customer,
            event_date=timezone.localdate() + timedelta(days=30),
            total_cost=500,
            package_title="My celebration",
            guest_count=3,
        )
        PackageService.objects.create(
            package=package,
            service=service,
            seller=self.seller,
            selected_price=500,
        )
        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("custom-package-booking", args=[package.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My celebration")
        self.assertContains(response, "checkout-service")
        self.assertContains(response, "Photography")
        self.assertContains(response, self.seller.business_name)
        self.assertContains(response, "/media/services/photography.jpg")
        self.assertContains(response, "₹500.00")
        self.assertContains(response, "₹450.00")
        self.assertContains(response, "A fixed fee of")
        self.assertContains(response, "₹950.00")
        self.assertEqual(response.context["guest_count"], 3)
        self.assertEqual(response.context["guest_total"], Decimal("450.00"))
        self.assertEqual(response.context["total_price"], Decimal("950.00"))
        self.assertNotContains(response, "Number of guests")
        self.assertNotIn("guest_count", response.context["form"].fields)
        self.assertLess(
            response.content.index(b"Booking summary"),
            response.content.index(b"Event details"),
        )

    def test_selected_event_date_prefills_package_booking_form(self):
        self.client.force_login(self.customer)
        booking_date = timezone.localdate() + timedelta(days=10)
        response = self.client.get(
            reverse("package-booking", args=[self.package.pk]),
            {"booking_date": booking_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["form"]["booking_date"].value(),
            booking_date,
        )
        self.assertContains(response, f'data-selected-date="{booking_date.isoformat()}"')
        self.assertContains(response, 'class="form-control booking-date-input"')
        self.assertContains(response, f'value="{booking_date.isoformat()}"')

    def test_calendar_marks_seller_blocked_dates_unavailable(self):
        self.client.force_login(self.customer)
        blocked_date = timezone.localdate() + timedelta(days=20)
        SellerUnavailableDate.objects.create(
            seller=self.seller,
            date=blocked_date,
        )

        response = self.client.get(
            reverse("package-availability", args=[self.package.pk]),
            {"month": blocked_date.strftime("%Y-%m")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            blocked_date.isoformat(),
            response.json()["unavailable_dates"],
        )

    def test_calendar_includes_existing_active_bookings(self):
        self.client.force_login(self.customer)
        booked_date = timezone.localdate() + timedelta(days=22)
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CATALOG_PACKAGE,
            catalog_package=self.package,
            package_event=self.event,
            seller=self.seller,
            booking_date=booked_date,
            booking_end_date=booked_date,
            total_price=800,
            item_title=self.package.title,
        )
        booking.package_services.set(
            self.package.package_items.values_list("service_id", flat=True)
        )

        response = self.client.get(
            reverse("package-availability", args=[self.package.pk]),
            {"month": booked_date.strftime("%Y-%m")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            booked_date.isoformat(),
            response.json()["unavailable_dates"],
        )

    def test_simultaneous_date_holds_for_a_seller_cannot_overlap(self):
        booking_date = timezone.localdate() + timedelta(days=25)
        reserve_booking_dates(
            [self.seller.pk],
            booking_date,
            booking_date,
            payment_receipt="first-date-hold",
        )

        with self.assertRaises(BookingUnavailableError):
            reserve_booking_dates(
                [self.seller.pk],
                booking_date,
                booking_date,
                payment_receipt="second-date-hold",
            )

        self.assertEqual(
            BookingDateReservation.objects.filter(
                seller=self.seller,
                date=booking_date,
            ).count(),
            1,
        )

    @override_settings(
        MAILERS={
            "default": {
                "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
            }
        },
        RAZORPAY_KEY_ID="rzp_test_key",
        RAZORPAY_KEY_SECRET="test-secret",
    )
    @patch("payments.views.razorpay_client")
    def test_customer_requests_cancellation_and_admin_processes_refund(
        self,
        razorpay_client_mock,
    ):
        self.client.force_login(self.customer)
        booking_date = timezone.localdate() + timedelta(days=40)
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CATALOG_PACKAGE,
            catalog_package=self.package,
            package_event=self.event,
            seller=self.seller,
            booking_date=booking_date,
            booking_end_date=booking_date,
            total_price=800,
            item_title=self.package.title,
            customer_name="Package Customer",
            customer_email=self.customer.email,
        )
        PackagePaymentAttempt.objects.create(
            user=self.customer,
            package=self.package,
            booking=booking,
            receipt="refund-flow-receipt",
            order_id="order_refund_flow",
            payment_id="pay_refund_flow",
            amount_paise=80000,
            total_price=800,
            booking_date=booking_date,
            booking_end_date=booking_date,
            guest_count=1,
            customer_name="Package Customer",
            customer_email=self.customer.email,
            customer_phone="555-0123",
            status=PackagePaymentAttempt.Status.PAID,
        )
        reserve_booking_dates(
            [self.seller.pk],
            booking_date,
            booking_date,
            booking=booking,
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("cancel-booking", args=[booking.pk]),
                {"reason": "Plans changed."},
            )

        self.assertRedirects(response, reverse("booking-detail", args=[booking.pk]))
        cancellation = BookingCancellationRequest.objects.get(booking=booking)
        self.assertEqual(
            cancellation.status,
            BookingCancellationRequest.Status.REQUESTED,
        )
        self.assertEqual(
            Booking.objects.get(pk=booking.pk).status,
            Booking.Status.PENDING,
        )
        self.assertEqual(mail.outbox[-1].subject, "Cancellation request received")

        admin = get_user_model().objects.create_user(
            username="refund-flow-admin",
            email="refund-admin@example.com",
            is_staff=True,
        )
        self.client.force_login(admin)
        gateway = razorpay_client_mock.return_value
        gateway.payment.refund.return_value = {"id": "rfnd_test_123"}

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse(
                    "admin-process-cancellation",
                    args=[cancellation.pk],
                ),
                {"action": "approve", "admin_note": "Approved."},
            )

        self.assertRedirects(response, reverse("admin-bookings"))
        cancellation.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(cancellation.status, BookingCancellationRequest.Status.REFUNDED)
        self.assertEqual(cancellation.refund_id, "rfnd_test_123")
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertFalse(booking.date_reservations.exists())
        gateway.payment.refund.assert_called_once()
        self.assertEqual(mail.outbox[-1].subject, "Booking cancelled and refund processed")

    def test_package_cards_link_to_full_details_page(self):
        response = self.client.get(reverse("public-packages"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("public-package-detail", args=[self.package.pk]),
        )

    def test_package_details_page_shows_package_event_services_and_seller(self):
        response = self.client.get(reverse("public-package-detail", args=[self.package.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.package.title)
        self.assertContains(response, self.event.title)
        self.assertContains(response, "Photography")
        self.assertContains(response, self.seller.business_name)
        self.assertContains(response, "₹150.00")
        self.assertContains(response, "Continue to booking")

    def test_selected_package_date_is_forwarded_to_booking(self):
        booking_date = timezone.localdate() + timedelta(days=10)
        response = self.client.get(
            reverse("public-package-detail", args=[self.package.pk]),
            {"booking_date": booking_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'{reverse("package-booking", args=[self.package.pk])}'
            f'?booking_date={booking_date.isoformat()}',
        )

    @override_settings(
        RAZORPAY_KEY_ID="rzp_test_key",
        RAZORPAY_KEY_SECRET="test-secret",
        MAILERS={
            "default": {
                "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
            }
        },
    )
    @patch("payments.views.razorpay_client")
    def test_booking_is_created_after_verified_payment(self, razorpay_client_mock):
        self.client.force_login(self.customer)
        booking_date = date.today() + timedelta(days=10)
        booking_end_date = booking_date + timedelta(days=2)

        gateway = razorpay_client_mock.return_value
        gateway.order.create.return_value = {"id": "order_test_123"}
        gateway.payment.fetch.return_value = {
            "id": "pay_test_123",
            "order_id": "order_test_123",
            "amount": 80000,
            "currency": "INR",
            "status": "captured",
        }

        response = self.client.post(
            reverse("package-booking", args=[self.package.pk]),
            {
                "booking_date": booking_date.isoformat(),
                "booking_end_date": booking_end_date.isoformat(),
                "guest_count": "2",
                "customer_name": "Test Customer",
                "customer_email": "customer@example.com",
                "customer_phone": "555-0123",
                "customer_notes": "Please call before arrival.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.exists())

        attempt = PackagePaymentAttempt.objects.get(user=self.customer)
        self.assertEqual(attempt.order_id, "order_test_123")
        self.assertEqual(attempt.amount_paise, 80000)
        self.assertEqual(response.context["payment_options"]["amount"], 80000)
        self.assertContains(response, "Opening secure checkout...")
        self.assertContains(response, "Razorpay checkout is opening.")
        self.assertEqual(
            gateway.order.create.call_args.kwargs["data"]["amount"],
            80000,
        )
        self.assertEqual(
            response.context["payment_options"]["config"]["display"]["blocks"]["upi"],
            {
                "name": "Pay with UPI",
                "instruments": [{"method": "upi"}],
            },
        )
        self.assertTrue(
            response.context["payment_options"]["config"]["display"]["preferences"][
                "show_default_blocks"
            ]
        )

        with self.captureOnCommitCallbacks(execute=True):
            verify_response = self.client.post(
                reverse("verify-package-payment"),
                {
                    "attempt_id": attempt.pk,
                    "razorpay_order_id": "order_test_123",
                    "razorpay_payment_id": "pay_test_123",
                    "razorpay_signature": "valid-signature",
                },
            )

        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(
            mail.outbox[-1].subject,
            f"Booking request received: {self.package.title}",
        )
        self.assertEqual(Booking.objects.filter(user=self.customer).count(), 1)

        booking = Booking.objects.get(user=self.customer)
        self.assertEqual(
            verify_response.json()["redirect_url"],
            reverse("booking-detail", args=[booking.pk]),
        )
        self.assertEqual(attempt.__class__.objects.get(pk=attempt.pk).status, "PAID")
        self.assertEqual(booking.item_type, Booking.ItemType.CATALOG_PACKAGE)
        self.assertEqual(booking.catalog_package, self.package)
        self.assertEqual(booking.package_event, self.event)
        self.assertEqual(booking.seller, self.seller)
        self.assertEqual(
            list(booking.package_services.values_list("name", flat=True)),
            ["Photography"],
        )
        self.assertEqual(booking.booking_date, booking_date)
        self.assertEqual(booking.booking_end_date, booking_end_date)
        self.assertEqual(booking.guest_count, 2)
        self.assertEqual(booking.total_price, 800)
        payment_attempt = PackagePaymentAttempt.objects.get(booking=booking)
        self.assertEqual(payment_attempt.amount, 800)
        self.assertEqual(payment_attempt.payment_id, "pay_test_123")
        self.assertEqual(payment_attempt.status, "PAID")
        self.assertEqual(booking.customer_name, "Test Customer")
        self.assertEqual(booking.customer_email, "customer@example.com")
        self.assertEqual(booking.customer_phone, "555-0123")
        self.assertEqual(booking.customer_notes, "Please call before arrival.")

        detail_response = self.client.get(reverse("booking-detail", args=[booking.pk]))
        self.assertContains(detail_response, f"Booking #{booking.pk}")
        self.assertContains(detail_response, booking_end_date.strftime("%A, %d %B %Y"))
        self.assertContains(detail_response, "SELLER CONTACT")
        self.assertContains(detail_response, self.seller.phone)
        self.assertContains(detail_response, "seller@example.com")
        self.assertContains(detail_response, self.seller.address)
        self.assertContains(detail_response, "Payment status")
        self.assertContains(detail_response, "Amount paid")
        self.assertContains(detail_response, "pay_test_123")

    @override_settings(
        RAZORPAY_KEY_ID="rzp_test_key",
        RAZORPAY_KEY_SECRET="test-secret",
    )
    @patch("payments.views.razorpay_client")
    def test_invalid_payment_signature_does_not_create_booking(self, razorpay_client_mock):
        self.client.force_login(self.customer)
        booking_date = date.today() + timedelta(days=10)
        booking_end_date = booking_date + timedelta(days=2)

        gateway = razorpay_client_mock.return_value
        gateway.order.create.return_value = {"id": "order_test_123"}
        gateway.payment.fetch.return_value = {
            "id": "pay_test_123",
            "order_id": "order_test_123",
            "amount": 80000,
            "currency": "INR",
            "status": "captured",
        }

        self.client.post(
            reverse("package-booking", args=[self.package.pk]),
            {
                "booking_date": booking_date.isoformat(),
                "booking_end_date": booking_end_date.isoformat(),
                "guest_count": "2",
                "customer_name": "Test Customer",
                "customer_email": "customer@example.com",
                "customer_phone": "555-0123",
            },
        )

        attempt = PackagePaymentAttempt.objects.get(user=self.customer)
        gateway.utility.verify_payment_signature.side_effect = razorpay.errors.SignatureVerificationError

        verify_response = self.client.post(
            reverse("verify-package-payment"),
            {
                "attempt_id": attempt.pk,
                "razorpay_order_id": "order_test_123",
                "razorpay_payment_id": "pay_test_123",
                "razorpay_signature": "invalid-signature",
            },
        )

        self.assertEqual(verify_response.status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_customer_cannot_create_custom_package_from_finder(self):
        self.client.force_login(self.customer)
        service_id = self.package.package_items.get().service_id
        event_date = date.today() + timedelta(days=30)

        response = self.client.post(
            reverse("package-selection"),
            {
                "event_id": self.event.pk,
                "event_date": event_date.isoformat(),
                "services": [service_id],
                f"service_price_{service_id}": "725.50",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventPackage.objects.filter(user=self.customer).exists())
        self.assertContains(response, "Recommended for you")

    @override_settings(
        RAZORPAY_KEY_ID="rzp_test_key",
        RAZORPAY_KEY_SECRET="test-secret",
    )
    @patch("payments.views.razorpay_client")
<<<<<<< HEAD
    def test_custom_package_payment_allocates_earnings_by_selected_seller_prices(
=======
    def test_custom_package_payment_splits_ninety_percent_equally(
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
        self,
        razorpay_client_mock,
    ):
        second_user = get_user_model().objects.create_user(
            username="second-package-seller",
            email="second-seller@example.com",
            password="test-password",
        )
        Profile.objects.create(user=second_user, role="SELLER")
        second_seller = Seller.objects.create(
            user=second_user,
            business_name="Second Seller",
        )
        second_service = Service.objects.create(
            name="Catering",
            description="Food service",
            price=500,
            seller=second_seller,
        )
        package = EventPackage.objects.create(
            user=self.customer,
            event=None,
            event_date=date.today() + timedelta(days=20),
            event_price=0,
<<<<<<< HEAD
            total_cost=1500,
=======
            total_cost=1000,
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
            guest_count=2,
        )
        PackageService.objects.create(
            package=package,
            service=self.package.package_items.get().service,
<<<<<<< HEAD
            selected_price=1000,
=======
            selected_price=500,
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
        )
        PackageService.objects.create(
            package=package,
            service=second_service,
            selected_price=500,
        )
        booking_date = date.today() + timedelta(days=20)
        gateway = razorpay_client_mock.return_value
        gateway.order.create.return_value = {"id": "order_custom_123"}
        gateway.payment.fetch.return_value = {
            "id": "pay_custom_123",
            "order_id": "order_custom_123",
<<<<<<< HEAD
            "amount": 180000,
=======
            "amount": 130000,
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
            "currency": "INR",
            "status": "captured",
        }
        self.client.force_login(self.customer)

        response = self.client.post(
            reverse("custom-package-booking", args=[package.pk]),
            {
                "booking_date": booking_date.isoformat(),
                "booking_end_date": booking_date.isoformat(),
                "customer_name": "Test Customer",
                "customer_email": "customer@example.com",
                "customer_phone": "555-0123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Continue to secure payment")
<<<<<<< HEAD
        self.assertContains(response, "Pay ₹1800.00 securely")
        self.assertContains(response, 'id="razorpay-options"')
        self.assertContains(response, "₹1800.00")
=======
        self.assertContains(response, "Opening payment options...")
        self.assertContains(response, "checkout.open();")
        self.assertContains(response, "₹1300.00")
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
        self.assertContains(
            response,
            'type="button"\n                        id="customPaymentButton"',
        )
        attempt = PackagePaymentAttempt.objects.get(custom_package=package)
<<<<<<< HEAD
        self.assertEqual(attempt.amount_paise, 180000)
        self.assertEqual(attempt.total_price, 1800)
=======
        self.assertEqual(attempt.amount_paise, 130000)
        self.assertEqual(attempt.total_price, 1300)
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01

        verify_response = self.client.post(
            reverse("verify-package-payment"),
            {
                "attempt_id": attempt.pk,
                "razorpay_order_id": "order_custom_123",
                "razorpay_payment_id": "pay_custom_123",
                "razorpay_signature": "valid-signature",
            },
        )

        self.assertEqual(verify_response.status_code, 200)
        booking = Booking.objects.get(custom_package=package)
        self.assertEqual(booking.status, Booking.Status.PENDING)
<<<<<<< HEAD
        self.assertEqual(booking.total_price, 1800)
=======
        self.assertEqual(booking.total_price, 1300)
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
        self.assertEqual(
            set(
                booking.seller_earnings.values_list(
                    "seller_id",
                    flat=True,
                )
            ),
            {self.seller.pk, second_seller.pk},
        )
        self.assertEqual(
            list(
                booking.seller_earnings.order_by("seller_id").values_list(
                    "seller_amount",
                    flat=True,
                )
            ),
<<<<<<< HEAD
            [1080, 540],
=======
            [585, 585],
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
        )
        self.assertEqual(
            list(
                booking.seller_earnings.order_by("seller_id").values_list(
                    "commission_amount",
                    flat=True,
                )
            ),
<<<<<<< HEAD
            [120, 60],
=======
            [65, 65],
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
        )
        self.assertEqual(booking.seller_decisions.count(), 2)

    def test_sellers_must_give_rejection_reason_and_all_accept_to_confirm(self):
        second_user = get_user_model().objects.create_user(
            username="second-review-seller",
            email="review-seller@example.com",
            password="test-password",
        )
        Profile.objects.create(user=second_user, role="SELLER")
        second_seller = Seller.objects.create(
            user=second_user,
            business_name="Second Reviewer",
        )
        second_service = Service.objects.create(
            name="Catering",
            description="Food service",
            price=500,
            seller=second_seller,
        )
        package = EventPackage.objects.create(
            user=self.customer,
            event=self.event,
            event_date=date.today() + timedelta(days=20),
            event_price=1000,
            total_cost=2000,
        )
        PackageService.objects.create(
            package=package,
            service=self.package.package_items.get().service,
            selected_price=500,
        )
        PackageService.objects.create(
            package=package,
            service=second_service,
            selected_price=500,
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
        booking.package_services.set([item.service_id for item in package.package_services.all()])
        first_decision = BookingSellerDecision.objects.create(
            booking=booking,
            seller=self.seller,
        )
        BookingSellerDecision.objects.create(
            booking=booking,
            seller=second_seller,
        )

        self.client.force_login(self.seller.user)
        dashboard_response = self.client.get(reverse("seller-dashboard"))
        self.assertContains(dashboard_response, "Custom package requests")
        self.assertContains(dashboard_response, "Custom wedding package")
        response = self.client.post(
            reverse("seller-booking-decision", args=[booking.pk]),
            {"action": "accept"},
        )
        self.assertRedirects(response, reverse("seller-bookings"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)

        self.client.force_login(second_user)
        response = self.client.post(
            reverse("seller-booking-decision", args=[booking.pk]),
            {"action": "reject", "rejection_reason": "Unavailable on this date."},
        )
        self.assertRedirects(response, reverse("seller-bookings"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.REJECTED)
        self.assertIn("Unavailable on this date.", booking.rejection_reason)
        first_decision.refresh_from_db()
        self.assertEqual(first_decision.status, BookingSellerDecision.Status.ACCEPTED)

    def test_custom_package_event_seller_can_review_their_request(self):
        event_user = get_user_model().objects.create_user(
            username="custom-package-event-seller",
            email="event-seller@example.com",
            password="test-password",
        )
        Profile.objects.create(user=event_user, role="SELLER")
        event_seller = Seller.objects.create(
            user=event_user,
            business_name="Event Venue Seller",
        )
        self.event.seller = event_seller
        self.event.save(update_fields=["seller"])
        package = EventPackage.objects.create(
            user=self.customer,
            event=self.event,
            event_date=date.today() + timedelta(days=20),
            event_price=1000,
            total_cost=1500,
        )
        PackageService.objects.create(
            package=package,
            service=self.package.package_items.get().service,
            selected_price=500,
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
        booking.package_services.set(
            package.package_services.values_list("service_id", flat=True)
        )
        ensure_booking_seller_decisions(booking)

        self.client.force_login(event_user)
        dashboard_response = self.client.get(reverse("seller-dashboard"))
        self.assertContains(dashboard_response, "Custom package requests")
        self.assertContains(dashboard_response, self.event.title)
        response = self.client.post(
            reverse("seller-booking-decision", args=[booking.pk]),
            {"action": "accept"},
        )

        self.assertRedirects(response, reverse("seller-bookings"))
        decision = BookingSellerDecision.objects.get(
            booking=booking,
            seller=event_seller,
        )
        self.assertEqual(decision.status, BookingSellerDecision.Status.ACCEPTED)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)

    def test_seller_can_request_matured_earnings_and_admin_can_mark_paid(self):
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CATALOG_PACKAGE,
            catalog_package=self.package,
            package_event=self.event,
            seller=self.seller,
            booking_date=date.today(),
            total_price=1000,
            item_title=self.package.title,
            status=Booking.Status.COMPLETED,
            customer_confirmed_at=timezone.now(),
            admin_completed_at=timezone.now(),
        )
        earning = SellerEarning.objects.create(
            booking=booking,
            seller=self.seller,
            commission_amount=100,
            seller_amount=900,
            available_on=date.today(),
        )

        self.client.force_login(self.seller.user)
        response = self.client.post(reverse("seller-payments"))
        self.assertRedirects(response, reverse("seller-payments"))
        payout = PayoutRequest.objects.get(seller=self.seller)
        self.assertEqual(payout.amount, 900)
        earning.refresh_from_db()
        self.assertEqual(earning.payout_request, payout)

        admin = get_user_model().objects.create_superuser(
            username="payment-admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(admin)
        response = self.client.post(
            reverse("admin-payments"),
            {
                "payout_id": payout.pk,
                "action": "paid",
                "payment_method": "UPI",
                "payment_reference": "UTR-123",
            },
        )
        self.assertRedirects(response, reverse("admin-payments"))
        payout.refresh_from_db()
        self.assertEqual(payout.status, PayoutRequest.Status.PAID)
        self.assertEqual(payout.payment_reference, "UTR-123")

    def test_completion_requires_seller_report_customer_confirmation_and_admin_approval(self):
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CATALOG_PACKAGE,
            catalog_package=self.package,
            package_event=self.event,
            seller=self.seller,
            booking_date=date.today() - timedelta(days=2),
            total_price=1000,
            item_title=self.package.title,
            status=Booking.Status.CONFIRMED,
        )
        decision = BookingSellerDecision.objects.create(
            booking=booking,
            seller=self.seller,
            status=BookingSellerDecision.Status.ACCEPTED,
        )
        earning = SellerEarning.objects.create(
            booking=booking,
            seller=self.seller,
            commission_amount=100,
            seller_amount=900,
            available_on=date.today() - timedelta(days=1),
        )
        admin = get_user_model().objects.create_superuser(
            username="completion-admin",
            email="completion-admin@example.com",
        )

        self.client.force_login(admin)
        response = self.client.post(
            reverse("admin-complete-booking", args=[booking.pk])
        )
        self.assertRedirects(response, reverse("admin-bookings"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertIsNone(booking.admin_completed_at)

        self.client.force_login(self.customer)
        detail = self.client.get(reverse("booking-detail", args=[booking.pk]))
        self.assertContains(detail, "Confirm event completed")
        self.assertContains(detail, 'disabled aria-describedby="completion-hint"')
        response = self.client.post(
            reverse("confirm-booking-completion", args=[booking.pk])
        )
        self.assertRedirects(response, reverse("booking-detail", args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

        self.client.force_login(self.seller.user)
        response = self.client.post(
            reverse("seller-report-booking-completion", args=[booking.pk])
        )
        self.assertRedirects(response, reverse("seller-bookings"))
        decision.refresh_from_db()
        self.assertIsNotNone(decision.seller_completed_at)
        seller_bookings = self.client.get(reverse("seller-bookings"))
        self.assertContains(seller_bookings, "Seller complete · awaiting customer")

        response = self.client.post(reverse("seller-payments"))
        self.assertRedirects(response, reverse("seller-payments"))
        self.assertFalse(PayoutRequest.objects.filter(seller=self.seller).exists())
        earning.refresh_from_db()
        self.assertIsNone(earning.payout_request)

        self.client.force_login(self.customer)
        detail = self.client.get(reverse("booking-detail", args=[booking.pk]))
        self.assertNotContains(detail, 'disabled aria-describedby="completion-hint"')
        response = self.client.post(
            reverse("confirm-booking-completion", args=[booking.pk])
        )
        self.assertRedirects(response, reverse("booking-detail", args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertIsNotNone(booking.customer_confirmed_at)
        self.assertIsNone(booking.admin_completed_at)

<<<<<<< HEAD
        detail = self.client.get(reverse("booking-detail", args=[booking.pk]))
        self.assertContains(detail, "Review this package")
        self.assertNotContains(detail, "Request cancellation")
        cancellation_response = self.client.post(
            reverse("cancel-booking", args=[booking.pk]),
            {"reason": "No longer needed"},
        )
        self.assertRedirects(
            cancellation_response,
            reverse("booking-detail", args=[booking.pk]),
        )
        self.assertFalse(
            BookingCancellationRequest.objects.filter(booking=booking).exists()
        )

        review_response = self.client.post(
            reverse("submit-package-review", args=[booking.pk]),
            {"rating": "5", "comment": "The event was completed successfully."},
        )
        self.assertRedirects(
            review_response,
            reverse("booking-detail", args=[booking.pk]),
        )
        self.assertTrue(PackageReview.objects.filter(booking=booking).exists())
        self.assertEqual(booking.service_reviews.count(), 1)

=======
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
        self.client.force_login(self.seller.user)
        seller_dashboard = self.client.get(reverse("seller-dashboard"))
        self.assertEqual(seller_dashboard.context["available_total"], 0)
        response = self.client.get(reverse("seller-payments"))
        self.assertEqual(response.context["available_total"], 0)
        response = self.client.post(reverse("seller-payments"))
        self.assertRedirects(response, reverse("seller-payments"))
        self.assertFalse(PayoutRequest.objects.filter(seller=self.seller).exists())

        self.client.force_login(admin)
        admin_bookings = self.client.get(reverse("admin-bookings"))
        self.assertContains(admin_bookings, "Approve completion")
        self.assertEqual(admin_bookings.context["ready_for_admin_count"], 1)
        response = self.client.post(
            reverse("admin-complete-booking", args=[booking.pk])
        )
        self.assertRedirects(response, reverse("admin-bookings"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.COMPLETED)
        self.assertIsNotNone(booking.admin_completed_at)

        self.client.force_login(self.seller.user)
        seller_bookings = self.client.get(reverse("seller-bookings"))
        self.assertContains(seller_bookings, "Complete · admin approved")
        seller_dashboard = self.client.get(reverse("seller-dashboard"))
        self.assertEqual(seller_dashboard.context["available_total"], 900)
        response = self.client.get(reverse("seller-payments"))
        self.assertEqual(response.context["available_total"], 900)
        response = self.client.post(reverse("seller-payments"))
        self.assertRedirects(response, reverse("seller-payments"))
        self.assertEqual(PayoutRequest.objects.get(seller=self.seller).amount, 900)

    def test_admin_cannot_pay_a_payout_without_admin_completion_approval(self):
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CATALOG_PACKAGE,
            catalog_package=self.package,
            package_event=self.event,
            seller=self.seller,
            booking_date=date.today() - timedelta(days=2),
            total_price=1000,
            item_title=self.package.title,
            status=Booking.Status.CONFIRMED,
            customer_confirmed_at=timezone.now(),
        )
        payout = PayoutRequest.objects.create(
            seller=self.seller,
            amount=900,
        )
        SellerEarning.objects.create(
            booking=booking,
            seller=self.seller,
            commission_amount=100,
            seller_amount=900,
            available_on=date.today() - timedelta(days=1),
            payout_request=payout,
        )
        admin = get_user_model().objects.create_superuser(
            username="unconfirmed-payout-admin",
            email="unconfirmed-payout-admin@example.com",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("admin-payments"),
            {
                "payout_id": payout.pk,
                "action": "paid",
                "payment_method": "UPI",
                "payment_reference": "UTR-UNCONFIRMED",
            },
        )

        self.assertRedirects(response, reverse("admin-payments"))
        payout.refresh_from_db()
        self.assertEqual(payout.status, PayoutRequest.Status.REQUESTED)

<<<<<<< HEAD
    def test_admin_can_pay_each_seller_share_for_a_completed_multi_seller_booking(self):
        second_user = get_user_model().objects.create_user(
            username="admin-multi-payout-seller",
            email="admin-multi-payout-seller@example.com",
            password="test-password",
        )
        Profile.objects.create(user=second_user, role="SELLER")
        second_seller = Seller.objects.create(
            user=second_user,
            business_name="Second payout seller",
        )
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CUSTOM_PACKAGE,
            custom_package=EventPackage.objects.create(
                user=self.customer,
                event=self.event,
                event_date=date.today() - timedelta(days=2),
                total_cost=1500,
            ),
            booking_date=date.today() - timedelta(days=2),
            total_price=1800,
            item_title="Multiple seller package",
            status=Booking.Status.COMPLETED,
            admin_completed_at=timezone.now(),
        )
        first_earning = SellerEarning.objects.create(
            booking=booking,
            seller=self.seller,
            commission_amount=120,
            seller_amount=1080,
            available_on=date.today(),
        )
        second_earning = SellerEarning.objects.create(
            booking=booking,
            seller=second_seller,
            commission_amount=60,
            seller_amount=540,
            available_on=date.today(),
        )
        admin = get_user_model().objects.create_superuser(
            username="multi-payout-admin",
            email="multi-payout-admin@example.com",
        )
        self.client.force_login(admin)

        page = self.client.get(reverse("admin-payments"))
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.context["available_seller_payouts"]), 2)
        self.assertContains(page, "Completed earnings ready for payout")
        self.assertContains(page, "Second payout seller")

        for seller, amount, reference in (
            (self.seller, "1080.00", "UTR-FIRST"),
            (second_seller, "540.00", "UTR-SECOND"),
        ):
            response = self.client.post(
                reverse("admin-payments"),
                {
                    "action": "pay_available",
                    "seller_id": seller.pk,
                    "payment_method": "UPI",
                    "payment_reference": reference,
                },
            )
            self.assertRedirects(response, reverse("admin-payments"))
            payout = PayoutRequest.objects.get(seller=seller)
            self.assertEqual(payout.amount, Decimal(amount))
            self.assertEqual(payout.status, PayoutRequest.Status.PAID)
            self.assertEqual(payout.payment_reference, reference)

        first_earning.refresh_from_db()
        second_earning.refresh_from_db()
        self.assertNotEqual(first_earning.payout_request_id, second_earning.payout_request_id)
        self.assertEqual(
            SellerEarning.objects.filter(
                booking=booking,
                payout_request__status=PayoutRequest.Status.PAID,
            ).count(),
            2,
        )

=======
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
    def test_seller_and_admin_booking_payment_pages_render(self):
        booking = Booking.objects.create(
            user=self.customer,
            item_type=Booking.ItemType.CATALOG_PACKAGE,
            catalog_package=self.package,
            package_event=self.event,
            seller=self.seller,
            booking_date=date.today(),
            total_price=1000,
            item_title=self.package.title,
        )
        booking.package_services.set(
            self.package.package_items.values_list("service_id", flat=True)
        )

        self.client.force_login(self.seller.user)
        seller_bookings = self.client.get(reverse("seller-bookings"))
        self.assertEqual(seller_bookings.status_code, 200)
        self.assertContains(seller_bookings, "Bookings &amp; completion")
        self.assertContains(seller_bookings, "Pending response")
        self.assertEqual(self.client.get(reverse("seller-payments")).status_code, 200)
        self.assertEqual(self.client.get(reverse("seller-dashboard")).status_code, 200)

        admin = get_user_model().objects.create_superuser(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="test-password",
        )
        self.client.force_login(admin)
        bookings_response = self.client.get(reverse("admin-bookings"))
        self.assertEqual(bookings_response.status_code, 200)
        self.assertContains(bookings_response, self.customer.email)
        self.assertContains(bookings_response, "Booking management")
        payments_response = self.client.get(reverse("admin-payments"))
        self.assertEqual(payments_response.status_code, 200)
        self.assertContains(payments_response, "Customer payment transactions")
        self.assertContains(payments_response, "Seller payout transactions")
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    @override_settings(RAZORPAY_WEBHOOK_SECRET="test-webhook-secret")
    def test_razorpay_webhook_accepts_valid_signature(self):
        payload = json.dumps({"event": "payment.failed"}).encode()
        signature = hmac.new(
            b"test-webhook-secret",
            payload,
            hashlib.sha256,
        ).hexdigest()

        response = self.client.post(
            reverse("razorpay-webhook"),
            data=payload,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ignored"})

    @override_settings(RAZORPAY_WEBHOOK_SECRET="test-webhook-secret")
    def test_razorpay_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            reverse("razorpay-webhook"),
            data=b'{"event":"payment.failed"}',
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE="invalid-signature",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"error": "Invalid webhook signature."},
        )
