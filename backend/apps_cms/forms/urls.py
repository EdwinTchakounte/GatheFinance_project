from django.urls import path

from . import views

app_name = "site_forms"

urlpatterns = [
    path("captcha/", views.captcha_challenge, name="captcha"),
    path("contact/", views.contact, name="contact"),
    path("adhesion/", views.membership, name="membership"),
    path("newsletter/", views.newsletter, name="newsletter"),
]
