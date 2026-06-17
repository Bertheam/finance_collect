from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Agent, Client, Notification, User
from ledger.models import MouvementFinancier

from .models import Cycle, DemandeRetrait, Retenue, Retrait
from .services import (
    approve_demande_retrait,
    cycle_is_editable,
    create_cycle,
    create_demande_retrait,
    create_depot,
    create_retrait,
    execute_retrait_from_demande,
    get_montant_retirable,
    reject_demande_retrait,
    soft_delete_cycle,
    update_cycle,
)


class FinanceServiceTests(TestCase):
    def setUp(self):
        self.agent_user = User.objects.create_user(
            username="agent-finance",
            password="secret123",
            telephone="700199999",
            role="AGENT",
        )
        self.client_user = User.objects.create_user(
            username="client-finance",
            password="secret123",
            telephone="700299999",
            role="CLIENT",
        )
        self.agent = Agent.objects.create(
            user=self.agent_user,
            matricule="AG001",
            nom="IAM",
            prenom="Agent",
            telephone="700200000",
            zone="Bamako",
        )
        self.client = Client.objects.create(
            user=self.client_user,
            agent=self.agent,
            code_client="CL001",
            nom="Traore",
            prenom="Aminata",
            telephone="700300000",
            email="aminata@example.com",
        )

    def test_create_cycle_with_valid_mise_is_accepted(self):
        cycle = create_cycle(client=self.client, mise=1000)

        self.assertEqual(cycle.mise, 1000)
        self.assertEqual(cycle.nb_collectes, 0)
        self.assertEqual(cycle.statut, "EN_COURS")
        self.assertEqual(cycle.agent, self.agent)

    def test_create_cycle_with_non_multiple_of_100_is_refused(self):
        with self.assertRaises(ValidationError):
            create_cycle(client=self.client, mise=1050)

    def test_cycle_can_be_updated_before_any_deposit_or_operation(self):
        cycle = create_cycle(client=self.client, mise=1000)

        updated_cycle = update_cycle(cycle=cycle, client=self.client, mise=2000)

        self.assertEqual(updated_cycle.mise, 2000)
        self.assertTrue(cycle_is_editable(updated_cycle))

    def test_depot_of_five_mises_increments_collectes_and_creates_mise(self):
        cycle = create_cycle(client=self.client, mise=1000)

        depot = create_depot(cycle=cycle, nb_mises=5)
        cycle.refresh_from_db()
        mouvement = MouvementFinancier.objects.get(cycle=cycle, type_mouvement="MISE")

        self.assertEqual(depot.nb_mises, 5)
        self.assertEqual(depot.montant, 5000)
        self.assertEqual(cycle.nb_collectes, 5)
        self.assertEqual(cycle.solde_actuel, 5000)
        self.assertEqual(mouvement.montant, 5000)

    def test_depot_exceeding_31_collectes_is_refused(self):
        cycle = create_cycle(client=self.client, mise=1000)
        create_depot(cycle=cycle, nb_mises=30)

        with self.assertRaises(ValidationError):
            create_depot(cycle=cycle, nb_mises=2)

    def test_cycle_update_is_refused_after_first_deposit(self):
        cycle = create_cycle(client=self.client, mise=1000)
        create_depot(cycle=cycle, nb_mises=1)

        with self.assertRaises(ValidationError):
            update_cycle(cycle=cycle, client=self.client, mise=2000)

    def test_exactly_31_collectes_closes_cycle_automatically(self):
        cycle = create_cycle(client=self.client, mise=1000)

        create_depot(cycle=cycle, nb_mises=31)
        cycle.refresh_from_db()
        retenue = Retenue.objects.get(cycle=cycle)
        mouvements = list(
            MouvementFinancier.objects.filter(cycle=cycle).order_by("type_mouvement", "montant")
        )

        self.assertEqual(cycle.nb_collectes, 31)
        self.assertEqual(cycle.statut, "CLOTURE")
        self.assertEqual(cycle.type_cloture, "AUTOMATIQUE")
        self.assertEqual(retenue.montant, 1000)
        self.assertEqual(retenue.commission_agent, 500)
        self.assertEqual(retenue.commission_institution, 500)
        self.assertEqual(cycle.solde_actuel, 30000)
        self.assertEqual(get_montant_retirable(self.client), 30000)
        self.assertEqual(self.agent.commission_totale, 0)

        self.agent.refresh_from_db()
        self.assertEqual(self.agent.commission_totale, 500)
        self.assertEqual(
            [(m.type_mouvement, m.montant) for m in mouvements],
            [
                ("COM_AGENT", 500),
                ("COM_INSTITUTION", 500),
                ("CREDIT_CLIENT", 30000),
                ("MISE", 31000),
                ("RETENUE", 1000),
            ],
        )

    def test_closed_cycle_refuses_new_depot(self):
        cycle = create_cycle(client=self.client, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)

        with self.assertRaises(ValidationError):
            create_depot(cycle=cycle, nb_mises=1)

    def test_retrait_larger_than_withdrawable_is_refused(self):
        cycle = create_cycle(client=self.client, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)

        with self.assertRaises(ValidationError):
            create_retrait(client=self.client, montant=30001)

    def test_retrait_available_amount_is_accepted_and_decreases_withdrawable(self):
        cycle = create_cycle(client=self.client, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)

        retrait = create_retrait(client=self.client, montant=5000)
        mouvement = MouvementFinancier.objects.get(type_mouvement="RETRAIT", client=self.client)

        self.assertEqual(retrait.montant, 5000)
        self.assertEqual(Retrait.objects.count(), 1)
        self.assertEqual(mouvement.montant, 5000)
        self.assertEqual(get_montant_retirable(self.client), 25000)

    def test_anticipatory_withdrawal_request_is_accepted_on_open_cycle(self):
        cycle = create_cycle(client=self.client, mise=1000)

        demande = create_demande_retrait(
            cycle=cycle,
            type_demande="ANTICIPE",
            montant_souhaite=2000,
            motif="Urgence",
        )

        self.assertEqual(demande.type_demande, "ANTICIPE")
        self.assertEqual(demande.statut, "EN_ATTENTE")
        self.assertEqual(demande.montant_souhaite, 2000)
        self.assertEqual(DemandeRetrait.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.agent_user, is_read=False).count(), 1)

    def test_normal_withdrawal_request_requires_closed_cycle(self):
        cycle = create_cycle(client=self.client, mise=1000)

        with self.assertRaises(ValidationError):
            create_demande_retrait(cycle=cycle, type_demande="NORMAL", montant_souhaite=1000)

    def test_normal_withdrawal_request_amount_cannot_exceed_withdrawable_amount(self):
        cycle = create_cycle(client=self.client, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)

        with self.assertRaises(ValidationError):
            create_demande_retrait(cycle=cycle, type_demande="NORMAL", montant_souhaite=30001)

    def test_validating_request_notifies_client(self):
        cycle = create_cycle(client=self.client, mise=1000)
        demande = create_demande_retrait(cycle=cycle, type_demande="ANTICIPE", montant_souhaite=2000)

        approve_demande_retrait(demande=demande, processed_by=self.agent_user)

        demande.refresh_from_db()
        self.assertEqual(demande.statut, "VALIDEE")
        self.assertEqual(demande.processed_by, self.agent_user)
        self.assertEqual(Notification.objects.filter(user=self.client_user, is_read=False).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.agent_user, is_read=False).count(), 0)

    def test_rejecting_request_notifies_client(self):
        cycle = create_cycle(client=self.client, mise=1000)
        demande = create_demande_retrait(cycle=cycle, type_demande="ANTICIPE", montant_souhaite=2000)

        reject_demande_retrait(demande=demande, processed_by=self.agent_user)

        demande.refresh_from_db()
        self.assertEqual(demande.statut, "REJETEE")
        self.assertEqual(Notification.objects.filter(user=self.client_user, is_read=False).count(), 1)

    def test_executing_validated_request_creates_withdrawal_and_notifies_client(self):
        cycle = create_cycle(client=self.client, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)
        demande = create_demande_retrait(cycle=cycle, type_demande="NORMAL", montant_souhaite=5000)
        approve_demande_retrait(demande=demande, processed_by=self.agent_user)

        retrait = execute_retrait_from_demande(demande=demande, processed_by=self.agent_user)

        demande.refresh_from_db()
        self.assertEqual(retrait.montant, 5000)
        self.assertEqual(demande.retrait, retrait)
        self.assertEqual(get_montant_retirable(self.client), 25000)
        self.assertEqual(Notification.objects.filter(user=self.client_user, is_read=False).count(), 2)

    def test_database_check_rejects_cycle_mise_not_multiple_of_100(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Cycle.objects.create(
                    client=self.client,
                    agent=self.agent,
                    mise=1050,
                    nb_collectes=0,
                    solde_actuel=0,
                    statut="EN_COURS",
                )

    def test_database_check_rejects_incoherent_retenue_total(self):
        cycle = create_cycle(client=self.client, mise=1000)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Retenue.objects.create(
                    code="RET-BAD-001",
                    cycle=cycle,
                    montant=1000,
                    commission_agent=500,
                    commission_institution=400,
                )

    def test_database_check_rejects_invalid_demande_retrait_status(self):
        cycle = create_cycle(client=self.client, mise=1000)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DemandeRetrait.objects.create(
                    code="DMD-BAD-001",
                    cycle=cycle,
                    client=self.client,
                    type_demande="ANTICIPE",
                    statut="INVALIDE",
                )

    def test_soft_delete_cycle_requires_closed_status(self):
        cycle = create_cycle(client=self.client, mise=1000)

        with self.assertRaises(ValidationError):
            soft_delete_cycle(cycle=cycle, deleted_by=self.agent_user)

    def test_soft_delete_cycle_masks_closed_cycle(self):
        cycle = create_cycle(client=self.client, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)

        soft_delete_cycle(cycle=cycle, deleted_by=self.agent_user)

        cycle.refresh_from_db()
        self.assertIsNotNone(cycle.deleted_at)
        self.assertEqual(cycle.deleted_by, self.agent_user)
