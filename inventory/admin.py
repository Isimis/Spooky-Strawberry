from django.contrib import admin

from .models import StockEntry


@admin.register(StockEntry)
class StockEntryAdmin(admin.ModelAdmin):
    list_display = ("variant", "direction", "source", "quantity", "occurred_at", "created_at")
    list_filter = ("direction", "source", "occurred_at")
    search_fields = ("variant__product__name", "note", "supplier_url")
    autocomplete_fields = ()
    date_hierarchy = "occurred_at"
