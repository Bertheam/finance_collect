from django.test import TestCase

from finance.services import create_cycle, create_depot

from .models import Agent, Client, User


class MonolithPagesTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin-web",
            password="secret123",
            telephone="700100001",
            role="ADMIN",
        )
        self.agent_user = User.objects.create_user(
            username="agent-web",
            password="secret123",
            telephone="700100002",
            role="AGENT",
        )
        self.agent = Agent.objects.create(
            user=self.agent_user,
            matricule="AG-DTL",
            nom="IAM",
            prenom="Agent",
            telephone="700100002",
            zone="Zone test",
        )
        self.client_user = User.objects.create_user(
            username="client-web",
            password="secret123",
            telephone="700100003",
            role="CLIENT",
        )
        self.client_profile = Client.objects.create(
            user=self.client_user,
            agent=self.agent,
            code_client="CL-DTL",
            nom="Traore",
            prenom="Aminata",
            telephone="700100003",
        )
        self.cycle = create_cycle(client=self.client_profile, mise=1000)
        create_depot(cycle=self.cycle, nb_mises=5)

    def test_dashboard_page_is_accessible_for_authenticated_user(self):
        self.client.force_login(self.admin)
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tableau de bord operationnel")
        self.assertContains(response, "Montant retirable cumule")

    def test_client_and_agent_detail_pages_are_accessible(self):
        self.client.force_login(self.admin)

        client_response = self.client.get(f"/clients/{self.client_profile.pk}/")
        agent_response = self.client.get(f"/agents/{self.agent.pk}/")

        self.assertEqual(client_response.status_code, 200)
        self.assertEqual(agent_response.status_code, 200)
        self.assertContains(client_response, "Retrait global")
        self.assertContains(agent_response, "Clients geres")

    def test_login_page_is_accessible(self):
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Acceder au cockpit")
