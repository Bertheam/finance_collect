from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import Agent, Notification, User
from accounts.services import create_notification
from ledger.models import MouvementFinancier

from .models import Collecte, Cycle, DemandeRetrait, Retenue, Retrait


MOUVEMENT_MISE = "MISE"
MOUVEMENT_RETENUE = "RETENUE"
MOUVEMENT_COM_AGENT = "COM_AGENT"
MOUVEMENT_COM_INSTITUTION = "COM_INSTITUTION"
MOUVEMENT_CREDIT_CLIENT = "CREDIT_CLIENT"
MOUVEMENT_RETRAIT = "RETRAIT"


def _generate_code(prefix):
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def _require_positive_integer(value, label):
    if value is None or int(value) <= 0:
        raise ValidationError(f"{label} doit être positif.")


def _require_multiple_of_100(value, label):
    if int(value) % 100 != 0:
        raise ValidationError(f"{label} doit être un multiple de 100 FCFA.")


def _sum_mouvements(*, type_mouvement, client=None, agent=None):
    filters = {"type_mouvement": type_mouvement}
    if client is not None:
        filters["client"] = client
    if agent is not None:
        filters["agent"] = agent

    return (
        MouvementFinancier.objects.filter(**filters).aggregate(total=Sum("montant"))["total"]
        or 0
    )


def _sync_agent_commission(agent):
    total = _sum_mouvements(type_mouvement=MOUVEMENT_COM_AGENT, agent=agent)
    Agent.objects.filter(pk=agent.pk).update(commission_totale=total)
    agent.commission_totale = total
    return total


def _create_mouvement(
    *,
    type_mouvement,
    montant,
    client=None,
    agent=None,
    cycle=None,
    source=None,
    destination=None,
):
    mouvement = MouvementFinancier(
        type_mouvement=type_mouvement,
        montant=int(montant),
        client=client,
        agent=agent,
        cycle=cycle,
        source=source or "INSTITUTION",
        destination=destination or "INSTITUTION",
    )
    mouvement.full_clean()
    mouvement.save()
    return mouvement


def get_montant_retirable(client):
    total_credit = _sum_mouvements(type_mouvement=MOUVEMENT_CREDIT_CLIENT, client=client)
    total_retraits = _sum_mouvements(type_mouvement=MOUVEMENT_RETRAIT, client=client)
    return int(total_credit - total_retraits)


def cycle_is_editable(cycle):
    return (
        cycle.deleted_at is None
        and cycle.statut == "EN_COURS"
        and not cycle.collectes.exists()
        and not cycle.demandes_retrait.exists()
        and not MouvementFinancier.objects.filter(cycle=cycle).exists()
    )


@transaction.atomic
def soft_delete_cycle(*, cycle, deleted_by):
    cycle = Cycle.objects.select_for_update().get(pk=cycle.pk)

    if cycle.deleted_at is not None:
        raise ValidationError("Ce cycle est déjà supprimé.")

    if cycle.statut != "CLOTURE":
        raise ValidationError("Suppression impossible : seul un cycle clôturé peut être supprimé.")

    cycle.deleted_at = timezone.now()
    cycle.deleted_by = deleted_by
    cycle.save(update_fields=["deleted_at", "deleted_by"])
    return cycle


@transaction.atomic
def create_cycle(*, client, mise):
    _require_positive_integer(mise, "La mise")
    _require_multiple_of_100(mise, "La mise")

    cycle = Cycle(
        client=client,
        agent=client.agent,
        mise=int(mise),
        nb_collectes=0,
        solde_actuel=0,
        statut="EN_COURS",
    )
    cycle.full_clean()
    cycle.save()
    return cycle


@transaction.atomic
def update_cycle(*, cycle, client, mise):
    _require_positive_integer(mise, "La mise")
    _require_multiple_of_100(mise, "La mise")

    cycle = (
        Cycle.objects.select_for_update()
        .select_related("client", "agent")
        .prefetch_related("collectes", "demandes_retrait")
        .get(pk=cycle.pk)
    )

    if not cycle_is_editable(cycle):
        raise ValidationError("Modification impossible : ce cycle a déjà commencé ou possède déjà des opérations liées.")

    cycle.client = client
    cycle.agent = client.agent
    cycle.mise = int(mise)
    cycle.full_clean()
    cycle.save(update_fields=["client", "agent", "mise"])
    return cycle


