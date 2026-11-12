from django.urls import path
from . import views

urlpatterns = [

    path("login/", views.login_page, name="accounts-login-page"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register_page, name="accounts-register-page"),

    path("api/registration-options/", views.registration_options_api, name="accounts-registration-options"),
    path("api/register/", views.register_api, name="accounts-register"),
    path("api/login/", views.login_api, name="accounts-login"),
    path("api/logout/", views.logout_api, name="accounts-logout"),
    path("session-test/", views.session_test, name="session-test"),
]