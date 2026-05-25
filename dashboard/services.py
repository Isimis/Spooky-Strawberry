from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlparse

from django.db.models import Count, Sum
from django.utils import timezone

from analytics.models import AnalyticsEvent, AnalyticsSession
from catalog.models import Product
from orders.models import Order

from .models import DataQualityIssue


DAILY_CHART_DAYS = 14
HOURLY_CHART_HOURS = 24


PRODUCT_QUALITY_CHECKS = [
    {
        "type": "missing_image",
        "severity": DataQualityIssue.SEVERITY_HIGH,
        "message": "Produkt nie ma żadnego zdjęcia.",
        "test": lambda product: not product.images.exists(),
    },
    {
        "type": "missing_main_image",
        "severity": DataQualityIssue.SEVERITY_MEDIUM,
        "message": "Produkt nie ma ustawionego głównego zdjęcia.",
        "test": lambda product: product.images.exists() and not product.images.filter(is_main=True).exists(),
    },
    {
        "type": "missing_variant",
        "severity": DataQualityIssue.SEVERITY_HIGH,
        "message": "Produkt nie ma żadnego wariantu.",
        "test": lambda product: not product.variants.exists(),
    },
    {
        "type": "inactive_variants",
        "severity": DataQualityIssue.SEVERITY_MEDIUM,
        "message": "Produkt jest aktywny, ale nie ma aktywnego wariantu w magazynie.",
        "test": lambda product: product.status == Product.STATUS_ACTIVE and not product.is_available,
    },
    {
        "type": "missing_short_description",
        "severity": DataQualityIssue.SEVERITY_MEDIUM,
        "message": "Produkt nie ma krótkiego opisu.",
        "test": lambda product: not product.short_description.strip(),
    },
    {
        "type": "missing_mood_description",
        "severity": DataQualityIssue.SEVERITY_LOW,
        "message": "Produkt nie ma opisu klimatycznego.",
        "test": lambda product: not product.mood_description.strip(),
    },
    {
        "type": "missing_details",
        "severity": DataQualityIssue.SEVERITY_LOW,
        "message": "Produkt nie ma szczegółów produktu.",
        "test": lambda product: not product.details.strip(),
    },
    {
        "type": "missing_styling_tips",
        "severity": DataQualityIssue.SEVERITY_LOW,
        "message": "Produkt nie ma sekcji jak stylizować.",
        "test": lambda product: not product.styling_tips.strip(),
    },
    {
        "type": "missing_seo_title",
        "severity": DataQualityIssue.SEVERITY_LOW,
        "message": "Produkt nie ma SEO title.",
        "test": lambda product: not product.seo_title.strip(),
    },
    {
        "type": "missing_seo_description",
        "severity": DataQualityIssue.SEVERITY_LOW,
        "message": "Produkt nie ma SEO description.",
        "test": lambda product: not product.seo_description.strip(),
    },
    {
        "type": "missing_aesthetic",
        "severity": DataQualityIssue.SEVERITY_LOW,
        "message": "Produkt nie ma przypisanej estetyki.",
        "test": lambda product: not product.aesthetics.exists(),
    },
]


def get_dashboard_analytics():
    now = timezone.localtime()
    today_start = start_of_day(now.date())
    week_start = start_of_day(now.date() - timedelta(days=now.weekday()))
    month_start = start_of_day(now.date().replace(day=1))

    return {
        "updated_at": now,
        "summary_cards": [
            build_period_summary("Dziś", today_start, now),
            build_period_summary("Ten tydzień", week_start, now),
            build_period_summary("Ten miesiąc", month_start, now),
        ],
        "hourly_chart": build_hourly_chart(now),
        "daily_chart": build_daily_chart(now),
        "top_pages_periods": [
            {
                "title": "Top podstrony - dziś",
                "rows": get_top_pages_between(today_start, now, limit=7),
            },
            {
                "title": "Top podstrony - tydzień",
                "rows": get_top_pages_between(week_start, now, limit=7),
            },
            {
                "title": "Top podstrony - miesiąc",
                "rows": get_top_pages_between(month_start, now, limit=7),
            },
        ],
        "top_sources": get_top_sources_between(month_start, now),
        "device_breakdown": get_device_breakdown_between(month_start, now),
    }


