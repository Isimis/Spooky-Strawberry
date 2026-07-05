from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("session_id", "order", "provider", "amount", "status", "created_at", "paid_at")
    list_filter = ("provider", "status", "created_at")
    search_fields = ("session_id", "p24_order_id", "order__order_number", "order__email")
    readonly_fields = ("created_at", "updated_at", "paid_at", "raw_register", "raw_notification")
