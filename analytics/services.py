from uuid import uuid4

from .models import AnalyticsEvent, AnalyticsSession


VISITOR_COOKIE_NAME = "spooky_visitor_id"
VISITOR_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def get_device_type(user_agent):
    user_agent = user_agent.lower()
    if "mobile" in user_agent or "android" in user_agent or "iphone" in user_agent:
        return "mobile"
    if "ipad" in user_agent or "tablet" in user_agent:
        return "tablet"
    return "desktop"


def get_or_create_visitor_id(request):
    visitor_id = getattr(request, "_analytics_visitor_id", "") or request.COOKIES.get(VISITOR_COOKIE_NAME, "")
    if visitor_id:
        request._analytics_visitor_id = visitor_id
        return visitor_id

    visitor_id = uuid4().hex
    request._analytics_visitor_id = visitor_id
    request._analytics_set_visitor_cookie = True
    return visitor_id


def persist_visitor_cookie(request, response):
    visitor_id = getattr(request, "_analytics_visitor_id", "")
    should_set_cookie = getattr(request, "_analytics_set_visitor_cookie", False)
    if visitor_id and should_set_cookie:
        response.set_cookie(
            VISITOR_COOKIE_NAME,
            visitor_id,
            max_age=VISITOR_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure(),
        )


def get_or_create_analytics_session(request):
    if not request.session.session_key:
        request.session.save()

    visitor_id = get_or_create_visitor_id(request)
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    session, created = AnalyticsSession.objects.get_or_create(
        session_key=request.session.session_key,
        defaults={
            "visitor_id": visitor_id,
            "device_type": get_device_type(user_agent),
            "user_agent": user_agent,
            "referrer": request.META.get("HTTP_REFERER", "")[:200],
            "utm_source": request.GET.get("utm_source", "")[:120],
            "utm_medium": request.GET.get("utm_medium", "")[:120],
            "utm_campaign": request.GET.get("utm_campaign", "")[:120],
        },
    )
    if not created and visitor_id and session.visitor_id != visitor_id:
        session.visitor_id = visitor_id
        session.save(update_fields=["visitor_id"])
    return session


def track_event(request, event_type, product=None, variant=None, metadata=None):
    if request.path.startswith(("/static/", "/media/", "/admin/", "/django-admin/")):
        return None

    session = get_or_create_analytics_session(request)
    return AnalyticsEvent.objects.create(
        session=session,
        event_type=event_type,
        path=request.get_full_path()[:500],
        product=product,
        variant=variant,
        metadata=metadata or {},
    )
