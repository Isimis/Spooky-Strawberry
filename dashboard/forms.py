from django import forms
from django.forms import inlineformset_factory
from django.forms import modelform_factory

from catalog.models import Product, ProductImage, ProductVariant


def build_model_form(model):
    form_class = modelform_factory(model, fields="__all__")
    for field in form_class.base_fields.values():
        field.widget.attrs.setdefault("class", "dashboard-input")
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = "dashboard-checkbox"
        if isinstance(field.widget, forms.SelectMultiple):
            field.widget.attrs["class"] = "dashboard-input dashboard-multiselect"
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs.setdefault("rows", 5)
    return form_class


class DashboardFormMixin:
    def apply_dashboard_widgets(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "dashboard-input")
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "dashboard-checkbox"
            if isinstance(field.widget, forms.SelectMultiple):
                field.widget.attrs["class"] = "dashboard-input dashboard-multiselect"
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 5)


class ProductDashboardForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "category",
            "aesthetics",
            "short_description",
            "mood_description",
            "details",
            "styling_tips",
            "base_price",
            "compare_at_price",
            "is_featured",
            "is_new_drop",
            "sort_order",
            "seo_title",
            "seo_description",
            "status",
        ]
        widgets = {
            "short_description": forms.Textarea(attrs={"rows": 3}),
            "mood_description": forms.Textarea(attrs={"rows": 5}),
            "details": forms.Textarea(attrs={"rows": 5}),
            "styling_tips": forms.Textarea(attrs={"rows": 4}),
            "seo_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()


class ProductVariantInlineForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = [
            "color",
            "size",
            "sku",
            "price_override",
            "stock_quantity",
            "is_active",
            "sort_order",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()


class ProductImageInlineForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = [
            "variant",
            "image",
            "alt_text",
            "caption",
            "sort_order",
            "is_main",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        if self.instance and self.instance.product_id:
            self.fields["variant"].queryset = self.instance.product.variants.all()


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantInlineForm,
    extra=2,
    can_delete=True,
)

ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageInlineForm,
    extra=2,
    can_delete=True,
)
