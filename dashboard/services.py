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


HOURLY_CHART_HOURS = 24
DAILY_CHART_DAYS = 14
MONTHLY_CHART_DAYS = 30
CHART_WIDTH = 1000
CHART_HEIGHT = 320
CHART_PLOT_LEFT = 46
CHART_PLOT_RIGHT = 984
CHART_PLOT_TOP = 28
CHART_PLOT_BOTTOM = 258

IGNORED_USER_AGENT_PARTS = (
    "windowspowershell",
    "powershell",
    "python-requests",
    "curl/",
    "wget/",
    "httpie",
    "postmanruntime",
    "django test client",
)


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
        "type": "missing_description",
        "severity": DataQualityIssue.SEVERITY_LOW,
        "message": "Produkt nie ma opisu.",
        "test": lambda product: not product.description.strip(),
    },
    {
        "type": "missing_styling_tips",
        "severity": DataQualityIssue.SEVERITY_LOW,
        "message": "Produkt nie ma porad dotyczących stylizacji.",
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
    yesterday_start = today_start - timedelta(days=1)
    seven_days_start = today_start - timedelta(days=6)
    thirty_days_start = today_start - timedelta(days=29)

    last_30_events = period_events(thirty_days_start, now)
    last_30_sessions = period_sessions(thirty_days_start, now)
    last_30_orders = active_orders().filter(created_at__gte=thirty_days_start, created_at__lte=now)

    return {
        "updated_at": now,
        "summary_cards": [
            build_period_summary("Dzisiaj", today_start, now),
            build_period_summary("Wczoraj", yesterday_start, today_start),
            build_period_summary("Ostatnie 7 dni", seven_days_start, now),
            build_period_summary("Ostatnie 30 dni", thirty_days_start, now),
        ],
        "funnel": build_funnel(last_30_events, last_30_orders),
        "quality_metrics": build_quality_metrics(last_30_events, last_30_sessions, last_30_orders),
        "hourly_line": build_hourly_line_chart(now),
        "monthly_line": build_monthly_line_chart(now),
        "daily_activity": build_daily_activity(now),
        "top_pages": get_top_pages_between(thirty_days_start, now, limit=10),
        "top_sources": get_top_sources_between(thirty_days_start, now),
        "device_breakdown": get_device_breakdown_between(thirty_days_start, now),
        "data_note": build_data_note(last_30_events),
    }


def build_period_summary(label, start_at, end_at):
    events = period_events(start_at, end_at)
    page_views = events.filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW)
    product_views = events.filter(event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW).count()
    add_to_cart = events.filter(event_type=AnalyticsEvent.EVENT_ADD_TO_CART).count()
    sessions = page_views.values("session_id").distinct().count()
    unique_visitors = count_unique_visitors(page_views)
    orders = active_orders().filter(created_at__gte=start_at, created_at__lt=end_at)
    revenue = orders.aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")

    return {
        "label": label,
        "unique_visitors": unique_visitors,
        "sessions": sessions,
        "page_views": page_views.count(),
        "product_views": product_views,
        "add_to_cart": add_to_cart,
        "orders": orders.count(),
        "revenue": format_money(revenue),
        "pages_per_session": ratio(page_views.count(), sessions),
        "cart_rate": percent(add_to_cart, product_views),
    }


def count_unique_visitors(events):
    event_rows = list(events.values(
        "session_id",
        "session__session_key",
        "session__visitor_id",
        "session__user_agent",
    ))
    known_visitors = known_visitors_by_user_agent(event_rows)
    keys = set()
    for event in event_rows:
        key = visitor_key(event, known_visitors)
        if key:
            keys.add(key)
    return len(keys)


def known_visitors_by_user_agent(rows):
    known_visitors = {}
    for values in rows:
        user_agent = (values.get("session__user_agent") or values.get("user_agent") or "").strip()
        visitor_id = values.get("session__visitor_id") or values.get("visitor_id")
        if user_agent and visitor_id and not is_ignored_user_agent(user_agent):
            known_visitors.setdefault(user_agent, visitor_id)
    return known_visitors


