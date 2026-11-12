from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from bookings.models import Favourite
from dashboard.models import Event, Profile, Seller, Service
from packages.models import CatalogPackage, CatalogPackageItem


class HomeAuthenticationTests(TestCase):
    def test_homepage_is_public_and_shows_login_actions(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in")
        self.assertContains(response, "Get Started")
        self.assertNotContains(response, "My Dashboard")

    def test_anonymous_visitors_can_navigate_public_pages(self):
        for page_name in (
            "home",
            "public-events",
            "public-services",
            "public-packages",
            "about",
            "contact",
        ):
            with self.subTest(page=page_name):
                response = self.client.get(reverse(page_name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Log in")
                self.assertContains(response, "Get Started")

    def test_authenticated_visitors_can_view_homepage(self):
        user = User.objects.create_user(
            username="home-visitor",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-hero-slider")
        self.assertContains(response, "data-hero-next")
        self.assertContains(response, "data-hero-pause")
        self.assertContains(response, "home/images/hero-wedding.webp")
        self.assertContains(response, "home/images/hero-celebration.webp")
        self.assertContains(response, "home/images/hero-event.webp")
        self.assertNotContains(response, "images.unsplash.com")
        self.assertContains(response, "Find your people.")
        self.assertContains(response, "Your event,")
        self.assertContains(response, "page-loader")
        self.assertContains(response, "home/js/home.js")
        self.assertNotContains(response, "Patna")

    def test_start_planning_sends_logged_in_customer_to_package_finder(self):
        user = User.objects.create_user(
            username="home-planning-customer",
            password="test-password",
        )
        Profile.objects.create(user=user, role="USER")
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'id="start-planning-cta" href="{reverse("package-selection")}"',
        )

    def test_start_planning_sends_signed_out_visitor_to_registration(self):
        response = self.client.get(reverse("home"))

        self.assertContains(
            response,
            'id="start-planning-cta" href="/accounts/register/"',
        )

    def test_staff_user_sees_login_and_get_started_in_public_header(self):
        admin = User.objects.create_user(
            username="public-header-admin",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(admin)

        response = self.client.get(reverse("public-events"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log in")
        self.assertContains(response, "Get Started")
        self.assertNotContains(response, "Admin Panel")


class PublicListingFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="listing-seller",
            password="test-password",
        )
        self.seller = Seller.objects.create(
            user=self.user,
            business_name="Celebrations Co.",
        )
        self.event = Event.objects.create(
            title="Wedding Celebration",
            description="A joyful outdoor celebration",
            location="Patna",
            event_date=date.today() + timedelta(days=30),
            price=1000,
            seller=self.seller,
        )
        self.other_event = Event.objects.create(
            title="Birthday Gathering",
            description="A family birthday",
            location="Delhi",
            event_date=date.today() + timedelta(days=45),
            price=500,
            seller=self.seller,
        )
        self.service = Service.objects.create(
            name="Wedding Photography",
            description="Photography for your special day",
            price=500,
            seller=self.seller,
        )
        self.expensive_service = Service.objects.create(
            name="Premium Catering",
            description="Full-service catering",
            price=1500,
            seller=self.seller,
        )
        self.package = CatalogPackage.objects.create(
            title="Wedding Essentials",
            description="A curated wedding package",
            event=self.event,
            seller=self.seller,
        )
        CatalogPackageItem.objects.create(
            package=self.package,
            service=self.service,
            selected_price=500,
        )
        self.other_package = CatalogPackage.objects.create(
            title="Birthday Collection",
            description="A birthday package",
            event=self.other_event,
            seller=self.seller,
        )
        CatalogPackageItem.objects.create(
            package=self.other_package,
            service=self.expensive_service,
            selected_price=1500,
        )

    def test_homepage_has_horizontal_catalog_carousels_and_explore_links(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-home-carousel")
        self.assertContains(response, 'id="home-events-track"')
        self.assertContains(response, 'id="home-services-track"')
        self.assertContains(response, 'id="home-packages-track"')
        self.assertContains(response, reverse("public-events"))
        self.assertContains(response, reverse("public-services"))
        self.assertContains(response, reverse("public-packages"))
        self.assertContains(response, "Explore more events")
        self.assertContains(response, "Explore more services")
        self.assertContains(response, "Explore more packages")

    def test_event_listing_ignores_search_and_hides_location(self):
        response = self.client.get(
            reverse("public-events"),
            {"q": "wedding", "location": "Patna"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)
        self.assertContains(response, self.other_event.title)
        self.assertNotContains(response, "Search events")
        self.assertNotContains(response, "Patna")
        self.assertNotContains(response, "Location")

    def test_service_listing_ignores_filters_and_hides_price(self):
        response = self.client.get(
            reverse("public-services"),
            {"q": "photography", "max_price": "600"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service.name)
        self.assertContains(response, self.expensive_service.name)
        self.assertNotContains(response, "Search services")
        self.assertNotContains(response, "Maximum price")
        self.assertNotContains(response, "₹500")

    def test_package_search_and_event_filter(self):
        search_response = self.client.get(
            reverse("public-packages"),
            {"q": "photography"},
        )
        self.assertContains(search_response, self.package.title)
        self.assertNotContains(search_response, self.other_package.title)

        event_response = self.client.get(
            reverse("public-packages"),
            {"event": str(self.other_event.pk)},
        )
        self.assertContains(event_response, self.other_package.title)
        self.assertNotContains(event_response, self.package.title)

    def test_package_listing_paginates_large_catalogs(self):
        for index in range(11):
            CatalogPackage.objects.create(
                title=f"Additional package {index}",
                description="Additional listing package",
                event=self.event,
                seller=self.seller,
            )

        response = self.client.get(reverse("public-packages"), {"page": "2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 13)
        self.assertEqual(len(response.context["packages"]), 1)

    def test_customer_can_favourite_a_package_from_listing_and_view_it_in_favourites(self):
        customer = User.objects.create_user(username="package-favourite-customer")
        Profile.objects.create(user=customer, role="USER")
        self.client.force_login(customer)

        listing = self.client.get(reverse("public-packages"))
        self.assertContains(listing, "Add to favorites")
        self.assertContains(listing, self.package.title)

        response = self.client.post(
            reverse("toggle-package-favourite", args=[self.package.pk]),
            {"next": reverse("public-packages")},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_favourite"])
        self.assertTrue(
            Favourite.objects.filter(
                user=customer,
                catalog_package=self.package,
            ).exists()
        )

        favourites_page = self.client.get(reverse("my-favourites"))
        self.assertEqual(favourites_page.status_code, 200)
        self.assertContains(favourites_page, self.package.title)
        self.assertEqual(favourites_page.context["favourite_package_count"], 1)

        detail = self.client.get(
            reverse("public-package-detail", args=[self.package.pk])
        )
        self.assertContains(detail, "Remove Wedding Essentials from favorites")

    def test_customer_can_remove_package_from_favourites_and_external_next_is_ignored(self):
        customer = User.objects.create_user(username="remove-package-favourite")
        Profile.objects.create(user=customer, role="USER")
        Favourite.objects.create(user=customer, catalog_package=self.package)
        self.client.force_login(customer)

        response = self.client.post(
            reverse("toggle-package-favourite", args=[self.package.pk]),
            {"next": "https://example.com/"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_favourite"])
        self.assertFalse(
            Favourite.objects.filter(
                user=customer,
                catalog_package=self.package,
            ).exists()
        )

    def test_non_customer_cannot_toggle_package_favourite(self):
        response = self.client.post(
            reverse("toggle-package-favourite", args=[self.package.pk]),
            {"next": reverse("public-packages")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts-login-page")))
        self.assertFalse(Favourite.objects.exists())

    def test_signed_in_footer_hides_login_option(self):
        Profile.objects.create(user=self.user, role="USER")
        self.client.force_login(self.user)

        response = self.client.get(reverse("public-services"))

        self.assertContains(response, "You're signed in")
        self.assertNotContains(response, ">Log in</a>")

    def test_guest_footer_offers_login_and_registration(self):
        response = self.client.get(reverse("public-services"))

        self.assertContains(response, "Log in")
        self.assertContains(response, "Create an account")
