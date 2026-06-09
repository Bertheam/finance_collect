from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Agent, Client
from finance.models import Cycle
from finance.services import create_cycle, create_depot, create_retrait, get_montant_retirable


class Command(BaseCommand):
    help = "Charge le jeu de donnees minimum demande par le sujet."

    @transaction.atomic
    def handle(self, *args, **options):
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
        self.stdout.write(f"Agent: {agent.matricule} - {agent.prenom} {agent.nom}")
        self.stdout.write(f"Client: {client.code_client} - {client.prenom} {client.nom}")
        self.stdout.write(
            f"Cycle ferme: #{cycle.id} | mise={cycle.mise} | collectes={cycle.nb_collectes} | statut={cycle.statut}"
        )
        self.stdout.write(f"Montant retirable courant: {get_montant_retirable(client)}")