def visitor_key(values, known_visitors=None):
    user_agent = (values.get("session__user_agent") or values.get("user_agent") or "").strip()
    if user_agent and is_ignored_user_agent(user_agent):
        return None

    visitor_id = values.get("session__visitor_id") or values.get("visitor_id")
    if visitor_id:
        return f"visitor:{visitor_id}"

    if not user_agent:
        return None

    if known_visitors and user_agent in known_visitors:
        return f"visitor:{known_visitors[user_agent]}"

    # Older local analytics rows were created before a stable visitor cookie existed.
    # For those rows, grouping by the browser signature is closer to a real user count
    # than treating every Django session as a separate person.
    if user_agent:
        return f"legacy-browser:{user_agent[:220]}"

    session_key = values.get("session__session_key") or values.get("session_key")
    if session_key:
        return f"session:{session_key}"

    return f"session-id:{values.get('session_id') or values.get('id') or 'unknown'}"


def is_ignored_user_agent(user_agent):
    normalized = user_agent.lower()
    return any(part in normalized for part in IGNORED_USER_AGENT_PARTS)


def build_funnel(events, orders):
    page_views = events.filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW).count()
    product_views = events.filter(event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW).count()
    add_to_cart = events.filter(event_type=AnalyticsEvent.EVENT_ADD_TO_CART).count()
    orders_count = orders.count()
    max_value = max(page_views, product_views, add_to_cart, orders_count, 1)

    steps = [
        ("Odsłony stron", page_views, page_views, "Cały ruch w sklepie"),
        ("Wejścia w produkty", product_views, page_views, "Czy katalog prowadzi do produktu"),
        ("Dodania do koszyka", add_to_cart, product_views, "Czy produkt budzi intencję zakupu"),
        ("Zamówienia", orders_count, add_to_cart, "Finalizacja, gdy checkout będzie aktywny"),
    ]
    return [
        {
            "label": label,
            "value": value,
            "detail": detail,
            "rate": percent(value, previous_value),
            "width": percentage(value, max_value),
        }
        for label, value, previous_value, detail in steps
    ]


def build_quality_metrics(events, sessions, orders):
    page_views = events.filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW).count()
    product_views = events.filter(event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW).count()
    add_to_cart = events.filter(event_type=AnalyticsEvent.EVENT_ADD_TO_CART).count()
    sessions_count = events.values("session_id").distinct().count()
    orders_count = orders.count()
    revenue = orders.aggregate(total=Sum("grand_total"))["total"] or Decimal("0.00")

    return [
        {
            "label": "Strony / sesję",
            "value": ratio(page_views, sessions_count),
            "detail": "Czy użytkowniczki przeglądają więcej niż jedną stronę",
        },
        {
            "label": "Produkt / odsłony",
            "value": percent(product_views, page_views),
            "detail": "Odsetek ruchu, który dociera do kart produktów",
        },
        {
            "label": "Koszyk / produkt",
            "value": percent(add_to_cart, product_views),
            "detail": "Intencja zakupu po obejrzeniu produktu",
        },
        {
            "label": "Średnie zamówienie",
            "value": format_money(revenue / orders_count) if orders_count else "0,00 zł",
            "detail": "Będzie realne po uruchomieniu sprzedaży",
        },
    ]


