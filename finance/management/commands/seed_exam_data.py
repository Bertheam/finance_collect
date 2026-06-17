from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from accounts.models import Agent, Client, User
from finance.models import Cycle
from finance.services import create_cycle, create_depot, create_retrait, get_montant_retirable


class Command(BaseCommand):
    help = "Charge le jeu de donnees minimum demande par le sujet."

    admin_credentials = ("iam-admin", "CollecteAdmin#2026")
    agent_credentials = ("iam-agent", "CollecteAgent#2026")
    client_credentials = ("iam-client", "CollecteClient#2026")

    def _related_profile(self, user, relation_name):
        try:
            return getattr(user, relation_name)
        except ObjectDoesNotExist:
            return None

    def _unique_user_value(self, *, field_name, desired_value, current_user=None):
        candidate = desired_value
        suffix = 1
        queryset = User.objects.all()
        if current_user is not None and current_user.pk:
            queryset = queryset.exclude(pk=current_user.pk)

        while queryset.filter(**{field_name: candidate}).exists():
            candidate = f"{desired_value}-{suffix}"
            suffix += 1

        return candidate

    def ensure_admin_user(self, *, username, password, telephone, first_name="", last_name="", email=""):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "telephone": telephone,
                "role": "ADMIN",
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        user.telephone = telephone
        user.role = "ADMIN"
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        if created or not user.check_password(password):
            user.set_password(password)
            user.save()
        else:
            user.save(update_fields=["telephone", "role", "first_name", "last_name", "email", "is_staff", "is_superuser", "is_active"])

        return user

    def ensure_profile_user(
        self,
        *,
        profile,
        relation_name,
        desired_username,
        password,
        telephone,
        role,
        first_name="",
        last_name="",
        email="",
    ):
        user = getattr(profile, "user", None)
        if user is None:
            candidate = User.objects.filter(username=desired_username).first()
            if candidate is not None:
                owner = self._related_profile(candidate, relation_name)
                if owner is None or owner.pk == profile.pk:
                    user = candidate

        if user is None:
            user = User(role=role)

        desired_username = self._unique_user_value(
            field_name="username",
            desired_value=desired_username,
            current_user=user if user.pk else None,
        )
        desired_telephone = self._unique_user_value(
            field_name="telephone",
            desired_value=telephone,
            current_user=user if user.pk else None,
        )

        user.username = desired_username
        user.telephone = desired_telephone
        user.role = role
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.is_active = True
        user.set_password(password)
        user.save()

        if profile.user_id != user.id:
            profile.user = user
            profile.save(update_fields=["user"])

        return user

    @transaction.atomic
    def handle(self, *args, **options):
        admin_user = self.ensure_admin_user(
            username=self.admin_credentials[0],
            password=self.admin_credentials[1],
            telephone="700000000",
            first_name="IAM",
            last_name="Admin",
            email="admin@finance-collecte.local",
        )

        agent, _ = Agent.objects.get_or_create(
            matricule="AG-IAM-1",
            defaults={
                "nom": "IAM",
                "prenom": "Agent 1",
                "telephone": "700000001",
                "zone": "Bamako",
            },
        )

        client, _ = Client.objects.get_or_create(
            code_client="CL-AMINATA-001",
            defaults={
                "agent": agent,
                "nom": "TRAORE",
                "prenom": "Aminata",
                "telephone": "700000002",
                "email": "aminata.traore@example.com",
                "adresse": "Bamako",
            },
        )

        agent_user = self.ensure_profile_user(
            profile=agent,
            relation_name="agent_profile",
            desired_username=self.agent_credentials[0],
            password=self.agent_credentials[1],
            telephone=agent.telephone,
            role="AGENT",
            first_name=agent.prenom,
            last_name=agent.nom,
        )
        client_user = self.ensure_profile_user(
            profile=client,
            relation_name="client_profile",
            desired_username=self.client_credentials[0],
            password=self.client_credentials[1],
            telephone=client.telephone,
            role="CLIENT",
            first_name=client.prenom,
            last_name=client.nom,
            email=client.email or "",
        )

        if client.agent_id != agent.id:
            client.agent = agent
            client.save(update_fields=["agent"])

        cycle = (
            Cycle.objects.filter(client=client, mise=1000, nb_collectes=31, statut="CLOTURE")
            .order_by("id")
            .first()
        )
        if cycle is None:
            cycle = create_cycle(client=client, mise=1000)
            create_depot(cycle=cycle, nb_mises=31)
            cycle.refresh_from_db()

        if not client.retraits.exists() and get_montant_retirable(client) >= 5000:
            create_retrait(client=client, montant=5000)

        self.stdout.write(self.style.SUCCESS("Jeu de donnees minimal charge."))
        self.stdout.write(f"Admin: {admin_user.username} / {self.admin_credentials[1]}")
        self.stdout.write(f"Agent: {agent_user.username} / {self.agent_credentials[1]}")
        self.stdout.write(f"Client: {client_user.username} / {self.client_credentials[1]}")
        self.stdout.write(f"Agent: {agent.matricule} - {agent.prenom} {agent.nom}")
        self.stdout.write(f"Client: {client.code_client} - {client.prenom} {client.nom}")
        self.stdout.write(
            f"Cycle ferme: #{cycle.id} | mise={cycle.mise} | collectes={cycle.nb_collectes} | statut={cycle.statut}"
        )
        self.stdout.write(f"Montant retirable courant: {get_montant_retirable(client)}")
