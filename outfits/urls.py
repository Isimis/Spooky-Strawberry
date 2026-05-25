from django.urls import path

from . import views

app_name = "outfits"

urlpatterns = [
    path("gotowe-kreacje/", views.outfit_list, name="list"),
    path("gotowe-kreacje/<slug:slug>/", views.outfit_detail, name="detail"),
]
