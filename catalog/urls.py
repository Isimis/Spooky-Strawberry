from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("sklep/", views.product_list, name="product_list"),
    path("kategoria/<slug:slug>/", views.category_detail, name="category_detail"),
    path("produkt/<slug:slug>/", views.product_detail, name="product_detail"),
    path("estetyki/", views.aesthetic_list, name="aesthetic_list"),
    path("quiz-stylu/", views.style_quiz, name="style_quiz"),
    path("estetyki/<slug:slug>/", views.aesthetic_detail, name="aesthetic_detail"),
]
