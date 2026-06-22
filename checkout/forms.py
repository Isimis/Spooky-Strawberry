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
    address_line_1 = forms.CharField(max_length=180, label="Ulica i numer")
    address_line_2 = forms.CharField(max_length=180, required=False, label="Dodatkowe informacje")
    postal_code = forms.CharField(max_length=20, label="Kod pocztowy")
    city = forms.CharField(max_length=100, label="Miasto")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "shipping_method":
                continue
            field.widget.attrs.setdefault("class", "input")