def build_hourly_line_chart(now):
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    hours = [current_hour - timedelta(hours=offset) for offset in reversed(range(HOURLY_CHART_HOURS))]
    start_at = hours[0]
    sessions_by_hour = defaultdict(set)
    users_by_hour = defaultdict(set)

    page_events = list(AnalyticsEvent.objects.filter(
        event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
        created_at__gte=start_at,
        created_at__lte=now,
    ).values("created_at", "session_id", "session__session_key", "session__visitor_id", "session__user_agent"))
    known_visitors = known_visitors_by_user_agent(page_events)

    for event in page_events:
        bucket = timezone.localtime(event["created_at"]).replace(minute=0, second=0, microsecond=0)
        sessions_by_hour[bucket].add(event["session_id"])
        key = visitor_key(event, known_visitors)
        if key:
            users_by_hour[bucket].add(key)

    rows = []
    max_value = 1
    for hour in hours:
        sessions = len(sessions_by_hour.get(hour, set()))
        users = len(users_by_hour.get(hour, set()))
        max_value = max(max_value, sessions, users)
        rows.append(
            {
                "label": hour.strftime("%H:%M"),
                "tooltip": f"{hour.strftime('%H:%M')}: {sessions} sesji, {users} użytkowników",
                "sessions": sessions,
                "users": users,
            }
        )

    total_sessions = len(set().union(*sessions_by_hour.values())) if sessions_by_hour else 0
    total_users = len(set().union(*users_by_hour.values())) if users_by_hour else 0
    return build_line_chart(rows, max_value, x_label_every=3, total_sessions=total_sessions, total_users=total_users)


def build_monthly_line_chart(now):
    today = now.date()
    dates = [today - timedelta(days=offset) for offset in reversed(range(MONTHLY_CHART_DAYS))]
    start_at = start_of_day(dates[0])
    sessions_by_day = defaultdict(set)
    users_by_day = defaultdict(set)

    page_events = list(AnalyticsEvent.objects.filter(
        event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
        created_at__gte=start_at,
        created_at__lte=now,
    ).values("created_at", "session_id", "session__session_key", "session__visitor_id", "session__user_agent"))
    known_visitors = known_visitors_by_user_agent(page_events)

    for event in page_events:
        bucket = timezone.localtime(event["created_at"]).date()
        sessions_by_day[bucket].add(event["session_id"])
        key = visitor_key(event, known_visitors)
        if key:
            users_by_day[bucket].add(key)

    rows = []
    max_value = 1
    for day in dates:
        sessions = len(sessions_by_day.get(day, set()))
        users = len(users_by_day.get(day, set()))
        max_value = max(max_value, sessions, users)
        rows.append(
            {
                "label": day.strftime("%d.%m"),
                "tooltip": f"{day.strftime('%d.%m')}: {sessions} sesji, {users} użytkowników",
                "sessions": sessions,
                "users": users,
            }
        )

    total_sessions = len(set().union(*sessions_by_day.values())) if sessions_by_day else 0
    total_users = len(set().union(*users_by_day.values())) if users_by_day else 0
    return build_line_chart(rows, max_value, x_label_every=5, total_sessions=total_sessions, total_users=total_users)


def build_line_chart(rows, max_value, x_label_every, total_sessions=None, total_users=None):
    chart_max = nice_axis_max(max_value)
    plot_width = CHART_PLOT_RIGHT - CHART_PLOT_LEFT
    plot_height = CHART_PLOT_BOTTOM - CHART_PLOT_TOP
    if len(rows) == 1:
        x_step = 0
    else:
        x_step = plot_width / (len(rows) - 1)

    chart_rows = []
    sessions_points = []
    users_points = []
    for index, row in enumerate(rows):
        x_value = CHART_PLOT_LEFT + (index * x_step)
        sessions_y = chart_y(row["sessions"], chart_max, plot_height)
        users_y = chart_y(row["users"], chart_max, plot_height)
        x = coordinate(x_value)
        sessions_y_text = coordinate(CHART_PLOT_TOP + sessions_y)
        users_y_text = coordinate(CHART_PLOT_TOP + users_y)
        hover_width = plot_width / max(len(rows), 1)
        hover_x = max(CHART_PLOT_LEFT, x_value - (hover_width / 2))
        chart_row = {
            **row,
            "x": x,
            "sessions_y": sessions_y_text,
            "users_y": users_y_text,
            "hover_x": coordinate(hover_x),
            "hover_width": coordinate(hover_width),
        }
        chart_rows.append(chart_row)
        sessions_points.append(f"{x},{sessions_y_text}")
        users_points.append(f"{x},{users_y_text}")

    return {
        "rows": chart_rows,
        "sessions_points": " ".join(sessions_points),
        "users_points": " ".join(users_points),
        "x_labels": build_x_labels(chart_rows, every=x_label_every),
        "y_ticks": build_y_ticks(chart_max, plot_height),
        "max_value": chart_max,
        "total_sessions": total_sessions if total_sessions is not None else sum(row["sessions"] for row in rows),
        "total_users": total_users if total_users is not None else sum(row["users"] for row in rows),
        "best": max(rows, key=lambda row: row["sessions"]),
        "width": CHART_WIDTH,
        "height": CHART_HEIGHT,
        "plot_left": CHART_PLOT_LEFT,
        "plot_right": CHART_PLOT_RIGHT,
        "plot_top": CHART_PLOT_TOP,
        "plot_bottom": CHART_PLOT_BOTTOM,
        "plot_width": plot_width,
        "plot_height": plot_height,
    }