@transaction.atomic
def close_cycle(cycle):
    cycle = Cycle.objects.select_for_update().select_related("client", "agent").get(pk=cycle.pk)

    if cycle.statut != "EN_COURS":
        raise ValidationError("Le cycle est déjà clôturé.")

    if cycle.nb_collectes != 31:
        raise ValidationError("Le cycle ne peut être clôturé que lorsqu'il atteint 31 collectes.")

    if hasattr(cycle, "retenue"):
        raise ValidationError("La retenue de ce cycle existe déjà.")

    total_collecte = cycle.mise * cycle.nb_collectes
    retenue = cycle.mise
    commission_agent = retenue // 2
    commission_institution = retenue - commission_agent
    credit_client = total_collecte - retenue

    retenue_record = Retenue(
        code=_generate_code("RET"),
        cycle=cycle,
        montant=retenue,
        commission_agent=commission_agent,
        commission_institution=commission_institution,
    )
    retenue_record.full_clean()
    retenue_record.save()

    _create_mouvement(
        type_mouvement=MOUVEMENT_RETENUE,
        montant=retenue,
        client=cycle.client,
        agent=cycle.agent,
        cycle=cycle,
        source="CYCLE",
        destination="INSTITUTION",
    )
    _create_mouvement(
        type_mouvement=MOUVEMENT_COM_AGENT,
        montant=commission_agent,
        client=cycle.client,
        agent=cycle.agent,
        cycle=cycle,
        source="INSTITUTION",
        destination="AGENT",
    )
    _create_mouvement(
        type_mouvement=MOUVEMENT_COM_INSTITUTION,
        montant=commission_institution,
        client=cycle.client,
        agent=cycle.agent,
        cycle=cycle,
        source="INSTITUTION",
        destination="INSTITUTION",
    )
    _create_mouvement(
        type_mouvement=MOUVEMENT_CREDIT_CLIENT,
        montant=credit_client,
        client=cycle.client,
        agent=cycle.agent,
        cycle=cycle,
        source="CYCLE",
        destination="CLIENT",
    )

    cycle.solde_actuel = credit_client
    cycle.statut = "CLOTURE"
    cycle.type_cloture = "AUTOMATIQUE"
    cycle.date_cloture = timezone.now()
    cycle.full_clean()
    cycle.save(update_fields=["solde_actuel", "statut", "type_cloture", "date_cloture"])

    _sync_agent_commission(cycle.agent)
    return retenue_record


@transaction.atomic
def create_depot(*, cycle, nb_mises):
    _require_positive_integer(nb_mises, "Le nombre de mises")

    cycle = Cycle.objects.select_for_update().select_related("client", "agent").get(pk=cycle.pk)

    if cycle.statut != "EN_COURS":
        raise ValidationError("Le cycle doit être EN_COURS.")

    future_collectes = cycle.nb_collectes + int(nb_mises)
    if future_collectes > 31:
        raise ValidationError("Le total des collectes ne doit pas dépasser 31.")

    montant = cycle.mise * int(nb_mises)
    depot = Collecte(
        code=_generate_code("DEP"),
        cycle=cycle,
        nb_mises=int(nb_mises),
        montant=montant,
    )
    depot.full_clean()
    depot.save()

    _create_mouvement(
        type_mouvement=MOUVEMENT_MISE,
        montant=montant,
        client=cycle.client,
        agent=cycle.agent,
        cycle=cycle,
        source="CLIENT",
        destination="CYCLE",
    )

    cycle.nb_collectes = future_collectes
    cycle.solde_actuel += montant
    cycle.full_clean()
    cycle.save(update_fields=["nb_collectes", "solde_actuel"])

    if cycle.nb_collectes == 31:
        close_cycle(cycle)

    cycle.refresh_from_db()
    return depot


@transaction.atomic
def create_retrait(*, client, montant):
    _require_positive_integer(montant, "Le montant")

    montant = int(montant)
    montant_retirable = get_montant_retirable(client)
    if montant > montant_retirable:
        raise ValidationError("Le montant retirable calculé est insuffisant.")

    retrait = Retrait(code=_generate_code("RGT"), client=client, montant=montant)
    retrait.full_clean()
    retrait.save()

    _create_mouvement(
        type_mouvement=MOUVEMENT_RETRAIT,
        montant=montant,
        client=client,
        agent=client.agent,
        cycle=None,
        source="INSTITUTION",
        destination="CLIENT",
    )

    return retrait


