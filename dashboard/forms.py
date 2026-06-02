import re

from django import forms
from django.forms import inlineformset_factory
from django.forms import modelform_factory

from blog.models import Article, BlogCategory
from catalog.models import Aesthetic, Category, Color, Product, ProductImage, ProductVariant, Size, unique_slug_for
from outfits.models import Outfit, OutfitImage, OutfitItem


def build_model_form(model):
    if model is Category:
        return CategoryDashboardForm
    if model is Aesthetic:
        return AestheticDashboardForm
    if model is Color:
        return ColorDashboardForm
    if model is Size:
        return SizeDashboardForm
    if model is Outfit:
        return OutfitDashboardForm
    if model is Article:
        return ArticleDashboardForm
    if model is BlogCategory:
        return BlogCategoryDashboardForm

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


class AutoSlugDashboardForm(DashboardFormMixin, forms.ModelForm):
    slug_source_field = "name"

    def save(self, commit=True):
        obj = super().save(commit=False)
        previous_value = None
        if obj.pk:
            previous_value = obj.__class__.objects.filter(pk=obj.pk).values_list(self.slug_source_field, flat=True).first()

        current_value = getattr(obj, self.slug_source_field)
        if not obj.slug or previous_value != current_value:
            obj.slug = unique_slug_for(obj, current_value)

        if commit:
            obj.save()
            self.save_m2m()
        return obj


