import re
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from uuid import uuid4

from .models import Agent, Client, Notification, User


DEMANDE_NOTIFICATION_TITLE = "Nouvelle demande de retrait"
DEMANDE_NOTIFICATION_LINK = "/demandes-retrait/"
DEMANDE_CODE_PATTERN = re.compile(r"\bDMD-[A-Z0-9]+\b")


def _create_user_account(*, username, password, telephone, role, first_name="", last_name="", email=""):
    temp_user = User(
        username=username,
        telephone=telephone,
        role=role,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    validate_password(password, user=temp_user)

    return User.objects.create_user(
        username=username,
        password=password,
        telephone=telephone,
        role=role,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )


def _generate_client_code(pk):
    return f"CL-{pk:05d}"


def create_notification(*, user, title, message, link=""):
    notification = Notification(
        user=user,
        title=title.strip(),
        message=message.strip(),
        link=link.strip(),
    )
    notification.full_clean()
    notification.save()
    return notification


def _extract_demande_code_from_notification(notification):
    if notification.title != DEMANDE_NOTIFICATION_TITLE or notification.link != DEMANDE_NOTIFICATION_LINK:
        return None
    match = DEMANDE_CODE_PATTERN.search(notification.message or "")
    return match.group(0) if match else None


def get_visible_notifications(*, user, statut=""):
    from finance.models import DemandeRetrait

    notifications = list(Notification.objects.filter(user=user).order_by("-created_at"))
    pending_codes = set(DemandeRetrait.objects.filter(statut="EN_ATTENTE").values_list("code", flat=True))
    stale_notification_ids = []
    visible_notifications = []

    for notification in notifications:
        demande_code = _extract_demande_code_from_notification(notification)
        if demande_code is not None and demande_code not in pending_codes:
            if not notification.is_read:
                stale_notification_ids.append(notification.pk)
            continue

        if statut == "non_lues" and notification.is_read:
            continue
        if statut == "lues" and not notification.is_read:
            continue

        visible_notifications.append(notification)

    if stale_notification_ids:
        Notification.objects.filter(pk__in=stale_notification_ids).update(is_read=True)

    return visible_notifications


@transaction.atomic
def create_agent(
    *,
    matricule,
    nom,
    prenom,
    telephone,
    zone="",
    create_account=False,
    username="",
    password="",
    first_name="",
    last_name="",
    email="",
):
    agent = Agent(
        matricule=matricule,
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        zone=zone,
    )
    agent.full_clean()
    agent.save()

    if create_account:
        user = _create_user_account(
            username=username,
            password=password,
            telephone=telephone,
            role="AGENT",
            first_name=first_name or prenom,
            last_name=last_name or nom,
            email=email,
        )
        agent.user = user
        agent.save(update_fields=["user"])

    return agent


@transaction.atomic
def create_client(
    *,
    agent,
    code_client="",
    nom,
    prenom,
    telephone,
    email="",
    adresse="",
    create_account=False,
    username="",
    password="",
    first_name="",
    last_name="",
):
    raw_code_client = (code_client or "").strip()
    client = Client(
        agent=agent,
        code_client=raw_code_client or f"TMP-{uuid4().hex[:12].upper()}",
        nom=nom,
        prenom=prenom,
        telephone=telephone,
        email=email,
        adresse=adresse,
    )
    client.full_clean()
    client.save()

    if not raw_code_client:
        client.code_client = _generate_client_code(client.pk)
        client.full_clean()
        client.save(update_fields=["code_client"])

    if create_account:
        user = _create_user_account(
            username=username,
            password=password,
            telephone=telephone,
            role="CLIENT",
            first_name=first_name or prenom,
            last_name=last_name or nom,
            email=email,
        )
        client.user = user
        client.save(update_fields=["user"])

    return client


@transaction.atomic
def soft_delete_client(*, client, deleted_by):
    from finance.models import Cycle
    from finance.services import soft_delete_cycle

    client = Client.objects.select_for_update().get(pk=client.pk)

    if client.deleted_at is not None:
        raise ValidationError("Ce client est déjà supprimé.")

    active_cycles = Cycle.objects.filter(client=client, deleted_at__isnull=True)
    if active_cycles.filter(statut="EN_COURS").exists():
        raise ValidationError("Suppression impossible : ce client possède au moins un cycle en cours.")

    for cycle in active_cycles:
        soft_delete_cycle(cycle=cycle, deleted_by=deleted_by)

    client.deleted_at = timezone.now()
    client.deleted_by = deleted_by
    client.save(update_fields=["deleted_at", "deleted_by"])

    if client.user_id:
        client.user.is_active = False
        client.user.save(update_fields=["is_active"])

    return client


@transaction.atomic
def soft_delete_agent(*, agent, deleted_by):
    active_agent = Agent.objects.select_for_update().get(pk=agent.pk)

    if active_agent.deleted_at is not None:
        raise ValidationError("Cet agent est déjà supprimé.")

    clients = Client.objects.filter(agent=active_agent, deleted_at__isnull=True).order_by("pk")
    blocked_clients = clients.filter(cycles__deleted_at__isnull=True, cycles__statut="EN_COURS").distinct()
    if blocked_clients.exists():
        raise ValidationError("Suppression impossible : cet agent possède des clients avec au moins un cycle en cours.")

    for client in clients:
        soft_delete_client(client=client, deleted_by=deleted_by)

    active_agent.deleted_at = timezone.now()
    active_agent.deleted_by = deleted_by
    active_agent.save(update_fields=["deleted_at", "deleted_by"])

    if active_agent.user_id:
        active_agent.user.is_active = False
        active_agent.user.save(update_fields=["is_active"])

    return active_agent
