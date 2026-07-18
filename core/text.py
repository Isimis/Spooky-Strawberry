"""Niewielkie reguły wspólne dla tekstów widocznych klientkom."""


def normalize_dashes(value):
    """Sklep używa zwykłego łącznika, nigdy długiego myślnika."""
    if not isinstance(value, str):
        return value
    return value.replace("—", "-").replace("–", "-")
