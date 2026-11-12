from django.urls import path

from . import views


urlpatterns = [
    path(
        "packages/<int:package_id>/book/",
        views.package_booking_page,
        name="package-booking",
    ),
    path(
        "my-account/packages/<int:package_id>/book/",
        views.custom_package_booking_page,
        name="custom-package-booking",
    ),
    path(
        "packages/payment/verify/",
        views.verify_package_payment,
        name="verify-package-payment",
    ),
    path(
        "api/payments/razorpay/webhook/",
        views.razorpay_webhook,
        name="razorpay-webhook",
    ),
    path(
        "seller/bookings/",
        views.seller_bookings_page,
        name="seller-bookings",
    ),
    path(
        "seller/availability/",
        views.seller_availability_page,
        name="seller-availability",
    ),
    path(
        "seller/bookings/<int:booking_id>/decision/",
        views.seller_booking_decision,
        name="seller-booking-decision",
    ),
    path(
        "seller/bookings/<int:booking_id>/report-completion/",
        views.seller_report_booking_completion,
        name="seller-report-booking-completion",
    ),
    path(
        "seller/payments/",
        views.seller_payments_page,
        name="seller-payments",
    ),
    path(
        "admin-dashboard/bookings/",
        views.admin_bookings_page,
        name="admin-bookings",
    ),
    path(
        "admin-dashboard/bookings/<int:booking_id>/complete/",
        views.admin_complete_booking,
        name="admin-complete-booking",
    ),
    path(
        "admin-dashboard/cancellations/<int:request_id>/process/",
        views.admin_process_cancellation,
        name="admin-process-cancellation",
    ),
    # path(
    #     "admin-dashboard/bookings/<int:booking_id>/payout-seller/",
    #     views.admin_payout_booking_seller,
    #     name="admin-payout-booking-seller",
    # ),
    path(
        "admin-dashboard/payments/",
        views.admin_payments_page,
        name="admin-payments",
    ),
    path(
        "api/packages/<int:package_id>/availability/",
        views.package_availability_api,
        name="package-availability",
    ),
    path(
        "api/my-account/packages/<int:package_id>/availability/",
        views.custom_package_availability_api,
        name="custom-package-availability",
    ),
]
