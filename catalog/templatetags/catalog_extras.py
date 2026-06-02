import html
import re
from urllib.parse import urlparse

from django import template
from django.utils.safestring import mark_safe


register = template.Library()


@register.filter
def money(value):
    if value is None:
        return ""
    return f"{value:.2f}".replace(".", ",") + " zł"


@register.filter
def formatted_text(value):
    if not value:
        return ""

    raw_lines = [line.rstrip() for line in str(value).splitlines()]
    blocks = []
    list_items = []
    list_tag = None

    def flush_list():
        nonlocal list_tag
        if not list_items:
            return
        tag = list_tag or "ul"
        blocks.append(f"<{tag}>" + "".join(f"<li>{format_inline(item)}</li>" for item in list_items) + f"</{tag}>")
        list_items.clear()
        list_tag = None

    for line in raw_lines:
        stripped_raw = line.strip()
        stripped = html.escape(stripped_raw)
        if not stripped:
            flush_list()
            continue
        if stripped.startswith(("- ", "* ")):
            if list_tag != "ul":
                flush_list()
                list_tag = "ul"
            list_items.append(stripped[2:].strip())
            continue
        ordered_item = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ordered_item:
            if list_tag != "ol":
                flush_list()
                list_tag = "ol"
            list_items.append(ordered_item.group(1).strip())
            continue
        flush_list()
        if stripped == "---":
            blocks.append("<hr>")
        elif stripped_raw.startswith("> "):
            blocks.append(f"<blockquote>{format_inline(html.escape(stripped_raw[2:].strip()))}</blockquote>")
        elif stripped.startswith("### "):
            blocks.append(f"<h3>{format_inline(stripped[4:].strip())}</h3>")
        elif stripped.startswith("## "):
            blocks.append(f"<h2>{format_inline(stripped[3:].strip())}</h2>")
        elif stripped.startswith("# "):
            blocks.append(f"<h2>{format_inline(stripped[2:].strip())}</h2>")
        else:
            blocks.append(f"<p>{format_inline(stripped)}</p>")

    flush_list()
    return mark_safe("".join(blocks))


def format_inline(value):
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"\*(.+?)\*", r"<em>\1</em>", value)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, value)


def replace_link(match):
    label = match.group(1)
    url = html.unescape(match.group(2)).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return label
    safe_url = html.escape(url, quote=True)
    return f'<a href="{safe_url}" rel="noopener noreferrer" target="_blank">{label}</a>'