def build_period_summary(label, start_at, end_at):
    events = period_events(start_at, end_at)
    page_views = events.filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW)
    product_views = events.filter(event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW).count()
    add_to_cart = events.filter(event_type=AnalyticsEvent.EVENT_ADD_TO_CART).count()
    sessions = period_sessions(start_at, end_at).count()
    unique_visitors = page_views.values("session_id").distinct().count()
    orders = active_orders().filter(created_at__gte=start_at, created_at__lte=end_at)
    revenue = orders.aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")
    top_page = get_top_page(page_views)

    return {
        "label": label,
        "unique_visitors": unique_visitors,
        "sessions": sessions,
        "page_views": page_views.count(),
        "product_views": product_views,
        "add_to_cart": add_to_cart,
        "orders": orders.count(),
        "revenue": format_money(revenue),
        "top_path": top_page["path"],
        "top_count": top_page["count"],
    }


def build_hourly_chart(now):
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    hours = [current_hour - timedelta(hours=offset) for offset in reversed(range(HOURLY_CHART_HOURS))]
    start_at = hours[0]
    page_events = list(
        AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
            created_at__gte=start_at,
            created_at__lte=now,
        ).values("created_at", "session_id")
    )
    pageviews_by_hour = Counter()
    unique_by_hour = defaultdict(set)

    for event in page_events:
        bucket = timezone.localtime(event["created_at"]).replace(minute=0, second=0, microsecond=0)
        pageviews_by_hour[bucket] += 1
        unique_by_hour[bucket].add(event["session_id"])

    rows = []
    max_value = 1
    for hour in hours:
        pageviews = pageviews_by_hour.get(hour, 0)
        unique = len(unique_by_hour.get(hour, set()))
        max_value = max(max_value, pageviews, unique)
        rows.append(
            {
                "hour": hour,
                "label": hour.strftime("%H:%M"),
                "pageviews": pageviews,
                "unique": unique,
            }
        )

    with_geometry = add_line_chart_geometry(rows, max_value, "pageviews", "unique")
    return {
        "rows": with_geometry["rows"],
        "pageviews_points": with_geometry["primary_points"],
        "unique_points": with_geometry["secondary_points"],
        "x_labels": build_x_labels(with_geometry["rows"], every=3),
        "y_ticks": build_y_ticks(max_value),
        "max_value": max_value,
    }


def build_daily_chart(now):
    today = now.date()
    dates = [today - timedelta(days=offset) for offset in reversed(range(DAILY_CHART_DAYS))]
    start_at = start_of_day(dates[0])
    page_events = list(
        AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
            created_at__gte=start_at,
            created_at__lte=now,
        ).values("created_at", "session_id")
    )
    orders = list(active_orders().filter(created_at__gte=start_at, created_at__lte=now).values("created_at"))
    pageviews_by_day = Counter()
    unique_by_day = defaultdict(set)
    orders_by_day = Counter()

    for event in page_events:
        day = timezone.localtime(event["created_at"]).date()
        pageviews_by_day[day] += 1
        unique_by_day[day].add(event["session_id"])
    for order in orders:
        orders_by_day[timezone.localtime(order["created_at"]).date()] += 1

    max_value = max(
        [1]
        + [pageviews_by_day.get(day, 0) for day in dates]
        + [len(unique_by_day.get(day, set())) for day in dates]
    )
    rows = []
    for day in dates:
        pageviews = pageviews_by_day.get(day, 0)
        unique = len(unique_by_day.get(day, set()))
        rows.append(
            {
                "date": day,
                "label": day.strftime("%d.%m"),
                "pageviews": pageviews,
                "unique": unique,
                "orders": orders_by_day.get(day, 0),
                "pageviews_percent": percentage(pageviews, max_value),
                "unique_percent": percentage(unique, max_value),
            }
        )

    return {
        "rows": rows,
        "max_value": max_value,
        "y_ticks": build_y_ticks(max_value),
    }


def add_line_chart_geometry(rows, max_value, primary_key, secondary_key):
    if len(rows) == 1:
        x_step = 100
    else:
        x_step = 100 / (len(rows) - 1)

    primary_points = []
    secondary_points = []
    rows_with_points = []
    for index, row in enumerate(rows):
        x = round(index * x_step, 2)
        primary_y = chart_y(row[primary_key], max_value)
        secondary_y = chart_y(row[secondary_key], max_value)
        primary_points.append(f"{x},{primary_y}")
        secondary_points.append(f"{x},{secondary_y}")
        rows_with_points.append(
            {
                **row,
                "x": x,
                "primary_y": primary_y,
                "secondary_y": secondary_y,
            }
        )

    return {
        "rows": rows_with_points,
        "primary_points": " ".join(primary_points),
        "secondary_points": " ".join(secondary_points),
    }


