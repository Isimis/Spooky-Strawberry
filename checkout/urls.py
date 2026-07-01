from django.urls import path

from . import views

app_name = "checkout"

urlpatterns = [
    path("zamowienie/dostawa/", views.shipping, name="shipping"),
    path("zamowienie/platnosc/", views.payment, name="payment"),
    path("zamowienie/potwierdzenie/<str:order_number>/<str:token>/", views.confirmation, name="confirmation"),
]