class CategoryDashboardForm(AutoSlugDashboardForm):
    class Meta:
        model = Category
        fields = ["name", "description", "parent", "is_active"]
        labels = {
            "name": "Nazwa kategorii",
            "description": "Opis kategorii",
            "parent": "Kategoria nadrzędna",
            "is_active": "Widoczna w sklepie",
        }
        help_texts = {
            "name": "Krótka nazwa widoczna w filtrach katalogu.",
            "description": "Opis roboczy kategorii. Później możemy użyć go też jako tekst SEO.",
            "parent": "Opcjonalnie, jeśli kategoria ma być podkategorią innej kategorii.",
            "is_active": "Wyłącz, jeśli kategoria ma zostać w panelu, ale nie ma być pokazywana klientkom.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6, "placeholder": "Np. chokery, podwiązki, mitenki..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["parent"].empty_label = "Brak - kategoria główna"
        if self.instance and self.instance.pk:
            self.fields["parent"].queryset = Category.objects.exclude(pk=self.instance.pk)

    def clean_parent(self):
        parent = self.cleaned_data.get("parent")
        if parent and self.instance.pk and parent.pk == self.instance.pk:
            raise forms.ValidationError("Kategoria nie może być swoją własną kategorią nadrzędną.")
        return parent


class AestheticDashboardForm(AutoSlugDashboardForm):
    class Meta:
        model = Aesthetic
        fields = ["name", "description", "sort_order", "is_active"]
        labels = {
            "name": "Nazwa estetyki",
            "description": "Opis estetyki",
            "sort_order": "Kolejność wyświetlania",
            "is_active": "Widoczna w sklepie",
        }
        help_texts = {
            "name": "Nazwa stylu używana w filtrach i sekcjach sklepu.",
            "description": "Krótki opis klimatu, który później może trafić do kolekcji albo SEO.",
            "sort_order": "Niższa liczba oznacza wcześniejsze miejsce na listach.",
            "is_active": "Wyłącz, jeśli estetyka ma zostać w panelu, ale nie ma być używana w sklepie.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6, "placeholder": "Np. soft goth, dark coquette, grunge..."}),
            "sort_order": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()


class ColorDashboardForm(AutoSlugDashboardForm):
    class Meta:
        model = Color
        fields = ["name", "hex_code", "is_active"]
        labels = {
            "name": "Nazwa koloru",
            "hex_code": "Kod koloru HEX",
            "is_active": "Widoczny w sklepie",
        }
        help_texts = {
            "name": "Nazwa widoczna przy wariantach i w filtrach katalogu.",
            "hex_code": "Opcjonalny kod, np. #000000. Przyda się do swatchy kolorów.",
            "is_active": "Wyłącz, jeśli kolor ma zostać w panelu, ale nie ma być używany w sklepie.",
        }
        widgets = {
            "hex_code": forms.TextInput(attrs={"placeholder": "#000000", "maxlength": 7}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()

    def clean_hex_code(self):
        value = (self.cleaned_data.get("hex_code") or "").strip()
        if not value:
            return ""
        if not re.match(r"^#[0-9a-fA-F]{6}$", value):
            raise forms.ValidationError("Wpisz kolor w formacie HEX, np. #000000.")
        return value.lower()


class SizeDashboardForm(AutoSlugDashboardForm):
    class Meta:
        model = Size
        fields = ["name", "sort_order", "is_active"]
        labels = {
            "name": "Nazwa rozmiaru",
            "sort_order": "Kolejność wyświetlania",
            "is_active": "Widoczny w sklepie",
        }
        help_texts = {
            "name": "Nazwa używana przy wariantach i w filtrach katalogu.",
            "sort_order": "Niższa liczba oznacza wcześniejsze miejsce na listach.",
            "is_active": "Wyłącz, jeśli rozmiar ma zostać w panelu, ale nie ma być używany w sklepie.",
        }
        widgets = {
            "sort_order": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()


class BlogCategoryDashboardForm(AutoSlugDashboardForm):
    class Meta:
        model = BlogCategory
        fields = ["name", "description", "sort_order", "is_active"]
        labels = {
            "name": "Nazwa kategorii poradników",
            "description": "Opis kategorii",
            "sort_order": "Kolejność wyświetlania",
            "is_active": "Widoczna w sklepie",
        }
        help_texts = {
            "name": "Krótka nazwa widoczna przy poradnikach i w filtrach treści.",
            "description": "Opis roboczy kategorii. Przyda się później do SEO i stron poradnikowych.",
            "sort_order": "Niższa liczba oznacza wcześniejsze miejsce na listach.",
            "is_active": "Wyłącz, jeśli kategoria ma zostać w panelu, ale nie ma być pokazywana klientkom.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6, "placeholder": "Np. stylizacje, estetyki, poradniki produktowe..."}),
            "sort_order": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()


class ProductDashboardForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "category",
            "aesthetics",
            "description",
            "styling_tips",
            "regular_price",
            "sale_price",
            "is_featured",
            "seo_title",
            "seo_description",
            "status",
        ]
        labels = {
            "name": "Nazwa produktu",
            "category": "Kategoria",
            "aesthetics": "Estetyki",
            "description": "Opis",
            "styling_tips": "Porady dotyczące stylizacji",
            "regular_price": "Cena regularna",
            "sale_price": "Cena promocyjna",
            "is_featured": "Polecany produkt",
            "seo_title": "Tytuł SEO",
            "seo_description": "Opis SEO",
            "status": "Status produktu",
        }
        help_texts = {
            "description": "Główny opis widoczny na karcie produktu. Obsługuje proste formatowanie.",
            "styling_tips": "Krótka inspiracja: do czego pasuje produkt i jak go nosić.",
            "regular_price": "Podstawowa cena produktu.",
            "sale_price": "Cena po obniżce. Zostaw puste, jeśli produkt nie jest w promocji.",
            "seo_title": "Opcjonalny tytuł do wyszukiwarki.",
            "seo_description": "Opcjonalny opis do wyszukiwarki.",
        }
        widgets = {
            "aesthetics": forms.CheckboxSelectMultiple(attrs={"class": "dashboard-choice-list"}),
            "description": forms.Textarea(attrs={"rows": 8, "data-rich-text-input": "description"}),
            "styling_tips": forms.Textarea(attrs={"rows": 4}),
            "seo_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()

    def clean(self):
        cleaned_data = super().clean()
        regular_price = cleaned_data.get("regular_price")
        sale_price = cleaned_data.get("sale_price")
        if sale_price is not None and regular_price is not None and sale_price >= regular_price:
            self.add_error("sale_price", "Cena promocyjna musi być niższa niż cena regularna.")
        return cleaned_data

    def save(self, commit=True):
        product = super().save(commit=False)
        previous_name = None
        if product.pk:
            previous_name = Product.objects.filter(pk=product.pk).values_list("name", flat=True).first()

        if not product.slug or (previous_name and previous_name != product.name):
            product.slug = unique_slug_for(product, product.name)

        if commit:
            product.save()
            self.save_m2m()
        return product


class OutfitDashboardForm(AutoSlugDashboardForm):
    class Meta:
        model = Outfit
        fields = [
            "name",
            "short_description",
            "mood_description",
            "styling_tips",
            "aesthetics",
            "bundle_price",
            "status",
            "is_featured",
            "seo_title",
            "seo_description",
        ]
        labels = {
            "name": "Nazwa kreacji",
            "short_description": "Krótki opis",
            "mood_description": "Opis klimatu",
            "styling_tips": "Porady stylizacyjne",
            "aesthetics": "Estetyki",
            "bundle_price": "Cena promocyjna zestawu",
            "status": "Status kreacji",
            "is_featured": "Polecana kreacja",
            "seo_title": "Tytuł SEO",
            "seo_description": "Opis SEO",
        }
        help_texts = {
            "short_description": "Jedno krótkie zdanie widoczne na karcie kreacji.",
            "mood_description": "Główny opis nastroju i stylu zestawu.",
            "styling_tips": "Jak nosić tę kreację i z czym ją łączyć.",
            "bundle_price": "Cena promocyjna za cały zestaw. Zostaw puste, jeśli nie ma rabatu.",
            "seo_title": "Opcjonalny tytuł do wyszukiwarki.",
            "seo_description": "Opcjonalny opis do wyszukiwarki.",
        }
        widgets = {
            "aesthetics": forms.CheckboxSelectMultiple(attrs={"class": "dashboard-choice-list"}),
            "mood_description": forms.Textarea(attrs={"rows": 6}),
            "styling_tips": forms.Textarea(attrs={"rows": 4}),
            "seo_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["status"].choices = [
            (Outfit.STATUS_DRAFT, "Szkic"),
            (Outfit.STATUS_ACTIVE, "Aktywna"),
            (Outfit.STATUS_ARCHIVED, "Archiwalna"),
        ]


class OutfitItemInlineForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = OutfitItem
        fields = [
            "product",
            "variant",
            "quantity",
            "sort_order",
        ]
        labels = {
            "product": "Produkt",
            "variant": "Wariant",
            "quantity": "Ilość",
            "sort_order": "Kolejność",
        }
        help_texts = {
            "variant": "Opcjonalnie wybierz konkretny wariant produktu.",
            "quantity": "Liczba sztuk tego produktu w kreacji.",
        }
        widgets = {
            "sort_order": forms.HiddenInput(),
            "quantity": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["product"].queryset = Product.objects.order_by("name")
        self.fields["variant"].queryset = ProductVariant.objects.select_related("product", "color", "size").order_by(
            "product__name",
            "sort_order",
            "id",
        )
        self.fields["variant"].empty_label = "Dowolny / domyślny"


class OutfitImageInlineForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = OutfitImage
        fields = ["sort_order"]
        labels = {
            "sort_order": "Kolejność",
        }
        widgets = {
            "sort_order": forms.HiddenInput(),
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
        labels = {
            "color": "Kolor",
            "size": "Rozmiar",
            "sku": "Kod wariantu (SKU)",
            "price_override": "Cena wariantu",
            "stock_quantity": "Ilość",
            "is_active": "Aktywny",
            "sort_order": "Kolejność",
        }
        help_texts = {
            "sku": "Wewnętrzny kod magazynowy wariantu. Możesz zostawić puste, jeśli go nie używasz.",
            "price_override": "Zostaw puste, jeśli wariant ma używać ceny produktu.",
            "stock_quantity": "Liczba sztuk dostępnych dla tego wariantu.",
        }
        widgets = {
            "sku": forms.TextInput(attrs={"placeholder": "np. CHOKER-BLK-ONESIZE"}),
            "sort_order": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()


class ProductImageInlineForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = [
            "variant",
            "sort_order",
        ]
        labels = {
            "variant": "Wariant",
            "sort_order": "Kolejność",
        }
        widgets = {
            "sort_order": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["variant"].empty_label = "Wszystkie"
        if self.instance and self.instance.product_id:
            self.fields["variant"].queryset = self.instance.product.variants.all()


class ArticleDashboardForm(AutoSlugDashboardForm):
    slug_source_field = "title"

    class Meta:
        model = Article
        fields = [
            "title",
            "intro",
            "body",
            "category",
            "cover_image",
            "aesthetics",
            "products",
            "outfits",
            "status",
            "is_featured",
            "published_at",
            "seo_title",
            "seo_description",
        ]
        labels = {
            "title": "Tytuł poradnika",
            "intro": "Zajawka",
            "body": "Treść poradnika",
            "category": "Kategoria",
            "cover_image": "Okładka",
            "aesthetics": "Estetyki",
            "products": "Powiązane produkty",
            "outfits": "Powiązane kreacje",
            "status": "Status publikacji",
            "is_featured": "Wyróżniony poradnik",
            "published_at": "Data publikacji",
            "seo_title": "Tytuł SEO",
            "seo_description": "Opis SEO",
        }
        help_texts = {
            "title": "Najważniejszy nagłówek poradnika.",
            "intro": "Krótki opis pod tytułem. Najlepiej jedno albo dwa zdania.",
            "body": "Obsługuje proste formatowanie i wklejanie sformatowanego tekstu.",
            "cover_image": "Opcjonalna grafika widoczna na liście i karcie poradnika.",
            "products": "Produkty, które będą pokazane pod artykułem.",
            "outfits": "Gotowe kreacje powiązane z poradnikiem.",
            "published_at": "Możesz zostawić puste. Przy publikacji uzupełni się automatycznie.",
            "seo_title": "Opcjonalny tytuł do wyszukiwarki.",
            "seo_description": "Opcjonalny opis do wyszukiwarki.",
        }
        widgets = {
            "intro": forms.Textarea(attrs={"rows": 3}),
            "body": forms.Textarea(attrs={"rows": 16, "data-rich-text-input": "article-body"}),
            "aesthetics": forms.CheckboxSelectMultiple(attrs={"class": "dashboard-choice-list"}),
            "products": forms.SelectMultiple(attrs={"class": "dashboard-input dashboard-multiselect"}),
            "outfits": forms.SelectMultiple(attrs={"class": "dashboard-input dashboard-multiselect"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "seo_description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["status"].choices = [
            (Article.STATUS_DRAFT, "Szkic"),
            (Article.STATUS_PUBLISHED, "Opublikowany"),
            (Article.STATUS_ARCHIVED, "Archiwalny"),
        ]
        if self.instance and self.instance.published_at:
            self.initial["published_at"] = self.instance.published_at.strftime("%Y-%m-%dT%H:%M")


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantInlineForm,
    extra=0,
    can_delete=True,
)

ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageInlineForm,
    extra=0,
    can_delete=True,
)

OutfitItemFormSet = inlineformset_factory(
    Outfit,
    OutfitItem,
    form=OutfitItemInlineForm,
    extra=0,
    can_delete=True,
)

OutfitImageFormSet = inlineformset_factory(
    Outfit,
    OutfitImage,
    form=OutfitImageInlineForm,
    extra=0,
    can_delete=True,
)
