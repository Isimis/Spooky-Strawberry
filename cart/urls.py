from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("koszyk/", views.cart_detail, name="detail"),
    path("koszyk/dodaj/", views.add_item, name="add"),
    path("koszyk/dodaj-zestaw/<slug:slug>/", views.add_outfit, name="add_outfit"),
    path("koszyk/aktualizuj/<int:variant_id>/", views.update_item, name="update"),
    path("koszyk/usun/<int:variant_id>/", views.remove_item, name="remove"),
    path("koszyk/wyczysc/", views.clear_items, name="clear"),
    path("koszyk/kod-rabatowy/", views.apply_discount, name="discount_apply"),
    path("koszyk/kod-rabatowy/usun/", views.remove_discount, name="discount_remove"),
]
