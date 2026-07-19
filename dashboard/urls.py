from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("ustawienia/", views.site_settings, name="site_settings"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("jakosc-danych/odswiez/", views.refresh_quality, name="refresh_quality"),
    path("products/nowy/panel/", views.product_create_workspace, name="product_create_workspace"),
    path("products/<int:pk>/panel/", views.product_workspace, name="product_workspace"),
    path("outfits/nowy/panel/", views.outfit_create_workspace, name="outfit_create_workspace"),
    path("outfits/<int:pk>/panel/", views.outfit_workspace, name="outfit_workspace"),
    path("articles/nowy/panel/", views.article_create_workspace, name="article_create_workspace"),
    path("articles/<int:pk>/panel/", views.article_workspace, name="article_workspace"),
    path("orders/nowy/panel/", views.order_create_workspace, name="order_create_workspace"),
    path("orders/<int:pk>/panel/", views.order_workspace, name="order_workspace"),
    path("order-items/<int:pk>/podglad/", views.order_item_detail, name="order_item_detail"),
    path("magazyn/", views.warehouse, name="warehouse"),
    path("magazyn/wariant/<int:pk>/przyjecie/", views.warehouse_add_entry, name="warehouse_add_entry"),
    path("magazyn/wpis/<int:pk>/usun/", views.warehouse_delete_entry, name="warehouse_delete_entry"),
    path("konta/nowe/", views.user_account_create, name="user_account_create"),
    path("szablony-maili/<int:pk>/", views.email_template_edit, name="email_template_edit"),
    path("szablon-bazowy/", views.base_layout_edit, name="base_layout_edit"),
    path("skrzynka/nowa/", views.message_compose, name="message_compose"),
    path("skrzynka/synchronizuj/", views.sync_messages, name="sync_messages"),
    path("skrzynka/wyslij-do-zaznaczonych/", views.bulk_compose, name="bulk_compose"),
    path("skrzynka/akcja-masowa/", views.bulk_message_action, name="bulk_message_action"),
    path("skrzynka/zalacznik/<int:pk>/pobierz/", views.message_attachment_download, name="message_attachment_download"),
    path("skrzynka/<int:pk>/", views.message_detail, name="message_detail"),
    path("konta/<int:pk>/", views.user_account_detail, name="user_account_detail"),
    path("<slug:model_slug>/", views.model_list, name="model_list"),
    path("<slug:model_slug>/nowy/", views.model_create, name="model_create"),
    path("<slug:model_slug>/<int:pk>/edytuj/", views.model_edit, name="model_edit"),
    path("<slug:model_slug>/<int:pk>/usun/", views.model_delete, name="model_delete"),
]
