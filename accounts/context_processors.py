from .services import get_visible_notifications


def unread_notifications(request):
    if not request.user.is_authenticated:
        return {
            "notification_preview": [],
            "unread_notifications_count": 0,
            "total_notifications_count": 0,
            "pending_demandes_count": 0,
        }

    visible_unread_notifications = get_visible_notifications(user=request.user, statut="non_lues")
    notifications = visible_unread_notifications[:15]
    unread_notifications_count = len(visible_unread_notifications)
    total_notifications_count = unread_notifications_count

    pending_demandes_count = 0
    if request.user.role in {"ADMIN", "AGENT"}:
        from finance.models import DemandeRetrait

        demandes = DemandeRetrait.objects.filter(statut="EN_ATTENTE")
        if request.user.role == "AGENT":
            agent = getattr(request.user, "agent_profile", None)
            demandes = demandes.filter(cycle__agent=agent) if agent is not None else demandes.none()
        pending_demandes_count = demandes.count()

    return {
        "notification_preview": notifications,
        "unread_notifications_count": unread_notifications_count,
        "total_notifications_count": total_notifications_count,
        "pending_demandes_count": pending_demandes_count,
    }
