from core.models import Message


def unread_messages(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {"dashboard_unread_messages_count": 0}

    unread_count = Message.objects.filter(
        direction=Message.DIRECTION_INBOUND,
        read_at__isnull=True,
    ).count()
    return {"dashboard_unread_messages_count": unread_count}
