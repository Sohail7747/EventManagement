from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_page, name="home"),

    # Public listing pages
    path("explore/events/", views.events_page, name="public-events"),
    path("explore/services/", views.services_page, name="public-services"),
    path("explore/packages/", views.packages_page, name="public-packages"),

    # Information pages
    path("about/", views.about_page, name="about"),
    path("contact/", views.contact_page, name="contact"),
]