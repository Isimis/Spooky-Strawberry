from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("jakosc-danych/odswiez/", views.refresh_quality, name="refresh_quality"),
    path("products/<int:pk>/panel/", views.product_workspace, name="product_workspace"),
    path("outfits/nowy/panel/", views.outfit_create_workspace, name="outfit_create_workspace"),
    path("outfits/<int:pk>/panel/", views.outfit_workspace, name="outfit_workspace"),
    path("articles/nowy/panel/", views.article_create_workspace, name="article_create_workspace"),
    path("articles/<int:pk>/panel/", views.article_workspace, name="article_workspace"),
    path("<slug:model_slug>/", views.model_list, name="model_list"),
    path("<slug:model_slug>/nowy/", views.model_create, name="model_create"),
    path("<slug:model_slug>/<int:pk>/edytuj/", views.model_edit, name="model_edit"),
    path("<slug:model_slug>/<int:pk>/usun/", views.model_delete, name="model_delete"),
]