def nice_axis_max(value):
    if value <= 1:
        return 1
    if value <= 10:
        return value
    if value <= 50:
        return ((value + 4) // 5) * 5
    if value <= 100:
        return ((value + 9) // 10) * 10
    return ((value + 24) // 25) * 25


def chart_y(value, max_value, plot_height):
    return plot_height - ((value / max_value) * plot_height)


def coordinate(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def build_x_labels(rows, every):
    labels = []
    for index, row in enumerate(rows):
        if index % every == 0 or index == len(rows) - 1:
            labels.append({"label": row["label"], "x": row["x"]})
    return labels


def build_y_ticks(max_value, plot_height):
    tick_values = sorted({0, round(max_value / 2), max_value}, reverse=True)
    return [
        {
            "value": value,
            "y": coordinate(CHART_PLOT_TOP + chart_y(value, max_value, plot_height)),
        }
        for value in tick_values
    ]


def build_hourly_activity(now):
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    hours = [current_hour - timedelta(hours=offset) for offset in reversed(range(HOURLY_CHART_HOURS))]
    start_at = hours[0]
    page_events = list(
        AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
            created_at__gte=start_at,
            created_at__lte=now,
        ).values("created_at", "session_id", "session__session_key", "session__visitor_id", "session__user_agent")
    )
    known_visitors = known_visitors_by_user_agent(page_events)
    pageviews_by_hour = Counter()
    unique_by_hour = defaultdict(set)

    for event in page_events:
        bucket = timezone.localtime(event["created_at"]).replace(minute=0, second=0, microsecond=0)
        pageviews_by_hour[bucket] += 1
        key = visitor_key(event, known_visitors)
        if key:
            unique_by_hour[bucket].add(key)

    max_value = max([1] + [pageviews_by_hour.get(hour, 0) for hour in hours])
    rows = []
    for hour in hours:
        pageviews = pageviews_by_hour.get(hour, 0)
        unique = len(unique_by_hour.get(hour, set()))
        rows.append(
            {
                "label": hour.strftime("%H:%M"),
                "pageviews": pageviews,
                "unique": unique,
                "height": percentage(pageviews, max_value),
                "is_empty": pageviews == 0,
            }
        )
    return {
        "rows": rows,
        "best": max(rows, key=lambda row: row["pageviews"]),
        "total_pageviews": sum(row["pageviews"] for row in rows),
        "total_unique": sum(row["unique"] for row in rows),
    }


def build_daily_activity(now):
    today = now.date()
    dates = [today - timedelta(days=offset) for offset in reversed(range(DAILY_CHART_DAYS))]
    start_at = start_of_day(dates[0])
    page_events = list(
        AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_PAGE_VIEW,
            created_at__gte=start_at,
            created_at__lte=now,
        ).values("created_at", "session_id", "session__session_key", "session__visitor_id", "session__user_agent")
    )
    known_visitors = known_visitors_by_user_agent(page_events)
    product_events = list(
        AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_PRODUCT_VIEW,
            created_at__gte=start_at,
            created_at__lte=now,
        ).values("created_at")
    )
    cart_events = list(
        AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EVENT_ADD_TO_CART,
            created_at__gte=start_at,
            created_at__lte=now,
        ).values("created_at")
    )
    orders = list(active_orders().filter(created_at__gte=start_at, created_at__lte=now).values("created_at"))

    pageviews_by_day = Counter()
    unique_by_day = defaultdict(set)
    product_by_day = Counter()
    cart_by_day = Counter()
    orders_by_day = Counter()

    for event in page_events:
        day = timezone.localtime(event["created_at"]).date()
        pageviews_by_day[day] += 1
        key = visitor_key(event, known_visitors)
        if key:
            unique_by_day[day].add(key)
    for event in product_events:
        product_by_day[timezone.localtime(event["created_at"]).date()] += 1
    for event in cart_events:
        cart_by_day[timezone.localtime(event["created_at"]).date()] += 1
    for order in orders:
        orders_by_day[timezone.localtime(order["created_at"]).date()] += 1

    max_value = max([1] + [pageviews_by_day.get(day, 0) for day in dates])
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
                "product_views": product_by_day.get(day, 0),
                "add_to_cart": cart_by_day.get(day, 0),
                "orders": orders_by_day.get(day, 0),
                "width": percentage(pageviews, max_value),
            }
        )
    return {
        "rows": rows,
        "best": max(rows, key=lambda row: row["pageviews"]),
    }


