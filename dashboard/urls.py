from django.urls import path
from . import views

urlpatterns = [
    # Dashboard pages
    path("admin-dashboard/", views.dashboard_page, name="dashboard"),
    path("seller/", views.sellers_home_page, name="seller-home"),
    path("users/", views.users_page, name="users"),

    # Dashboard APIs
    path("api/dashboard/", views.dashboard_api, name="api-dashboard"),
    path("api/seller-home/", views.seller_home_api, name="api-seller-home"),

    # Admin Users CRUD APIs
    path("api/users/", views.AdminUserListCreateAPI.as_view(), name="api-users"),
    path("api/users/<int:pk>/", views.AdminUserDetailAPI.as_view(), name="api-user-detail"),

    # Admin Seller CRUD APIs
    path("api/sellers/", views.AdminSellerListCreateAPI.as_view(), name="api-sellers"),
    path("api/sellers/<int:pk>/", views.AdminSellerDetailAPI.as_view(), name="api-seller-detail"),

    path("admin-sellers/", views.sellers_page, name="admin-sellers"),
    path("api/seller-accounts/", views.seller_accounts_api, name="api-seller-accounts"),

    
    # Events CRUD
    path("events/", views.events_page, name="admin-events"),
    path("events/create/", views.event_create, name="event-create"),
    path("events/<int:pk>/", views.event_detail, name="event-detail"),
    path("events/<int:pk>/edit/", views.event_edit, name="event-edit"),
    path("events/<int:pk>/delete/", views.event_delete, name="event-delete"),
    
    # Services CRUD
    path("services/", views.services_page, name="admin-services"),
    path("services/create/", views.service_create, name="service-create"),
    path("services/<int:pk>/", views.service_detail, name="service-detail"),
    path("services/<int:pk>/edit/", views.service_edit, name="service-edit"),
    path("services/<int:pk>/delete/", views.service_delete, name="service-delete"),

    # Static pages CRUD
    path("static-pages/", views.static_pages_page, name="admin-static-pages"),
    path("static-pages/create/", views.static_page_create, name="static-page-create"),
    path("static-pages/<int:pk>/", views.static_page_detail, name="static-page-detail"),
    path("static-pages/<int:pk>/edit/", views.static_page_edit, name="static-page-edit"),
    path("static-pages/<int:pk>/delete/", views.static_page_delete, name="static-page-delete"),

    # Admin Catalog Packages
    path(
        "packages/",
        views.catalog_packages_page,
        name="admin-catalog-packages",
    ),
    path(
        "packages/<int:pk>/",
        views.admin_catalog_package_detail,
        name="admin-catalog-package-detail",
    ),
    path(
        "packages/<int:pk>/delete/",
        views.admin_catalog_package_delete,
        name="admin-catalog-package-delete",
    ),
    
]   