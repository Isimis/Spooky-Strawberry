from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("kontakt/", views.contact_view, name="contact"),
    path("dostawa/", views.shipping_view, name="shipping"),
    path("zwroty/", views.returns_view, name="returns"),
    path("regulamin/", views.terms_view, name="terms"),
    path("polityka-prywatnosci/", views.privacy_view, name="privacy"),
    path("ustawienia-cookie/", views.cookies_view, name="cookies"),
    path("o-nas/", views.about_view, name="about"),
    path("dostepnosc/", views.accessibility_view, name="accessibility"),
    path("mapa-strony/", views.sitemap_view, name="sitemap"),
    path("status-zamowienia/", views.order_status_view, name="order_status"),
    path("design-system/", views.design_system_view, name="design_system"),
    path("szukaj/", views.search_view, name="search"),
    path("koszyk/", views.cart_view, name="cart"),
    path("konto/", views.account_view, name="account"),
    path("polityki/<slug:slug>/", views.policy_view, name="policy"),
    path("newsletter/zapisz/", views.newsletter_subscribe, name="newsletter_subscribe"),
]
