"""Reguły naliczania kodów rabatowych używane przez koszyk i checkout."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .models import DiscountCode


MONEY_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class DiscountResult:
    discount_code: DiscountCode | None = None
    discount_total: Decimal = Decimal("0.00")
    error: str = ""

    @property
    def is_valid(self):
        return self.discount_code is not None and not self.error


def normalize_code(value):
    return (value or "").strip().upper()


def find_discount_code(value):
    code = normalize_code(value)
    if not code:
        return None
    return DiscountCode.objects.filter(code__iexact=code).first()


def evaluate_discount(value, *, subtotal, user=None, email=""):
    """Sprawdza kod i oblicza rabat od wartości produktów, nigdy od dostawy."""
    discount_code = value if isinstance(value, DiscountCode) else find_discount_code(value)
    subtotal = Decimal(subtotal or "0.00").quantize(MONEY_PLACES)

    if discount_code is None:
        return DiscountResult(error="Nie znaleźliśmy takiego kodu rabatowego.")
    if not discount_code.is_active:
        return DiscountResult(error="Ten kod rabatowy nie jest aktywny.")

    now = timezone.now()
    if discount_code.starts_at and discount_code.starts_at > now:
        return DiscountResult(error="Ten kod rabatowy nie jest jeszcze aktywny.")
    if discount_code.ends_at and discount_code.ends_at < now:
        return DiscountResult(error="Ten kod rabatowy wygasł.")
    if discount_code.max_uses is not None and discount_code.used_count >= discount_code.max_uses:
        return DiscountResult(error="Ten kod rabatowy osiągnął limit użyć.")
    if discount_code.minimum_order_amount is not None and subtotal < discount_code.minimum_order_amount:
        return DiscountResult(
            error=(
                "Ten kod działa od "
                f"{discount_code.minimum_order_amount.quantize(MONEY_PLACES):.2f}".replace(".", ",")
                + " zł wartości produktów."
            )
        )
    if discount_code.once_per_user and discount_code.already_used_by(user=user, email=email):
        return DiscountResult(error="Ten kod można wykorzystać tylko raz.")
    if discount_code.first_order_only and discount_code.customer_has_paid_order(user=user, email=email):
        return DiscountResult(error="Ten kod działa tylko przy pierwszym opłaconym zamówieniu.")

    if discount_code.discount_type == DiscountCode.TYPE_PERCENT:
        discount_total = (subtotal * discount_code.value / Decimal("100")).quantize(
            MONEY_PLACES, rounding=ROUND_HALF_UP
        )
    else:
        discount_total = Decimal(discount_code.value).quantize(MONEY_PLACES)

    discount_total = min(discount_total, subtotal)
    return DiscountResult(discount_code=discount_code, discount_total=discount_total)
