from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("seller/", include("sellers.urls")),
    path("", include("home.urls")),
<<<<<<< HEAD
    path("", include("admin_panel.urls")),
=======
    path("", include("dashboard.urls")),
>>>>>>> 94851330fda38d03375e41cc7ee79f674bd05b01
    path("", include("packages.urls")),
    path("", include("bookings.urls")),
    path("", include("payments.urls")),
]
if settings.DEBUG:
        urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )   