from django.urls import path
from . import views

urlpatterns = [
    path("", views.seller_dashboard, name="seller-dashboard"),
    path(
<<<<<<< HEAD
=======
        "quotes/<int:quote_id>/respond/",
        views.seller_service_quote_response,
        name="seller-service-quote-response",
    ),
    path(
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
    "seller/packages/",
    views.seller_packages,
    name="seller-packages",
    ),
    path(
        "seller/packages/create/",
        views.seller_create_package,
        name="seller-create-package",
    ),
    path(
        "seller/packages/<int:package_id>/",
        views.seller_view_package,
        name="seller-view-package",
    ),
    path(
        "seller/packages/<int:package_id>/edit/",
        views.seller_edit_package,
        name="seller-edit-package",
    ),
    path(
        "seller/packages/<int:package_id>/delete/",
        views.seller_delete_package,
        name="seller-delete-package",
    ),
    path(
    "seller/profile/",
    views.seller_profile,
    name="seller-profile",
    ),
    

]