from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("koszyk/", views.cart_detail, name="detail"),
    path("koszyk/dodaj/", views.add_item, name="add"),
    path("koszyk/aktualizuj/<int:variant_id>/", views.update_item, name="update"),
    path("koszyk/usun/<int:variant_id>/", views.remove_item, name="remove"),
    path("koszyk/wyczysc/", views.clear_items, name="clear"),
]
