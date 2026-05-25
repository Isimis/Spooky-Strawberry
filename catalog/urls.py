from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("sklep/", views.product_list, name="product_list"),
    path("produkt/<slug:slug>/", views.product_detail, name="product_detail"),
]
