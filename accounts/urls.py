from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_page, name="accounts-login-page"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_page, name="accounts-register-page"),

    path("api/registration-options/", views.registration_options_api, name="accounts-registration-options"),
]