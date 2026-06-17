from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.conf import settings

from accounts.forms import AgentForm, ClientForm
from finance.forms import CycleForm
from finance.services import create_cycle, create_depot
from finance.services import approve_demande_retrait, create_demande_retrait
from finance.models import DemandeRetrait
from accounts.services import create_client, soft_delete_agent, soft_delete_client

from .models import Agent, Client, Notification, User


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
        self.assertNotContains(response, "Tableau de bord administrateur")
        self.assertContains(response, "Montant retirable cumulé")
        self.assertContains(response, "Cycles récents")
        self.assertContains(response, "Top agents")

    def test_client_and_agent_detail_pages_are_accessible(self):
        self.client.force_login(self.admin)

        client_response = self.client.get(f"/clients/{self.client_profile.pk}/")
        agent_response = self.client.get(f"/agents/{self.agent.pk}/")

        self.assertEqual(client_response.status_code, 200)
        self.assertEqual(agent_response.status_code, 200)
        self.assertContains(client_response, "Retrait global")
        self.assertContains(agent_response, "Clients gérés")

    def test_login_page_is_accessible(self):
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accéder à la plateforme")

    def test_notification_center_icon_and_page_are_accessible(self):
        Notification.objects.create(
            user=self.admin,
            title="Nouvelle demande",
            message="Une nouvelle demande est en attente.",
            link="/demandes-retrait/",
        )
        self.client.force_login(self.admin)

        dashboard_response = self.client.get("/")
        notifications_response = self.client.get(reverse("notifications"))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, reverse("notifications"))
        self.assertEqual(notifications_response.status_code, 200)
        self.assertContains(notifications_response, "Centre")
        self.assertContains(notifications_response, "Nouvelle demande")

    def test_notification_preview_is_limited_to_fifteen_items(self):
        for index in range(16):
            Notification.objects.create(
                user=self.admin,
                title=f"Notification {index}",
                message=f"Message {index}",
            )
        self.client.force_login(self.admin)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Notification 15")
        self.assertNotContains(response, "Notification 0")
        self.assertContains(response, "Tout voir")

    def test_login_sets_session_expiry(self):
        response = self.client.post(
            reverse("login"),
            {"username": "admin-web", "password": "secret123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 60 * 60 * 2)

    def test_agent_dashboard_is_scoped_to_agent_profile(self):
        self.client.force_login(self.agent_user)
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mon profil agent")
        self.assertContains(response, "Mes clients")
        self.assertNotContains(response, "Top agents")
        self.assertNotContains(response, 'href="/agents/"')

    def test_agent_cannot_access_agents_list_view(self):
        self.client.force_login(self.agent_user)

        response = self.client.get("/agents/")

        self.assertEqual(response.status_code, 403)

    def test_client_cannot_access_backoffice_pages_and_sees_limited_navigation(self):
        self.client.force_login(self.client_user)

        dashboard_response = self.client.get("/")
        clients_response = self.client.get("/clients/")
        agents_response = self.client.get("/agents/")
        mouvements_response = self.client.get("/mouvements/")
        my_space_response = self.client.get("/mon-espace/")

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "Mon dossier")
        self.assertContains(dashboard_response, "Mes cycles")
        self.assertContains(dashboard_response, "Montant retirable")
        self.assertNotContains(dashboard_response, 'href="/clients/"')
        self.assertNotContains(dashboard_response, 'href="/agents/"')
        self.assertNotContains(dashboard_response, 'href="/mouvements/"')
        self.assertEqual(clients_response.status_code, 403)
        self.assertEqual(agents_response.status_code, 403)
        self.assertEqual(mouvements_response.status_code, 403)
        self.assertRedirects(my_space_response, reverse("client-detail", kwargs={"pk": self.client_profile.pk}))

    def test_seed_exam_data_creates_demo_accounts_and_minimum_data(self):
        out = StringIO()

        call_command("seed_exam_data", stdout=out)

        self.assertTrue(User.objects.filter(username="iam-admin", role="ADMIN").exists())
        self.assertTrue(User.objects.filter(username="iam-agent", role="AGENT").exists())
        self.assertTrue(User.objects.filter(username="iam-client", role="CLIENT").exists())
        self.assertTrue(Agent.objects.filter(matricule="AG-IAM-1", user__username="iam-agent").exists())
        self.assertTrue(Client.objects.filter(code_client="CL-AMINATA-001", user__username="iam-client").exists())
        self.assertIn("CollecteAdmin#2026", out.getvalue())

    def test_seed_exam_data_is_idempotent(self):
        call_command("seed_exam_data")
        call_command("seed_exam_data")

        self.assertEqual(User.objects.filter(username="iam-admin").count(), 1)
        self.assertEqual(User.objects.filter(username="iam-agent").count(), 1)
        self.assertEqual(User.objects.filter(username="iam-client").count(), 1)
        self.assertEqual(Agent.objects.filter(matricule="AG-IAM-1").count(), 1)
        self.assertEqual(Client.objects.filter(code_client="CL-AMINATA-001").count(), 1)

    def test_agent_only_sees_own_clients_in_clients_list(self):
        other_agent_user = User.objects.create_user(
            username="agent-list-other",
            password="secret123",
            telephone="700100020",
            role="AGENT",
        )
        other_agent = Agent.objects.create(
            user=other_agent_user,
            matricule="AG-LIST-OTHER",
            nom="Coulibaly",
            prenom="Sira",
            telephone="700100020",
        )
        other_client = Client.objects.create(
            agent=other_agent,
            code_client="CL-LIST-OTHER",
            nom="Keita",
            prenom="Awa",
            telephone="700100021",
        )
        self.client.force_login(self.agent_user)

        response = self.client.get(reverse("clients"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.client_profile.code_client)
        self.assertNotContains(response, other_client.code_client)
        self.assertNotContains(response, 'id="clients-agent"')

    def test_cycle_form_for_agent_only_exposes_own_clients(self):
        other_agent_user = User.objects.create_user(
            username="agent-form-other",
            password="secret123",
            telephone="700100030",
            role="AGENT",
        )
        other_agent = Agent.objects.create(
            user=other_agent_user,
            matricule="AG-FORM-OTHER",
            nom="Cisse",
            prenom="Mariam",
            telephone="700100030",
        )
        other_client = Client.objects.create(
            agent=other_agent,
            code_client="CL-FORM-OTHER",
            nom="Sangare",
            prenom="Aicha",
            telephone="700100031",
        )

        form = CycleForm(user=self.agent_user)

        self.assertIn(self.client_profile, form.fields["client"].queryset)
        self.assertNotIn(other_client, form.fields["client"].queryset)

    def test_client_can_create_withdrawal_request_for_own_cycle(self):
        self.client.force_login(self.client_user)

        response = self.client.post(
            reverse("cycle-demande-retrait", kwargs={"pk": self.cycle.pk}),
            {
                "type_demande": "ANTICIPE",
                "montant_souhaite": "2000",
                "motif": "Besoin ponctuel",
            },
        )

        self.assertRedirects(response, reverse("cycle-detail", kwargs={"pk": self.cycle.pk}))
        self.assertEqual(DemandeRetrait.objects.count(), 1)
        demande = DemandeRetrait.objects.get()
        self.assertEqual(demande.client, self.client_profile)
        self.assertEqual(demande.created_by, self.client_user)
        self.assertEqual(demande.type_demande, "ANTICIPE")
        self.assertEqual(Notification.objects.filter(user=self.agent_user, is_read=False).count(), 1)

    def test_staff_can_create_anticipatory_request_for_client_without_account(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("cycle-demande-retrait", kwargs={"pk": self.cycle.pk}),
            {
                "type_demande": "ANTICIPE",
                "montant_souhaite": "2000",
                "motif": "Demande transmise par l'agent",
            },
        )

        self.assertRedirects(response, reverse("cycle-detail", kwargs={"pk": self.cycle.pk}))
        demande = DemandeRetrait.objects.get()
        self.assertEqual(demande.created_by, self.admin)
        self.assertEqual(demande.type_demande, "ANTICIPE")

    def test_staff_can_access_demandes_page(self):
        DemandeRetrait.objects.create(
            code="DMD-LIST-001",
            cycle=self.cycle,
            client=self.client_profile,
            created_by=self.client_user,
            type_demande="ANTICIPE",
            montant_souhaite=2000,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("demandes-retrait"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demandes de retrait")
        self.assertContains(response, "DMD-LIST-001")
        self.assertContains(response, "Valider")

    def test_admin_can_update_agent_and_reset_password(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("agent-update", kwargs={"pk": self.agent.pk}),
            {
                "matricule": "AG-DTL-2",
                "nom": "Diallo",
                "prenom": "Moussa",
                "telephone": "700199999",
                "zone": "Zone nord",
                "password": "agentStrong#2026",
                "password_confirm": "agentStrong#2026",
            },
        )

        self.assertRedirects(response, reverse("agent-detail", kwargs={"pk": self.agent.pk}))
        self.agent.refresh_from_db()
        self.agent_user.refresh_from_db()
        self.assertEqual(self.agent.matricule, "AG-DTL-2")
        self.assertEqual(self.agent.nom, "Diallo")
        self.assertEqual(self.agent.prenom, "Moussa")
        self.assertEqual(self.agent.telephone, "700199999")
        self.assertEqual(self.agent_user.first_name, "Moussa")
        self.assertEqual(self.agent_user.last_name, "Diallo")
        self.assertEqual(self.agent_user.telephone, "700199999")
        self.assertTrue(self.agent_user.check_password("agentStrong#2026"))

    def test_agent_can_update_own_client_and_sync_linked_user(self):
        self.client.force_login(self.agent_user)

        response = self.client.post(
            reverse("client-update", kwargs={"pk": self.client_profile.pk}),
            {
                "agent": str(self.agent.pk),
                "nom": "Keita",
                "prenom": "Awa",
                "telephone": "700188888",
                "email": "awa@example.com",
                "adresse": "Bamako",
            },
        )

        self.assertRedirects(response, reverse("client-detail", kwargs={"pk": self.client_profile.pk}))
        self.client_profile.refresh_from_db()
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_profile.nom, "Keita")
        self.assertEqual(self.client_profile.prenom, "Awa")
        self.assertEqual(self.client_profile.telephone, "700188888")
        self.assertEqual(self.client_profile.email, "awa@example.com")
        self.assertEqual(self.client_user.first_name, "Awa")
        self.assertEqual(self.client_user.last_name, "Keita")
        self.assertEqual(self.client_user.telephone, "700188888")
        self.assertEqual(self.client_user.email, "awa@example.com")

    def test_admin_can_update_client_and_reset_password(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("client-update", kwargs={"pk": self.client_profile.pk}),
            {
                "agent": str(self.agent.pk),
                "nom": "Traore",
                "prenom": "Aminata",
                "telephone": "700177777",
                "email": "aminata@example.com",
                "adresse": "Hamdallaye",
                "password": "clientStrong#2026",
                "password_confirm": "clientStrong#2026",
            },
        )

        self.assertRedirects(response, reverse("client-detail", kwargs={"pk": self.client_profile.pk}))
        self.client_profile.refresh_from_db()
        self.client_user.refresh_from_db()
        self.assertEqual(self.client_profile.telephone, "700177777")
        self.assertEqual(self.client_user.telephone, "700177777")
        self.assertTrue(self.client_user.check_password("clientStrong#2026"))

    def test_agent_cannot_see_password_fields_on_client_update(self):
        self.client.force_login(self.agent_user)

        response = self.client.get(reverse("client-update", kwargs={"pk": self.client_profile.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Nouveau mot de passe")

    def test_cycle_update_link_is_visible_only_before_any_deposit(self):
        self.client.force_login(self.admin)
        editable_cycle = create_cycle(client=self.client_profile, mise=1000)
        locked_cycle = create_cycle(client=self.client_profile, mise=1000)
        create_depot(cycle=locked_cycle, nb_mises=1)

        response = self.client.get(reverse("cycles"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("cycle-update", kwargs={"pk": editable_cycle.pk}))
        self.assertNotContains(response, reverse("cycle-update", kwargs={"pk": locked_cycle.pk}))

    def test_client_detail_replaces_local_cycles_tab_with_demandes(self):
        DemandeRetrait.objects.create(
            code="DMD-CLIENT-001",
            cycle=self.cycle,
            client=self.client_profile,
            created_by=self.client_user,
            type_demande="ANTICIPE",
            montant_souhaite=2000,
        )
        self.client.force_login(self.client_user)

        response = self.client.get(reverse("client-detail", kwargs={"pk": self.client_profile.pk}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-tab-target="demandes"', html=False)
        self.assertContains(response, "Demandes de retrait")
        self.assertContains(response, "DMD-CLIENT-001")
        self.assertNotContains(response, "Cycles associés")

    def test_staff_can_access_commissions_page(self):
        create_depot(cycle=self.cycle, nb_mises=26)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("commissions"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commissions par cycle")
        self.assertContains(response, "Commission institution")
        self.assertContains(response, f"#{self.cycle.pk}")

    def test_staff_cannot_create_normal_request_from_cycle_detail(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("cycle-demande-retrait", kwargs={"pk": self.cycle.pk}),
            {
                "type_demande": "NORMAL",
                "montant_souhaite": "2000",
                "motif": "Test",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(DemandeRetrait.objects.count(), 0)

    def test_staff_can_register_direct_withdrawal_from_cycle_detail(self):
        cycle = create_cycle(client=self.client_profile, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("cycle-retrait-direct", kwargs={"pk": cycle.pk}),
            {"montant": "5000"},
        )

        self.assertRedirects(response, reverse("cycle-detail", kwargs={"pk": cycle.pk}))
        self.client_profile.refresh_from_db()
        self.assertEqual(self.client_profile.retraits.count(), 1)
        self.assertEqual(self.client_profile.retraits.first().montant, 5000)

    def test_soft_delete_client_requires_no_open_cycle(self):
        with self.assertRaisesMessage(Exception, "cycle en cours"):
            soft_delete_client(client=self.client_profile, deleted_by=self.admin)

    def test_soft_delete_client_masks_closed_cycles_and_deactivates_account(self):
        create_depot(cycle=self.cycle, nb_mises=26)
        cycle = create_cycle(client=self.client_profile, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)

        soft_delete_client(client=self.client_profile, deleted_by=self.admin)

        self.client_profile.refresh_from_db()
        cycle.refresh_from_db()
        self.client_user.refresh_from_db()
        self.assertIsNotNone(self.client_profile.deleted_at)
        self.assertIsNotNone(cycle.deleted_at)
        self.assertFalse(self.client_user.is_active)

    def test_soft_delete_agent_requires_no_open_cycle(self):
        with self.assertRaisesMessage(Exception, "cycle en cours"):
            soft_delete_agent(agent=self.agent, deleted_by=self.admin)

    def test_soft_delete_agent_masks_linked_closed_data_and_deactivates_accounts(self):
        create_depot(cycle=self.cycle, nb_mises=26)
        cycle = create_cycle(client=self.client_profile, mise=1000)
        create_depot(cycle=cycle, nb_mises=31)

        soft_delete_agent(agent=self.agent, deleted_by=self.admin)

        self.agent.refresh_from_db()
        self.client_profile.refresh_from_db()
        cycle.refresh_from_db()
        self.agent_user.refresh_from_db()
        self.client_user.refresh_from_db()
        self.assertIsNotNone(self.agent.deleted_at)
        self.assertIsNotNone(self.client_profile.deleted_at)
        self.assertIsNotNone(cycle.deleted_at)
        self.assertFalse(self.agent_user.is_active)
        self.assertFalse(self.client_user.is_active)

    def test_client_code_is_generated_automatically_when_missing(self):
        client = create_client(
            agent=self.agent,
            nom="Diallo",
            prenom="Fatou",
            telephone="700100004",
        )

        self.assertTrue(client.code_client.startswith("CL-"))
        self.assertNotIn("TMP-", client.code_client)

    def test_client_account_fields_become_required_when_checkbox_is_checked(self):
        form = ClientForm(
            data={
                "agent": self.agent.pk,
                "nom": "Diallo",
                "prenom": "Fatou",
                "telephone": "700100005",
                "email": "",
                "adresse": "",
                "create_account": "on",
                "username": "",
                "password": "",
                "password_confirm": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertIn("password", form.errors)
        self.assertIn("password_confirm", form.errors)

    def test_agent_form_always_requires_account_credentials(self):
        form = AgentForm(
            data={
                "matricule": "AG-NEW-1",
                "nom": "Keita",
                "prenom": "Moussa",
                "telephone": "700100006",
                "zone": "Bamako",
                "username": "",
                "password": "",
                "password_confirm": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertNotIn("create_account", form.fields)
        self.assertIn("username", form.errors)
        self.assertIn("password", form.errors)
        self.assertIn("password_confirm", form.errors)

    def test_dashboard_exposes_recent_mouvement_limit(self):
        self.client.force_login(self.admin)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Affichage limité à 5 lignes")

    def test_admin_can_toggle_agent_account_status(self):
        self.client.force_login(self.admin)
        self.assertTrue(self.agent_user.is_active)

        response = self.client.post(reverse("agent-account-toggle", kwargs={"pk": self.agent.pk}))

        self.assertRedirects(response, reverse("agent-detail", kwargs={"pk": self.agent.pk}))
        self.agent_user.refresh_from_db()
        self.assertFalse(self.agent_user.is_active)

    def test_agent_can_toggle_owned_client_account_status(self):
        self.client.force_login(self.agent_user)
        self.assertTrue(self.client_user.is_active)

        response = self.client.post(reverse("client-account-toggle", kwargs={"pk": self.client_profile.pk}))

        self.assertRedirects(response, reverse("client-detail", kwargs={"pk": self.client_profile.pk}))
        self.client_user.refresh_from_db()
        self.assertFalse(self.client_user.is_active)

    def test_agent_cannot_toggle_unowned_client_account_status(self):
        other_agent_user = User.objects.create_user(
            username="agent-other",
            password="secret123",
            telephone="700100010",
            role="AGENT",
        )
        other_agent = Agent.objects.create(
            user=other_agent_user,
            matricule="AG-OTHER",
            nom="Coulibaly",
            prenom="Mariam",
            telephone="700100010",
        )
        other_client_user = User.objects.create_user(
            username="client-other",
            password="secret123",
            telephone="700100011",
            role="CLIENT",
        )
        other_client = Client.objects.create(
            user=other_client_user,
            agent=other_agent,
            code_client="CL-OTHER",
            nom="Diallo",
            prenom="Awa",
            telephone="700100011",
        )

        self.client.force_login(self.agent_user)
        response = self.client.post(reverse("client-account-toggle", kwargs={"pk": other_client.pk}))

        self.assertEqual(response.status_code, 404)
        other_client_user.refresh_from_db()
        self.assertTrue(other_client_user.is_active)

    def test_admin_can_validate_request_and_client_receives_notification(self):
        demande = DemandeRetrait.objects.create(
            code="DMD-TEST-001",
            cycle=self.cycle,
            client=self.client_profile,
            created_by=self.client_user,
            type_demande="ANTICIPE",
            montant_souhaite=2000,
        )
        self.client.force_login(self.admin)

        response = self.client.post(reverse("demande-retrait-approve", kwargs={"pk": demande.pk}))

        self.assertRedirects(response, reverse("cycle-detail", kwargs={"pk": self.cycle.pk}))
        demande.refresh_from_db()
        self.assertEqual(demande.statut, "VALIDEE")
        self.assertEqual(Notification.objects.filter(user=self.client_user, is_read=False).count(), 1)

    def test_validation_error_flash_is_rendered_without_brackets(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("cycle-retrait-direct", kwargs={"pk": self.cycle.pk}),
            {"montant": "999999"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Le montant retirable calculé est insuffisant.")
        self.assertNotContains(response, "['Le montant retirable calculé est insuffisant.']")

    def test_notification_can_be_marked_as_read(self):
        notification = Notification.objects.create(
            user=self.client_user,
            title="Demande validée",
            message="Votre demande a été validée.",
            link=f"/cycles/{self.cycle.pk}/",
        )
        self.client.force_login(self.client_user)

        response = self.client.post(
            reverse("notification-read", kwargs={"pk": notification.pk}),
            {"next": reverse("dashboard")},
        )

        self.assertRedirects(response, reverse("dashboard"))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_notifications_page_defaults_to_unread_items(self):
        Notification.objects.create(
            user=self.admin,
            title="Visible",
            message="Notification non lue.",
        )
        Notification.objects.create(
            user=self.admin,
            title="Masquée",
            message="Notification déjà lue.",
            is_read=True,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("notifications"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Masquée")

    def test_processed_demande_notification_is_hidden_from_notifications(self):
        demande = create_demande_retrait(
            cycle=self.cycle,
            type_demande="ANTICIPE",
            montant_souhaite=2000,
            created_by=self.client_user,
        )
        approve_demande_retrait(demande=demande, processed_by=self.admin)
        self.client.force_login(self.agent_user)

        dashboard_response = self.client.get(reverse("dashboard"))
        notifications_response = self.client.get(reverse("notifications"))

        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(notifications_response.status_code, 200)
        self.assertNotContains(dashboard_response, demande.code)
        self.assertNotContains(notifications_response, demande.code)
