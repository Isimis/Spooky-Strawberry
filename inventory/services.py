from django.db.models import Case, IntegerField, Sum, Value, When

from .models import StockEntry


def ensure_opening_balance(variant):
    """Gwarantuje kompletność ledgera: jeśli wariant ma stan, ale zero ruchów magazynowych
    (np. utworzony importem lub bezpośrednio), dopisuje bilans otwarcia równy bieżącemu stanowi.

    Dzięki temu ``recalculate_variant_stock`` nie wyzeruje stanu przy pierwszym wydaniu.
    """
    if variant.stock_quantity and not variant.stock_entries.exists():
        StockEntry.objects.create(
            variant=variant,
            direction=StockEntry.DIRECTION_IN,
            source=StockEntry.SOURCE_OPENING,
            quantity=variant.stock_quantity,
            note="Bilans otwarcia (auto)",
        )


def recalculate_variant_stock(variant):
    """Ustawia stan wariantu na sumę ruchów magazynowych (źródło prawdy).

    Przyjęcia (IN) dodają, wydania (OUT) odejmują. Wynik nigdy nie schodzi poniżej zera.
    """
    total = variant.stock_entries.aggregate(
        total=Sum(
            Case(
                When(direction=StockEntry.DIRECTION_IN, then="quantity"),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        - Sum(
            Case(
                When(direction=StockEntry.DIRECTION_OUT, then="quantity"),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )["total"]

    variant.stock_quantity = max(total or 0, 0)
    variant.save(update_fields=["stock_quantity"])
    return variant.stock_quantity
