from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("platnosci/przelewy24/webhook/", views.przelewy24_webhook, name="p24_webhook"),
]
