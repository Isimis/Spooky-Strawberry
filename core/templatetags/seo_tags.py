import json

from django import template
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter
def json_ld(value):
    """Bezpiecznie umieszcza JSON-LD w znaczniku script."""
    data = json.dumps(value, cls=DjangoJSONEncoder, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("<", "\\u003C").replace(">", "\\u003E").replace("&", "\\u0026")
    return mark_safe(data)