def get_top_pages_between(start_at, end_at, limit=10):
    page_counts = Counter()
    unique_by_path = defaultdict(set)
    page_events = list(
        period_events(start_at, end_at)
        .filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW)
        .values("path", "session_id", "session__session_key", "session__visitor_id", "session__user_agent")
    )
    known_visitors = known_visitors_by_user_agent(page_events)
    for event in page_events:
        page_counts[event["path"]] += 1
        key = visitor_key(event, known_visitors)
        if key:
            unique_by_path[event["path"]].add(key)

    paths = sorted(page_counts, key=lambda path: (-page_counts[path], path))[:limit]
    max_count = max([page_counts[path] for path in paths] + [1])
    return [
        {
            "path": path,
            "count": page_counts[path],
            "unique": len(unique_by_path[path]),
            "width": percentage(page_counts[path], max_count),
        }
        for path in paths
    ]


def get_top_sources_between(start_at, end_at):
    sessions = list(period_sessions(start_at, end_at).values("utm_source", "referrer", "session_key", "visitor_id", "user_agent"))
    known_visitors = known_visitors_by_user_agent(sessions)
    unique_by_source = defaultdict(set)
    for session in sessions:
        source = normalize_source(session["utm_source"], session["referrer"])
        key = visitor_key(session, known_visitors)
        if key:
            unique_by_source[source].add(key)
    total = sum(len(keys) for keys in unique_by_source.values()) or 1
    return [
        {
            "source": source,
            "count": len(keys),
            "percent": percentage(len(keys), total),
        }
        for source, keys in sorted(unique_by_source.items(), key=lambda item: (-len(item[1]), item[0]))[:8]
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
            "device": translate_device_type(row["device_type"]),
            "count": row["count"],
            "percent": percentage(row["count"], total),
        }
        for row in rows
    ]


def build_data_note(events):
    active_days = (
        events.filter(event_type=AnalyticsEvent.EVENT_PAGE_VIEW)
        .dates("created_at", "day")
        .count()
    )
    if active_days < 3:
        return "Dane są jeszcze bardzo świeże. Trendy czasowe traktuj roboczo, dopóki ruch nie zbierze się przez kilka dni."
    return ""


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


def translate_device_type(value):
    labels = {
        "desktop": "Komputer",
        "mobile": "Telefon",
        "tablet": "Tablet",
        "bot": "Bot",
    }
    return labels.get((value or "").lower(), "Nieznane")


def ratio(numerator, denominator):
    if not denominator:
        return "0,00"
    return f"{numerator / denominator:.2f}".replace(".", ",")


def percent(numerator, denominator):
    if not denominator:
        return "0%"
    return f"{round((numerator / denominator) * 100, 1):g}%".replace(".", ",")


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
