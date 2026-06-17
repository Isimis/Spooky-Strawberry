from django.urls import path

from . import views

app_name = "outfits"

urlpatterns = [
    path("stylizacje/", views.outfit_list, name="list"),
    path("stylizacje/<slug:slug>/", views.outfit_detail, name="detail"),
]
