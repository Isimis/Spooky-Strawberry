import re
from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory
from django.forms import modelform_factory
from django.utils.text import slugify

from blog.models import Article, BlogCategory
from catalog.models import Aesthetic, Category, Color, Product, ProductImage, ProductVariant, Size, unique_slug_for
from core.models import NewsletterSubscriber, SiteSettings
from inventory.models import StockEntry
from orders.models import DiscountCode, Order, OrderItem, ShippingMethod
from outfits.models import Outfit, OutfitHotspot, OutfitImage, OutfitItem


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
    if model is NewsletterSubscriber:
        return NewsletterSubscriberDashboardForm
    if model is Order:
        return OrderDashboardForm
    if model is ShippingMethod:
        return ShippingMethodDashboardForm
    if model is DiscountCode:
        return DiscountCodeDashboardForm

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
        fields = ["name", "tagline", "description", "image", "featured_image", "card_gradient", "is_featured", "sort_order", "is_active"]
        labels = {
            "name": "Nazwa estetyki",
            "tagline": "Podtytuł kafelka",
            "description": "Opis estetyki",
            "image": "Zdjęcie estetyki",
            "featured_image": "Zdjęcie wyróżnionego kafelka",
            "card_gradient": "Gradient tła (fallback)",
            "is_featured": "Wyróżniona (większy kafelek)",
            "sort_order": "Kolejność wyświetlania",
            "is_active": "Widoczna w sklepie",
        }
        help_texts = {
            "name": "Nazwa stylu używana w filtrach i sekcjach sklepu.",
            "tagline": "Krótkie hasło na kafelku, np. „Mrok, ale delikatny”.",
            "description": "Krótki opis klimatu, który później może trafić do kolekcji albo SEO.",
            "image": "Zdjęcie tła kafelka i hero estetyki. Jeśli puste, użyty zostanie gradient.",
            "featured_image": "Używane tylko, gdy estetyka jest wyróżniona (duży kafelek w mozaice). Jeśli puste, użyte zostanie zwykłe zdjęcie.",
            "card_gradient": "Dwa kolory rozdzielone przecinkiem, np. „#2a1622,#7a3d5a”.",
            "is_featured": "Wyróżnione estetyki dostają większy kafelek w mozaice.",
            "sort_order": "Niższa liczba oznacza wcześniejsze miejsce na listach.",
            "is_active": "Wyłącz, jeśli estetyka ma zostać w panelu, ale nie ma być używana w sklepie.",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6, "placeholder": "Np. soft goth, dark coquette, grunge..."}),
            "card_gradient": forms.TextInput(attrs={"placeholder": "#2a1622,#7a3d5a"}),
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


class NewsletterSubscriberDashboardForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ["email", "source", "is_active", "consent_text", "unsubscribed_at"]
        labels = {
            "email": "Adres e-mail",
            "source": "Źródło zapisu",
            "is_active": "Aktywna subskrypcja",
            "consent_text": "Treść zgody",
            "unsubscribed_at": "Data wypisu",
        }
        help_texts = {
            "email": "Adres używany przy wysyłce newslettera.",
            "source": "Miejsce, z którego osoba zapisała się do newslettera.",
            "is_active": "Wyłącz, jeśli adres nie powinien trafiać do wysyłki.",
            "consent_text": "Tekst zgody zapisany przy subskrypcji.",
            "unsubscribed_at": "Opcjonalnie uzupełnij, jeśli osoba wypisała się ręcznie.",
        }
        widgets = {
            "consent_text": forms.Textarea(attrs={"rows": 5}),
            "unsubscribed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["source"].choices = [
            (NewsletterSubscriber.SOURCE_FOOTER, "Stopka"),
            (NewsletterSubscriber.SOURCE_HOME, "Strona główna"),
            (NewsletterSubscriber.SOURCE_POPUP, "Popup"),
            (NewsletterSubscriber.SOURCE_OTHER, "Inne"),
        ]
        if self.instance and self.instance.unsubscribed_at:
            self.initial["unsubscribed_at"] = self.instance.unsubscribed_at.strftime("%Y-%m-%dT%H:%M")


class OrderDashboardForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            "order_number",
            "status",
            "placed_at",
            "email",
            "phone",
            "first_name",
            "last_name",
            "shipping_address_line_1",
            "shipping_address_line_2",
            "shipping_postal_code",
            "shipping_city",
            "shipping_country",
            "shipping_method",
            "pickup_point_code",
            "pickup_point_name",
            "pickup_point_address",
            "discount_code",
            "subtotal",
            "discount_total",
            "shipping_total",
            "grand_total",
            "customer_note",
            "admin_note",
            "source_session_key",
        ]
        labels = {
            "order_number": "Numer zamówienia",
            "status": "Status zamówienia",
            "placed_at": "Data złożenia",
            "email": "E-mail klientki",
            "phone": "Telefon",
            "first_name": "Imię",
            "last_name": "Nazwisko",
            "shipping_address_line_1": "Adres dostawy",
            "shipping_address_line_2": "Adres dostawy cd.",
            "shipping_postal_code": "Kod pocztowy",
            "shipping_city": "Miasto",
            "shipping_country": "Kraj",
            "shipping_method": "Metoda dostawy",
            "pickup_point_code": "Paczkomat — kod",
            "pickup_point_name": "Paczkomat — nazwa",
            "pickup_point_address": "Paczkomat — adres",
            "discount_code": "Kod rabatowy",
            "subtotal": "Wartość produktów",
            "discount_total": "Rabat",
            "shipping_total": "Koszt dostawy",
            "grand_total": "Razem",
            "customer_note": "Notatka klientki",
            "admin_note": "Komentarz administratora (wewnętrzny)",
            "source_session_key": "Sesja źródłowa",
        }
        help_texts = {
            "order_number": "Możesz zostawić puste przy roboczym zamówieniu.",
            "status": "Status realizacji po stronie sklepu. Płatności zostają poza zakresem do czasu działalności.",
            "placed_at": "Data złożenia zamówienia. Przy szkicu może zostać pusta.",
            "shipping_address_line_2": "Opcjonalnie mieszkanie, paczkomat albo dopisek adresowy.",
            "discount_code": "Kod użyty w zamówieniu, jeśli był przypisany.",
            "customer_note": "Wiadomość od klientki albo notatka robocza dla obsługi.",
            "admin_note": "Widoczny tylko w panelu (w szczegółach i na liście). Klient go nie widzi.",
            "pickup_point_address": "Wypełnione automatycznie, gdy klient wybierze paczkomat na mapie.",
            "source_session_key": "Techniczne powiązanie z sesją analityczną. Przyda się później do ścieżek zakupowych.",
        }
        widgets = {
            "placed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "customer_note": forms.Textarea(attrs={"rows": 5}),
            "admin_note": forms.Textarea(attrs={"rows": 4, "placeholder": "Notatka dla obsługi, np. ustalenia, wysyłka, uwagi…"}),
            "source_session_key": forms.TextInput(attrs={"placeholder": "np. session_key z analityki"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["status"].choices = [
            (Order.STATUS_DRAFT, "Szkic"),
            (Order.STATUS_PLACED, "Złożone"),
            (Order.STATUS_CONFIRMED, "Potwierdzone"),
            (Order.STATUS_PACKED, "Spakowane"),
            (Order.STATUS_SHIPPED, "Wysłane"),
            (Order.STATUS_CANCELLED, "Anulowane"),
        ]
        self.fields["shipping_method"].queryset = ShippingMethod.objects.order_by("sort_order", "name")
        self.fields["shipping_method"].empty_label = "Brak / do ustalenia"
        self.fields["discount_code"].queryset = DiscountCode.objects.order_by("code")
        self.fields["discount_code"].empty_label = "Brak kodu"
        if self.instance and self.instance.placed_at:
            self.initial["placed_at"] = self.instance.placed_at.strftime("%Y-%m-%dT%H:%M")


def unique_shipping_code(instance, value):
    base_code = slugify(value) or "dostawa"
    code = base_code
    counter = 2
    queryset = ShippingMethod.objects.filter(code=code)
    if instance.pk:
        queryset = queryset.exclude(pk=instance.pk)

    while queryset.exists():
        code = f"{base_code}-{counter}"
        queryset = ShippingMethod.objects.filter(code=code)
        if instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
        counter += 1

    return code


class ShippingMethodDashboardForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = ShippingMethod
        fields = [
            "name",
            "code",
            "description",
            "price",
            "free_from_amount",
            "sort_order",
            "is_active",
            "is_pickup_point",
        ]
        labels = {
            "name": "Nazwa metody dostawy",
            "code": "Kod techniczny",
            "description": "Opis dla klientki",
            "price": "Cena dostawy",
            "free_from_amount": "Darmowa od kwoty",
            "sort_order": "Kolejność",
            "is_active": "Aktywna w sklepie",
            "is_pickup_point": "Dostawa do paczkomatu (wybór punktu na mapie)",
        }
        help_texts = {
            "name": "Nazwa widoczna w koszyku i później przy zamówieniu.",
            "code": "Roboczy identyfikator metody. Możesz zostawić puste, utworzy się z nazwy.",
            "description": "Krótki tekst pomocniczy, np. czas dostawy albo miejsce odbioru.",
            "price": "Koszt tej dostawy przed ewentualnym progiem darmowej wysyłki.",
            "free_from_amount": "Zostaw puste, jeśli ta metoda nie ma własnego progu darmowej dostawy.",
            "sort_order": "Niższa liczba oznacza wyższą pozycję na liście.",
            "is_active": "Wyłącz, jeśli metoda ma zostać w panelu, ale nie ma być dostępna w sklepie.",
        }
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "np. inpost-paczkomat"}),
            "description": forms.Textarea(attrs={"rows": 5, "placeholder": "Np. Dostawa do paczkomatu zwykle w 1-3 dni robocze."}),
            "price": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "free_from_amount": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "sort_order": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["code"].required = False
        if not self.instance.pk:
            self.fields["price"].initial = Decimal("0.00")

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip()
        return slugify(code) if code else ""

    def save(self, commit=True):
        shipping_method = super().save(commit=False)
        if not shipping_method.code:
            shipping_method.code = unique_shipping_code(shipping_method, shipping_method.name)

        if commit:
            shipping_method.save()
            self.save_m2m()
        return shipping_method


class DiscountCodeDashboardForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = DiscountCode
        fields = [
            "code",
            "discount_type",
            "value",
            "minimum_order_amount",
            "max_uses",
            "used_count",
            "starts_at",
            "ends_at",
            "is_active",
        ]
        labels = {
            "code": "Kod rabatowy",
            "discount_type": "Typ rabatu",
            "value": "Wartość rabatu",
            "minimum_order_amount": "Minimalna wartość zamówienia",
            "max_uses": "Limit użyć",
            "used_count": "Użycia dotychczas",
            "starts_at": "Aktywny od",
            "ends_at": "Aktywny do",
            "is_active": "Włączony",
        }
        help_texts = {
            "code": "Kod wpisywany przez klientkę. Zapisuje się wielkimi literami.",
            "discount_type": "Procent obniża koszyk procentowo, kwota odejmuje stałą wartość.",
            "value": "Dla procentu wpisz np. 10, dla kwoty np. 15.00.",
            "minimum_order_amount": "Zostaw puste, jeśli kod działa od każdej kwoty koszyka.",
            "max_uses": "Opcjonalny limit całkowitej liczby użyć kodu.",
            "used_count": "Licznik historyczny. Zwykle będzie zwiększany automatycznie po zamówieniu.",
            "starts_at": "Opcjonalna data startu promocji.",
            "ends_at": "Opcjonalna data zakończenia promocji.",
            "is_active": "Wyłącz, aby kod nie działał mimo ustawionych dat.",
        }
        widgets = {
            "code": forms.TextInput(attrs={"placeholder": "np. SPOOKY10"}),
            "value": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "minimum_order_amount": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "max_uses": forms.NumberInput(attrs={"min": 0}),
            "used_count": forms.NumberInput(attrs={"min": 0}),
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["discount_type"].choices = [
            (DiscountCode.TYPE_PERCENT, "Procent"),
            (DiscountCode.TYPE_FIXED, "Kwota"),
        ]
        if self.instance and self.instance.starts_at:
            self.initial["starts_at"] = self.instance.starts_at.strftime("%Y-%m-%dT%H:%M")
        if self.instance and self.instance.ends_at:
            self.initial["ends_at"] = self.instance.ends_at.strftime("%Y-%m-%dT%H:%M")

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()

    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get("discount_type")
        value = cleaned_data.get("value")
        starts_at = cleaned_data.get("starts_at")
        ends_at = cleaned_data.get("ends_at")
        max_uses = cleaned_data.get("max_uses")
        used_count = cleaned_data.get("used_count") or 0

        if discount_type == DiscountCode.TYPE_PERCENT and value is not None and value > Decimal("100.00"):
            self.add_error("value", "Rabat procentowy nie może być większy niż 100%.")
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error("ends_at", "Data zakończenia musi być późniejsza niż data startu.")
        if max_uses is not None and used_count > max_uses:
            self.add_error("used_count", "Liczba użyć nie może być większa niż limit.")

        return cleaned_data


class OrderItemInlineForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = [
            "product",
            "variant",
            "product_name",
            "variant_name",
            "sku",
            "quantity",
            "unit_price",
            "line_total",
        ]
        labels = {
            "product": "Produkt z katalogu",
            "variant": "Wariant z katalogu",
            "product_name": "Nazwa w zamówieniu",
            "variant_name": "Wariant w zamówieniu",
            "sku": "Kod wariantu",
            "quantity": "Ilość",
            "unit_price": "Cena za sztukę",
            "line_total": "Razem za pozycję",
        }
        help_texts = {
            "product": "Powiązanie z aktualnym produktem w katalogu.",
            "variant": "Opcjonalnie konkretny wariant. Dane historyczne obok nie zmienią się same po zmianach w katalogu.",
            "product_name": "Snapshot nazwy z momentu zamówienia. To zostaje nawet po zmianie produktu w katalogu.",
            "variant_name": "Snapshot wariantu z momentu zamówienia.",
            "sku": "Snapshot kodu wariantu z momentu zamówienia.",
            "line_total": "Wylicza się z ilości i ceny za sztukę przy zapisie.",
        }
        widgets = {
            "sku": forms.HiddenInput(),
            "quantity": forms.NumberInput(attrs={"min": 1, "data-order-item-quantity": "true"}),
            "unit_price": forms.NumberInput(attrs={"min": 0, "step": "0.01", "data-order-item-unit-price": "true"}),
            "line_total": forms.NumberInput(attrs={"min": 0, "step": "0.01", "readonly": "readonly", "data-order-item-line-total": "true"}),
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
        self.fields["variant"].empty_label = "Brak / domyślny"
        self.fields["product_name"].required = False
        self.fields["variant_name"].required = False
        self.fields["sku"].required = False
        self.fields["unit_price"].required = False
        self.fields["line_total"].required = False

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data

        product = cleaned_data.get("product")
        variant = cleaned_data.get("variant")
        quantity = cleaned_data.get("quantity") or 1
        unit_price = cleaned_data.get("unit_price")

        if product and variant and variant.product_id != product.id:
            self.add_error("variant", "Wybierz wariant przypisany do tego produktu.")
            return cleaned_data
        if product and not cleaned_data.get("product_name"):
            cleaned_data["product_name"] = product.name
        if variant:
            if not cleaned_data.get("variant_name"):
                parts = []
                if variant.color:
                    parts.append(variant.color.name)
                if variant.size:
                    parts.append(variant.size.name)
                cleaned_data["variant_name"] = " / ".join(parts) or "Domyślny"
            if not cleaned_data.get("sku"):
                cleaned_data["sku"] = variant.sku or ""
            if unit_price is None:
                cleaned_data["unit_price"] = variant.price
                unit_price = variant.price
        elif product and unit_price is None:
            cleaned_data["unit_price"] = product.current_price
            unit_price = product.current_price

        if unit_price is not None:
            cleaned_data["line_total"] = unit_price * quantity

        return cleaned_data


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
            "is_new",
            "is_bestseller",
            "disable_low_stock_badge",
            "low_stock_threshold",
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
            "is_new": "Oznacz jako nowość",
            "is_bestseller": "Oznacz jako bestseller",
            "disable_low_stock_badge": "Nie pokazuj „ostatnie sztuki”",
            "low_stock_threshold": "Próg „ostatnich sztuk” (szt.)",
            "seo_title": "Tytuł SEO",
            "seo_description": "Opis SEO",
            "status": "Status produktu",
        }
        help_texts = {
            "description": "Główny opis widoczny na karcie produktu. Obsługuje proste formatowanie.",
            "styling_tips": "Krótka inspiracja: do czego pasuje produkt i jak go nosić.",
            "regular_price": "Podstawowa cena produktu.",
            "sale_price": "Cena po obniżce. Zostaw puste, jeśli produkt nie jest w promocji.",
            "is_featured": "Wyróżnia produkt na stronie głównej i w sekcjach „polecane”.",
            "is_new": "Pokazuje etykietę „Nowość” na karcie produktu.",
            "is_bestseller": "Pokazuje etykietę „Bestseller” na karcie produktu.",
            "disable_low_stock_badge": "Wyłącza automatyczne „ostatnie sztuki” dla tego produktu, nawet gdy stan jest niski.",
            "low_stock_threshold": "Od jakiego stanu pokazywać „ostatnie sztuki” dla tego produktu. Wartość początkowa pochodzi z Ustawień strony.",
            "seo_title": "Opcjonalny tytuł do wyszukiwarki.",
            "seo_description": "Opcjonalny opis do wyszukiwarki.",
        }
        widgets = {
            "aesthetics": forms.CheckboxSelectMultiple(attrs={"class": "dashboard-choice-list"}),
            "description": forms.Textarea(attrs={"rows": 8, "data-rich-text-input": "description"}),
            "styling_tips": forms.Textarea(attrs={"rows": 4}),
            "seo_description": forms.Textarea(attrs={"rows": 3}),
            "low_stock_threshold": forms.NumberInput(attrs={"min": 0}),
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
            "name": "Nazwa stylizacji",
            "short_description": "Krótki opis",
            "mood_description": "Opis klimatu",
            "styling_tips": "Porady stylizacyjne",
            "aesthetics": "Estetyki",
            "bundle_price": "Cena promocyjna zestawu",
            "status": "Status stylizacji",
            "is_featured": "Polecana stylizacja",
            "seo_title": "Tytuł SEO",
            "seo_description": "Opis SEO",
        }
        help_texts = {
            "short_description": "Jedno krótkie zdanie widoczne na karcie stylizacji.",
            "mood_description": "Główny opis nastroju i stylu zestawu.",
            "styling_tips": "Jak nosić tę stylizację i z czym ją łączyć.",
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
            "quantity": "Liczba sztuk tego produktu w stylizacji.",
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


class OutfitHotspotInlineForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = OutfitHotspot
        fields = ["product", "pos_x", "pos_y", "sort_order"]
        labels = {
            "product": "Produkt",
            "pos_x": "Pozycja X (%)",
            "pos_y": "Pozycja Y (%)",
            "sort_order": "Kolejność",
        }
        widgets = {
            "pos_x": forms.HiddenInput(),
            "pos_y": forms.HiddenInput(),
            "sort_order": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["product"].queryset = Product.objects.order_by("name")


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
        # Magazyn jest źródłem prawdy: dla istniejących wariantów stan zmienia się
        # tylko przez ruchy magazynowe, więc pole jest tu tylko do odczytu.
        if self.instance and self.instance.pk:
            field = self.fields["stock_quantity"]
            field.disabled = True
            field.help_text = "Stan zmieniasz w Magazynie (przyjęcia/wydania)."
            field.widget.attrs["readonly"] = True


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
            "outfits": "Powiązane stylizacje",
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
            "outfits": "Gotowe stylizacje powiązane z poradnikiem.",
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

OutfitHotspotFormSet = inlineformset_factory(
    Outfit,
    OutfitHotspot,
    form=OutfitHotspotInlineForm,
    extra=0,
    can_delete=True,
)

OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemInlineForm,
    extra=0,
    can_delete=True,
)


class SiteSettingsDashboardForm(DashboardFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "announcement_is_active",
            "announcement_text",
            "low_stock_default_enabled",
            "low_stock_threshold",
            "payments_sandbox",
            "drop_is_active",
            "drop_eyebrow",
            "drop_heading",
            "drop_date",
            "drop_products",
        ]
        labels = {
            "announcement_is_active": "Pokaż pasek zapowiedzi",
            "announcement_text": "Tekst paska zapowiedzi",
            "low_stock_default_enabled": "Domyślnie pokazuj „ostatnie sztuki” dla nowych produktów",
            "low_stock_threshold": "Domyślny próg „ostatnich sztuk” (szt.)",
            "payments_sandbox": "Tryb testowy płatności (Sandbox)",
            "drop_is_active": "Pokaż datę dropu na stronie głównej",
            "drop_eyebrow": "Nadtytuł dropu (nad hasłem hero)",
            "drop_heading": "Nagłówek sekcji „Najnowszy drop”",
            "drop_date": "Data i godzina dropu",
            "drop_products": "Produkty w dropie",
        }
        help_texts = {
            "announcement_text": "Tekst na czarnym pasku nad nagłówkiem. Możesz użyć emoji.",
            "low_stock_default_enabled": "Wartość domyślna dla NOWO dodawanych produktów: czy mają od razu mieć włączoną etykietę „ostatnie sztuki”. Nie zmienia produktów już dodanych — każdy produkt ma własne ustawienie.",
            "low_stock_threshold": "Domyślny próg dla NOWO dodawanych produktów. Każdy produkt ma własny próg, który możesz później zmienić w jego ustawieniach.",
            "payments_sandbox": "WŁĄCZONE = Sandbox: płatności testowe (P24 sandbox), a zakupy NIE zmieniają stanów magazynowych. WYŁĄCZONE = Prawdziwe płatności: dopóki nie są uruchomione, w koszyku i checkoutcie pokazujemy dymek „wersja testowa — wkrótce startujemy”, a zamówienia nie są finalizowane.",
            "drop_eyebrow": "Tekst widoczny nad hasłem na stronie głównej, np. „Najnowszy drop”.",
            "drop_date": "Wyświetlana na hero, np. „piątek 20:00”. Zostaw puste, by nie pokazywać godziny.",
            "drop_products": "Produkty pokazywane w sekcji „Najnowszy drop”. Jeśli nic nie wybierzesz, pokażemy najnowsze produkty.",
        }
        widgets = {
            "announcement_text": forms.TextInput(),
            "low_stock_threshold": forms.NumberInput(attrs={"min": 1}),
            "drop_date": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "drop_products": forms.CheckboxSelectMultiple(attrs={"class": "dashboard-choice-list"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["drop_date"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]
        self.fields["drop_products"].queryset = Product.objects.filter(
            status=Product.STATUS_ACTIVE
        ).order_by("sort_order", "name")
        self.fields["payments_sandbox"].help_text = (
            "WŁĄCZONE = Sandbox (testy): płatności na kluczach testowych P24, zakupy NIE "
            "zmieniają stanów magazynowych, a w koszyku/checkoutcie widnieje „wersja testowa”. "
            "WYŁĄCZONE = Prawdziwe płatności: klucze produkcyjne P24, realne transakcje i "
            "aktualizacja magazynu, bez informacji testowej. Zmieniaj świadomie."
        )
        self.apply_dashboard_widgets()


from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class UserAccountForm(DashboardFormMixin, forms.ModelForm):
    accepts_marketing = forms.BooleanField(required=False, label="Zgoda marketingowa / newsletter")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active", "is_staff"]
        labels = {
            "first_name": "Imię",
            "last_name": "Nazwisko",
            "email": "E-mail",
            "is_active": "Konto aktywne",
            "is_staff": "Dostęp do panelu (zespół)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(self.instance, "customer_profile", None)
        if profile is not None:
            self.fields["accepts_marketing"].initial = profile.accepts_marketing
        self.apply_dashboard_widgets()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ten e-mail jest już używany przez inne konto.")
        return email

    def save(self, commit=True):
        user = super().save(commit=commit)
        from accounts.models import CustomerProfile

        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.accepts_marketing = self.cleaned_data.get("accepts_marketing", False)
        profile.save(update_fields=["accepts_marketing"])
        return user


class UserAccountCreateForm(DashboardFormMixin, forms.ModelForm):
    password = forms.CharField(min_length=8, widget=forms.PasswordInput, label="Hasło")
    accepts_marketing = forms.BooleanField(required=False, label="Zgoda marketingowa / newsletter")

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_staff"]
        labels = {
            "first_name": "Imię",
            "last_name": "Nazwisko",
            "email": "E-mail",
            "is_staff": "Dostęp do panelu (zespół)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Podaj adres e-mail.")
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("Konto z tym adresem e-mail już istnieje.")
        return email

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self, commit=True):
        email = self.cleaned_data["email"]
        user = User(
            username=email,
            email=email,
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
            is_staff=self.cleaned_data.get("is_staff", False),
        )
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
            from accounts.models import CustomerProfile

            profile, _ = CustomerProfile.objects.get_or_create(user=user)
            profile.accepts_marketing = self.cleaned_data.get("accepts_marketing", False)
            profile.save(update_fields=["accepts_marketing"])
        return user


class StockEntryForm(DashboardFormMixin, forms.ModelForm):
    """Formularz przyjęcia magazynowego (zakup / reklamacja / korekta)."""

    class Meta:
        model = StockEntry
        fields = [
            "source",
            "quantity",
            "occurred_at",
            "unit_price_net",
            "vat_rate",
            "unit_price_gross",
            "customs_amount",
            "supplier_url",
            "invoice",
            "note",
        ]
        labels = {
            "source": "Źródło",
            "quantity": "Ilość sztuk",
            "occurred_at": "Data",
            "unit_price_net": "Cena netto (szt.)",
            "vat_rate": "VAT (%)",
            "unit_price_gross": "Cena brutto (szt.)",
            "customs_amount": "Cło",
            "supplier_url": "Link do produktu u dostawcy",
            "invoice": "Faktura (załącznik)",
            "note": "Notatka",
        }
        widgets = {
            "occurred_at": forms.DateInput(attrs={"type": "date"}),
            "supplier_url": forms.URLInput(attrs={"placeholder": "https://..."}),
        }

    # Źródła dostępne przy ręcznym przyjęciu (sprzedaż podpinamy automatycznie osobno).
    ALLOWED_SOURCES = [
        StockEntry.SOURCE_PURCHASE,
        StockEntry.SOURCE_COMPLAINT,
        StockEntry.SOURCE_ADJUSTMENT,
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_dashboard_widgets()
        self.fields["source"].choices = [
            (value, label)
            for value, label in StockEntry.SOURCE_CHOICES
            if value in self.ALLOWED_SOURCES
        ]
        self.fields["source"].initial = StockEntry.SOURCE_PURCHASE
        if not self.is_bound and not self.initial.get("occurred_at"):
            from django.utils import timezone

            self.fields["occurred_at"].initial = timezone.localdate()
        for name in ("unit_price_net", "vat_rate", "unit_price_gross", "customs_amount", "supplier_url", "note"):
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        net = cleaned.get("unit_price_net")
        vat = cleaned.get("vat_rate")
        gross = cleaned.get("unit_price_gross")

        # Uzupełnij brakujące pole z trójki netto / VAT / brutto (spójnie z JS).
        if net is not None and vat is not None and gross is None:
            cleaned["unit_price_gross"] = (net * (Decimal(1) + vat / Decimal(100))).quantize(Decimal("0.01"))
        elif net is not None and gross is not None and vat is None and net != 0:
            cleaned["vat_rate"] = ((gross / net - Decimal(1)) * Decimal(100)).quantize(Decimal("0.01"))
        elif vat is not None and gross is not None and net is None:
            cleaned["unit_price_net"] = (gross / (Decimal(1) + vat / Decimal(100))).quantize(Decimal("0.01"))

        return cleaned


