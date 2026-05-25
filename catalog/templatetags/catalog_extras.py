from django import template

register = template.Library()


@register.filter
def money(value):
    if value is None:
        return ""
    return f"{value:.2f}".replace(".", ",") + " zł"
