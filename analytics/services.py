from .models import AnalyticsEvent, AnalyticsSession


def get_device_type(user_agent):
    user_agent = user_agent.lower()
    if "mobile" in user_agent or "android" in user_agent or "iphone" in user_agent:
        return "mobile"
    if "ipad" in user_agent or "tablet" in user_agent:
        return "tablet"
    return "desktop"


def get_or_create_analytics_session(request):
    if not request.session.session_key:
        request.session.save()

    user_agent = request.META.get("HTTP_USER_AGENT", "")
    session, _ = AnalyticsSession.objects.get_or_create(
        session_key=request.session.session_key,
        defaults={
            "device_type": get_device_type(user_agent),
            "user_agent": user_agent,
            "referrer": request.META.get("HTTP_REFERER", "")[:200],
            "utm_source": request.GET.get("utm_source", "")[:120],
            "utm_medium": request.GET.get("utm_medium", "")[:120],
            "utm_campaign": request.GET.get("utm_campaign", "")[:120],
        },
    )
    return session


def track_event(request, event_type, product=None, variant=None, metadata=None):
    if request.path.startswith(("/static/", "/media/", "/admin/")):
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
