from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Agent, Client, User
from finance.services import create_cycle, create_depot
from ledger.models import MouvementFinancier


class LedgerMonolithTests(TestCase):
    def setUp(self):
        self.agent_user = User.objects.create_user(
            username="agent-ledger",
            password="secret123",
            telephone="700400000",
            role="AGENT",
        )
        self.agent = Agent.objects.create(
            user=self.agent_user,
            matricule="AGLED001",
            nom="IAM",
            prenom="Agent",
            telephone="700400000",
            zone="Bamako",
        )

        self.client_user = User.objects.create_user(
            username="client-ledger",
            password="secret123",
            telephone="700500000",
            role="CLIENT",
        )
        self.client_profile = Client.objects.create(
            user=self.client_user,
            agent=self.agent,
            code_client="CLLED001",
            nom="Traore",
            prenom="Aminata",
            telephone="700500000",
        )

        self.other_client_user = User.objects.create_user(
            username="client-ledger-2",
            password="secret123",
            telephone="700500001",
            role="CLIENT",
        )
        self.other_client = Client.objects.create(
            user=self.other_client_user,
            agent=self.agent,
            code_client="CLLED002",
            nom="Diallo",
            prenom="Fatou",
            telephone="700500001",
        )

    def test_client_only_sees_own_mouvements(self):
        own_cycle = create_cycle(client=self.client_profile, mise=1000)
        other_cycle = create_cycle(client=self.other_client, mise=1000)
        create_depot(cycle=own_cycle, nb_mises=1)
        create_depot(cycle=other_cycle, nb_mises=1)

        self.client.force_login(self.client_user)
        response = self.client.get("/mouvements/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CLLED001")
        self.assertNotContains(response, "CLLED002")
        self.assertContains(response, "MISE")

    def test_database_check_rejects_invalid_mouvement_flux(self):
        cycle = create_cycle(client=self.client_profile, mise=1000)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MouvementFinancier.objects.create(
                    cycle=cycle,
                    client=self.client_profile,
                    agent=self.agent,
                    type_mouvement="MISE",
                    source="INSTITUTION",
                    destination="CLIENT",
                    montant=1000,
                )
