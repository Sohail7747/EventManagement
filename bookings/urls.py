
from django.urls import path

from . import views

urlpatterns = [
    # =========================
    # USER HTML PAGES
    # =========================
    path(
        "packages/details/<int:package_id>/",
        views.package_detail_page,
        name="public-package-detail",
    ),
    path(
        "my-account/",
        views.user_dashboard_page,
        name="user-dashboard",
    ),
    path(
        "my-account/bookings/",
        views.my_bookings_page,
        name="my-bookings",
    ),
    path(
        "my-account/bookings/<int:pk>/",
        views.booking_detail_page,
        name="booking-detail",
    ),
    path(
        "my-account/bookings/<int:pk>/cancel/",
        views.cancel_booking_page,
        name="cancel-booking",
    ),
    path(
        "my-account/bookings/<int:pk>/review/",
        views.submit_package_review,
        name="submit-package-review",
    ),
    path(
        "my-account/bookings/<int:pk>/confirm-completion/",
        views.confirm_booking_completion,
        name="confirm-booking-completion",
    ),
    path(
        "my-account/bookings/<int:pk>/reject-completion/",
        views.reject_booking_completion,
        name="reject-booking-completion",
    ),
    path(
        "my-account/favourites/",
        views.my_favourites_page,
        name="my-favourites",
    ),
    path(
        "my-account/favourites/<int:pk>/remove/",
        views.remove_favourite_page,
        name="remove-favourite",
    ),
    path(
        "my-account/favourites/packages/<int:package_id>/toggle/",
        views.toggle_package_favourite,
        name="toggle-package-favourite",
    ),
    path(
        "my-account/profile/",
        views.user_profile_page,
        name="user-profile",
    ),
    path(
        "profile/",
        views.user_profile_page,
        name="profile",
    ),

    # =========================
    # BOOKING REST APIs
    # =========================
    path(
        "api/bookings/",
        views.bookings_api,
        name="bookings-api",
    ),
    path(
        "api/bookings/<int:pk>/",
        views.booking_detail_api,
        name="booking-detail-api",
    ),
    path(
        "api/bookings/<int:pk>/cancel/",
        views.cancel_booking_api,
        name="cancel-booking-api",
    ),

    # =========================
    # FAVOURITES REST APIs
    # =========================
    path(
        "api/favourites/",
        views.favourites_api,
        name="favourites-api",
    ),
    path(
        "api/favourites/<int:pk>/",
        views.remove_favourite_api,
        name="remove-favourite-api",
    ),
]
