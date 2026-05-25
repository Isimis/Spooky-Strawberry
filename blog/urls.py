from django.urls import path

from . import views

app_name = "blog"

urlpatterns = [
    path("poradniki/", views.article_list, name="list"),
    path("poradniki/<slug:slug>/", views.article_detail, name="article_detail"),
]
