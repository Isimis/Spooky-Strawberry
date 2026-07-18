from django import forms

from orders.models import ShippingMethod


class CheckoutForm(forms.Form):
    first_name = forms.CharField(max_length=80, label="Imię")
    last_name = forms.CharField(max_length=80, label="Nazwisko")
    email = forms.EmailField(label="E-mail")
    phone = forms.CharField(max_length=40, required=False, label="Telefon")
    shipping_method = forms.ModelChoiceField(
        queryset=ShippingMethod.objects.filter(is_active=True).order_by("sort_order", "price"),
        label="Sposób dostawy",
        empty_label=None,
    )
    # Adres - wymagany tylko przy dostawie kurierem (patrz clean()).
    address_line_1 = forms.CharField(max_length=180, required=False, label="Ulica i numer")
    address_line_2 = forms.CharField(max_length=180, required=False, label="Dodatkowe informacje")
    postal_code = forms.CharField(max_length=20, required=False, label="Kod pocztowy")
    city = forms.CharField(max_length=100, required=False, label="Miasto")

    # Punkt odbioru (Paczkomat) - wypełniane z mapy Geowidget (ukryte pola).
    pickup_point_code = forms.CharField(max_length=40, required=False, widget=forms.HiddenInput())
    pickup_point_name = forms.CharField(max_length=180, required=False, widget=forms.HiddenInput())
    pickup_point_address = forms.CharField(max_length=255, required=False, widget=forms.HiddenInput())

    # Zapis adresu jako domyślnego w koncie (tylko dla zalogowanych, dostawa kurierem).
    save_address = forms.BooleanField(required=False, label="Zapisz adres dla przyszłych zamówień")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "shipping_method" or isinstance(
                field.widget, (forms.HiddenInput, forms.CheckboxInput)
            ):
                continue
            field.widget.attrs.setdefault("class", "input")

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("shipping_method")
        if not method:
            return cleaned

        if method.is_pickup_point:
            # Dostawa do punktu - wymagany wybrany paczkomat, adres nieistotny.
            if not cleaned.get("pickup_point_code"):
                raise forms.ValidationError("Wybierz paczkomat na mapie, żeby kontynuować.")
            cleaned["address_line_1"] = ""
            cleaned["address_line_2"] = ""
            cleaned["postal_code"] = ""
            cleaned["city"] = ""
        else:
            # Dostawa kurierem - wymagany adres, punkt nieistotny.
            missing = [
                self.fields[name].label
                for name in ("address_line_1", "postal_code", "city")
                if not cleaned.get(name)
            ]
            if missing:
                raise forms.ValidationError("Podaj adres dostawy: " + ", ".join(missing).lower() + ".")
            cleaned["pickup_point_code"] = ""
            cleaned["pickup_point_name"] = ""
            cleaned["pickup_point_address"] = ""

        return cleaned
