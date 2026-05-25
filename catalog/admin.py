from django.contrib import admin
from .models import Aesthetic, Category, Color, Product, ProductImage, ProductVariant, Size


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "base_price",
        "status",
        "is_featured",
        "is_new_drop",
        "created_at",
    ]
    list_filter = [
        "status",
        "category",
        "aesthetics",
        "is_featured",
        "is_new_drop",
    ]
    search_fields = ["name", "short_description", "mood_description"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductVariantInline, ProductImageInline]


admin.site.register(Category)
admin.site.register(Aesthetic)
admin.site.register(Color)
admin.site.register(Size)
