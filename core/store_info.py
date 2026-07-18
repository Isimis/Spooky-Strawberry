"""Jedno źródło prawdziwych, publicznych informacji o sklepie."""

from decimal import Decimal


FREE_SHIPPING_THRESHOLD = Decimal("100.00")
MAX_DISPATCH_HOURS = 48

STORE_INFO = {
    "seller_name": "Wizards & Strawberries Patryk Lewandowski",
    "business_address": "ul. ppłk. pil. Romualda Sulińskiego 8B, 96-100 Skierniewice, Polska",
    "tax_id": "8361881374",
    "regon": "523748067",
    "contact_email": "kontakt@spookystrawberry.pl",
    "contact_phone": "668 639 593",
    "contact_phone_href": "+48668639593",
    "returns_address": "ul. Mazowiecka 20/68, 05-077 Warszawa, Polska",
    "returns_recipient": "Wizards & Strawberries Patryk Lewandowski",
    "free_shipping_threshold": FREE_SHIPPING_THRESHOLD,
    "free_shipping_threshold_display": "100 zł",
    "max_dispatch_hours": MAX_DISPATCH_HOURS,
}
