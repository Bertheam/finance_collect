from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import Agent
from ledger.models import MouvementFinancier

from .models import Collecte, Cycle, Retenue, Retrait


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
        raise ValidationError(f"{label} doit etre positif.")


def _require_multiple_of_100(value, label):
    if int(value) % 100 != 0:
        raise ValidationError(f"{label} doit etre un multiple de 100 FCFA.")


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
def close_cycle(cycle):
    cycle = Cycle.objects.select_for_update().select_related("client", "agent").get(pk=cycle.pk)

    if cycle.statut != "EN_COURS":
        raise ValidationError("Le cycle est deja cloture.")

    if cycle.nb_collectes != 31:
        raise ValidationError("Le cycle ne peut etre cloture que lorsqu'il atteint 31 collectes.")

    if hasattr(cycle, "retenue"):
        raise ValidationError("La retenue de ce cycle existe deja.")

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
        raise ValidationError("Le cycle doit etre EN_COURS.")

    future_collectes = cycle.nb_collectes + int(nb_mises)
    if future_collectes > 31:
        raise ValidationError("Le total des collectes ne doit pas depasser 31.")

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
        raise ValidationError("Le montant retirable calcule est insuffisant.")

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