def chart_y(value, max_value):
    return round(100 - ((value / max_value) * 100), 2)


def build_x_labels(rows, every):
    labels = []
    for index, row in enumerate(rows):
        if index % every == 0 or index == len(rows) - 1:
            labels.append({"label": row["label"], "x": row["x"]})
    return labels


def build_y_ticks(max_value):
    tick_values = sorted({0, round(max_value / 2), max_value}, reverse=True)
    return [{"value": value, "y": chart_y(value, max_value)} for value in tick_values]


def get_top_page(page_view_queryset):
    row = page_view_queryset.values("path").annotate(count=Count("id")).order_by("-count", "path").first()
    if row:
        return {"path": row["path"], "count": row["count"]}
    return {"path": "-", "count": 0}


def get_top_pages_between(start_at, end_at, limit=7):
    rows = (
        period_events(start_at, end_at)
        .filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW)
        .values("path")
        .annotate(count=Count("id"))
        .order_by("-count", "path")[:limit]
    )
    return [{"path": row["path"], "count": row["count"]} for row in rows]


def get_top_sources_between(start_at, end_at):
    sessions = period_sessions(start_at, end_at)
    counter = Counter()
    for session in sessions.values("utm_source", "referrer"):
        source = normalize_source(session["utm_source"], session["referrer"])
        counter[source] += 1
    total = sum(counter.values()) or 1
    return [
        {
            "source": source,
            "count": count,
            "percent": percentage(count, total),
        }
        for source, count in counter.most_common(8)
    ]


def get_device_breakdown_between(start_at, end_at):
    rows = (
        period_sessions(start_at, end_at)
        .values("device_type")
        .annotate(count=Count("id"))
        .order_by("-count", "device_type")
    )
    total = sum(row["count"] for row in rows) or 1
    return [
        {
            "device": row["device_type"] or "Nieznane",
            "count": row["count"],
            "percent": percentage(row["count"], total),
        }
        for row in rows
    ]


def period_events(start_at, end_at):
    return AnalyticsEvent.objects.filter(created_at__gte=start_at, created_at__lte=end_at)


def period_sessions(start_at, end_at):
    return AnalyticsSession.objects.filter(first_seen_at__gte=start_at, first_seen_at__lte=end_at)


def active_orders():
    return Order.objects.exclude(status=Order.STATUS_DRAFT)


def start_of_day(day):
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_current_timezone())


def normalize_source(utm_source, referrer):
    if utm_source:
        return utm_source
    if referrer:
        domain = urlparse(referrer).netloc.replace("www.", "")
        if domain:
            return domain
    return "Bezpośrednio / brak danych"


def percentage(value, max_value):
    if value <= 0:
        return 0
    return max(4, round((value / max_value) * 100, 2))


def format_money(value):
    return f"{value:.2f}".replace(".", ",") + " zł"


def get_product_quality_issues(product):
    issues = []
    for check in PRODUCT_QUALITY_CHECKS:
        if check["test"](product):
            issues.append(
                {
                    "issue_type": check["type"],
                    "severity": check["severity"],
                    "message": check["message"],
                }
            )
    return issues


def refresh_product_quality_issues(product):
    current_issues = get_product_quality_issues(product)
    current_types = {issue["issue_type"] for issue in current_issues}
    now = timezone.now()

    for issue in current_issues:
        DataQualityIssue.objects.update_or_create(
            product=product,
            issue_type=issue["issue_type"],
            defaults={
                "message": issue["message"],
                "severity": issue["severity"],
                "status": DataQualityIssue.STATUS_OPEN,
                "resolved_at": None,
            },
        )

    stale_issues = DataQualityIssue.objects.filter(
        product=product,
        status=DataQualityIssue.STATUS_OPEN,
    ).exclude(issue_type__in=current_types)
    stale_issues.update(status=DataQualityIssue.STATUS_RESOLVED, resolved_at=now)
    return current_issues


def refresh_all_product_quality_issues():
    products = Product.objects.prefetch_related("images", "variants", "aesthetics")
    total_open = 0
    for product in products:
        total_open += len(refresh_product_quality_issues(product))
    return total_open
