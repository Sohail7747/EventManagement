
from django.urls import path
from . import views

urlpatterns = [
    path(
        "api/package-options/",
        views.package_options_api,
        name="package-options",
    ),
    path(
        "api/packages/create/",
        views.create_event_package_api,
        name="create-event-package",
    ),
    path(
        "api/package-builder/availability/",
        views.package_builder_availability_api,
        name="package-builder-availability",
    ),
    path(
        "api/packages/my/",
        views.my_packages_api,
        name="my-packages",
    ),
    path(
        "packages/select/",
        views.package_selection_page,
        name="package-selection",
    ),
    path(
        "my-account/packages/",
        views.my_custom_packages_page,
        name="my-custom-packages",
    ),
    path(
        "my-account/quote-requests/",
        views.my_service_quotes_page,
        name="my-service-quotes",
    ),
    path(
        "quote-requests/create/",
        views.request_service_quote,
        name="request-service-quote",
    ),

    path(
        "catalog/<int:pk>/",
        views.catalog_package_detail,
        name="catalog-package-detail"
    ),

]
