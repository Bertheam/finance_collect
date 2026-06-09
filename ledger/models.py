from django.core.exceptions import ValidationError
from django.db import models

from finance.models import Cycle


class MouvementFinancier(models.Model):
    TYPE_MOUVEMENTS = (
        ("MISE", "MISE"),
        ("RETENUE", "RETENUE"),
        ("COM_AGENT", "COM_AGENT"),
        ("COM_INSTITUTION", "COM_INSTITUTION"),
        ("CREDIT_CLIENT", "CREDIT_CLIENT"),
        ("RETRAIT", "RETRAIT"),
    )

    ACTEUR_CHOICES = (
        ("CLIENT", "CLIENT"),
        ("CYCLE", "CYCLE"),
        ("AGENT", "AGENT"),
        ("INSTITUTION", "INSTITUTION"),
    )

    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.PROTECT,
        related_name="mouvements",
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        "accounts.Client",
        on_delete=models.PROTECT,
        related_name="mouvements",
        null=True,
        blank=True,
    )
    agent = models.ForeignKey(
        "accounts.Agent",
        on_delete=models.PROTECT,
        related_name="mouvements",
        null=True,
        blank=True,
    )
    type_mouvement = models.CharField(max_length=50, choices=TYPE_MOUVEMENTS)
    source = models.CharField(max_length=50, choices=ACTEUR_CHOICES)
    destination = models.CharField(max_length=50, choices=ACTEUR_CHOICES)
    montant = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.type_mouvement == "RETRAIT" and self.client_id is None:
            raise ValidationError({"client": "Un retrait doit etre rattache a un client."})
        if self.type_mouvement != "RETRAIT" and self.cycle_id is None:
            raise ValidationError({"cycle": "Ce mouvement doit etre rattache a un cycle."})
        if self.type_mouvement in {"MISE", "RETENUE", "COM_AGENT", "COM_INSTITUTION", "CREDIT_CLIENT"}:
            if self.client_id is None:
                raise ValidationError({"client": "Ce mouvement doit etre rattache a un client."})
            if self.agent_id is None:
                raise ValidationError({"agent": "Ce mouvement doit etre rattache a un agent."})

    def __str__(self):
        return f"{self.type_mouvement} - {self.montant}"