@transaction.atomic
def create_demande_retrait(*, cycle, type_demande, created_by=None, montant_souhaite=None, motif=""):
    cycle = Cycle.objects.select_related("client", "agent").get(pk=cycle.pk)

    if type_demande == "ANTICIPE" and cycle.statut != "EN_COURS":
        raise ValidationError("Une demande de retrait anticipé nécessite un cycle en cours.")

    if type_demande == "NORMAL" and cycle.statut != "CLOTURE":
        raise ValidationError("Une demande de retrait normal nécessite un cycle clôturé.")

    if montant_souhaite in ("", None):
        montant_souhaite = None
    else:
        _require_positive_integer(montant_souhaite, "Le montant souhaité")
        montant_souhaite = int(montant_souhaite)

    if type_demande == "NORMAL" and montant_souhaite is not None:
        montant_retirable = get_montant_retirable(cycle.client)
        if montant_souhaite > montant_retirable:
            raise ValidationError("Le montant souhaité dépasse le montant retirable du client.")

    demande = DemandeRetrait(
        code=_generate_code("DMD"),
        cycle=cycle,
        client=cycle.client,
        created_by=created_by,
        type_demande=type_demande,
        montant_souhaite=montant_souhaite,
        motif=motif.strip(),
    )
    demande.full_clean()
    demande.save()

    initiateur = cycle.client.code_client
    if created_by is not None and getattr(created_by, "role", None) in {"ADMIN", "AGENT"}:
        initiateur = f"{created_by.get_full_name() or created_by.username} pour {cycle.client.code_client}"

    destinataires = []
    if cycle.agent.user_id:
        destinataires.append(cycle.agent.user)
    destinataires.extend(User.objects.filter(role="ADMIN", is_active=True))

    seen_user_ids = set()
    for destinataire in destinataires:
        if destinataire.pk in seen_user_ids:
            continue
        seen_user_ids.add(destinataire.pk)
        if created_by is not None and destinataire.pk == created_by.pk:
            continue
        create_notification(
            user=destinataire,
            title="Nouvelle demande de retrait",
            message=f"{initiateur} a enregistré la demande {demande.code}.",
            link="/demandes-retrait/",
        )

    return demande


def _notify_client_demande(demande, *, title, message):
    user = getattr(demande.client, "user", None)
    if user is None:
        return None
    return create_notification(
        user=user,
        title=title,
        message=message,
        link=f"/cycles/{demande.cycle_id}/",
    )


def _dismiss_staff_notifications_for_demande(demande):
    Notification.objects.filter(
        link="/demandes-retrait/",
        is_read=False,
        user__role__in={"ADMIN", "AGENT"},
        message__icontains=demande.code,
    ).update(is_read=True)


@transaction.atomic
def approve_demande_retrait(*, demande, processed_by, commentaire=""):
    demande = DemandeRetrait.objects.select_for_update().select_related("client", "cycle").get(pk=demande.pk)

    if demande.statut != "EN_ATTENTE":
        raise ValidationError("Seule une demande en attente peut être validée.")

    demande.statut = "VALIDEE"
    demande.processed_by = processed_by
    demande.processed_at = timezone.now()
    demande.commentaire_traitement = commentaire.strip()
    demande.full_clean()
    demande.save(update_fields=["statut", "processed_by", "processed_at", "commentaire_traitement"])
    _dismiss_staff_notifications_for_demande(demande)

    _notify_client_demande(
        demande,
        title="Demande de retrait validée",
        message=f"Votre demande {demande.code} a été validée.",
    )
    return demande


@transaction.atomic
def reject_demande_retrait(*, demande, processed_by, commentaire=""):
    demande = DemandeRetrait.objects.select_for_update().select_related("client", "cycle").get(pk=demande.pk)

    if demande.statut != "EN_ATTENTE":
        raise ValidationError("Seule une demande en attente peut être rejetée.")

    demande.statut = "REJETEE"
    demande.processed_by = processed_by
    demande.processed_at = timezone.now()
    demande.commentaire_traitement = commentaire.strip()
    demande.full_clean()
    demande.save(update_fields=["statut", "processed_by", "processed_at", "commentaire_traitement"])
    _dismiss_staff_notifications_for_demande(demande)

    _notify_client_demande(
        demande,
        title="Demande de retrait rejetée",
        message=f"Votre demande {demande.code} a été rejetée.",
    )
    return demande


@transaction.atomic
def execute_retrait_from_demande(*, demande, processed_by, montant=None):
    demande = DemandeRetrait.objects.select_for_update().select_related("client", "cycle").get(pk=demande.pk)

    if demande.statut != "VALIDEE":
        raise ValidationError("Le retrait ne peut être effectué qu'après validation de la demande.")

    if demande.retrait_id is not None:
        raise ValidationError("Le retrait lié à cette demande a déjà été effectué.")

    montant_effectif = montant if montant is not None else demande.montant_souhaite
    if montant_effectif in ("", None):
        montant_effectif = get_montant_retirable(demande.client)

    retrait = create_retrait(client=demande.client, montant=montant_effectif)
    demande.retrait = retrait
    if demande.processed_by_id is None:
        demande.processed_by = processed_by
    if demande.processed_at is None:
        demande.processed_at = timezone.now()
    demande.full_clean()
    demande.save(update_fields=["retrait", "processed_by", "processed_at"])
    _dismiss_staff_notifications_for_demande(demande)

    _notify_client_demande(
        demande,
        title="Retrait effectué",
        message=f"Le retrait lié à votre demande {demande.code} a été exécuté pour {retrait.montant} FCFA.",
    )
    return retrait
